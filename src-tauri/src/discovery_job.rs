//! 将扫描进程树置于 Job 中，防止单文件 Sidecar 的子进程在取消后继续运行。
use std::os::windows::io::AsRawHandle;
use std::process::Child;
use windows_sys::Win32::Foundation::{CloseHandle, HANDLE, INVALID_HANDLE_VALUE};
use windows_sys::Win32::System::Diagnostics::ToolHelp::{CreateToolhelp32Snapshot, Thread32First, Thread32Next, THREADENTRY32, TH32CS_SNAPTHREAD};
use windows_sys::Win32::System::JobObjects::{AssignProcessToJobObject, CreateJobObjectW, SetInformationJobObject, JobObjectExtendedLimitInformation, JOBOBJECT_EXTENDED_LIMIT_INFORMATION, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE};
use windows_sys::Win32::System::Threading::{OpenThread, ResumeThread, THREAD_SUSPEND_RESUME};

pub struct Job(HANDLE);
impl Drop for Job {
    fn drop(&mut self) { unsafe { CloseHandle(self.0); } }
}

impl Job {
    pub fn attach_and_resume(child: &Child) -> Result<Self, String> {
        unsafe {
            let handle = CreateJobObjectW(std::ptr::null(), std::ptr::null());
            if handle.is_null() { return Err("process_failed".into()); }
            let job = Self(handle);
            let mut info: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = std::mem::zeroed();
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            if SetInformationJobObject(handle, JobObjectExtendedLimitInformation, &info as *const _ as _, std::mem::size_of_val(&info) as u32) == 0
                || AssignProcessToJobObject(handle, child.as_raw_handle() as _) == 0 {
                return Err("process_failed".into());
            }
            // 进程以挂起状态创建；先加入 Job，再恢复主线程，消除子进程逃逸的竞态。
            let snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
            if snapshot == INVALID_HANDLE_VALUE { return Err("process_failed".into()); }
            let mut entry: THREADENTRY32 = std::mem::zeroed();
            entry.dwSize = std::mem::size_of_val(&entry) as u32;
            let mut more = Thread32First(snapshot, &mut entry);
            let mut resumed = false;
            while more != 0 {
                if entry.th32OwnerProcessID == child.id() {
                    let thread = OpenThread(THREAD_SUSPEND_RESUME, 0, entry.th32ThreadID);
                    if !thread.is_null() {
                        resumed = ResumeThread(thread) != u32::MAX;
                        CloseHandle(thread);
                    }
                    break;
                }
                more = Thread32Next(snapshot, &mut entry);
            }
            CloseHandle(snapshot);
            if !resumed { return Err("process_failed".into()); }
            Ok(job)
        }
    }
}
