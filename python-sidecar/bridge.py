"""GBT Register Manager - Python Sidecar bridge.

协议（与 Rust 侧保持一致）：
- stdin  : UTF-8 JSON 单帧（Rust 写入后立即 close，收到 EOF 开始处理）
- stdout : UTF-8 文本，业务结果包裹在 `<<<GBT-BEGIN>>>` / `<<<GBT-END>>>` 之间；
           SDK/第三方库的任意垃圾输出都不会污染结果。
- stderr : 调试日志（`[GBT-PY] ...`），Rust 侧不用于解析。

退出码：
- 0 : 已输出一帧结果（ok 字段为 true 或 false）
- 1 : 未输出帧（sidecar 自身崩溃，Rust 兜底构造错误）
"""

from __future__ import annotations

import json
import logging
import math
import os
import sys
import traceback
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple

# ---------- 环境准备 --------------------------------------------------------

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", newline="")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", newline="")

try:
    import openpyxl  # noqa: F401  (显式校验，缺失时给出清晰错误)
    from openpyxl import Workbook
except Exception as _openpyxl_err:  # pragma: no cover
    Workbook = None  # type: ignore[assignment]
    _OPENPYXL_ERR = _openpyxl_err
else:
    _OPENPYXL_ERR = None

# ---------- 日志 ------------------------------------------------------------


def _resolve_log_dir() -> Path:
    """优先使用 Rust 通过环境变量传入的 app_log_dir；否则回退到用户目录。"""
    env_dir = os.environ.get("GBT_LOG_DIR")
    if env_dir:
        try:
            p = Path(env_dir)
            p.mkdir(parents=True, exist_ok=True)
            return p
        except Exception:
            pass
    fallback = Path.home() / ".gbt-register-manager" / "logs"
    try:
        fallback.mkdir(parents=True, exist_ok=True)
    except Exception:
        fallback = Path(os.getcwd())
    return fallback


_LOG_DIR = _resolve_log_dir()
_LOGGER = logging.getLogger("gbt-py")
_LOGGER.setLevel(logging.INFO)
_LOGGER.propagate = False
if not _LOGGER.handlers:
    _stderr_handler = logging.StreamHandler(sys.stderr)
    _stderr_handler.setFormatter(logging.Formatter("[GBT-PY] %(asctime)s %(levelname)s %(message)s"))
    _LOGGER.addHandler(_stderr_handler)
    try:
        _file_handler = RotatingFileHandler(
            _LOG_DIR / "gbt-py.log", maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        _file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        _LOGGER.addHandler(_file_handler)
    except Exception:  # pragma: no cover
        pass


def log_py(msg: str) -> None:
    _LOGGER.info(msg)


# ---------- Agilebot SDK 延迟加载 -------------------------------------------

try:
    from Agilebot import Arm, PoseRegister, PoseType, ProgramPose, StatusCodeEnum
except Exception as _sdk_err:  # pragma: no cover
    Arm = None  # type: ignore[assignment]
    PoseRegister = None  # type: ignore[assignment]
    PoseType = None  # type: ignore[assignment]
    ProgramPose = None  # type: ignore[assignment]
    StatusCodeEnum = None  # type: ignore[assignment]
    _SDK_IMPORT_ERR: Exception | None = _sdk_err
else:
    _SDK_IMPORT_ERR = None


def _ensure_sdk_ready() -> None:
    if Arm is None or StatusCodeEnum is None:
        err = f": {_SDK_IMPORT_ERR!r}" if _SDK_IMPORT_ERR is not None else ""
        raise RuntimeError(
            "未找到 Agilebot Python SDK。请确认已安装 Python_v2.0.1.0 目录中的 .whl，"
            f"或在打包脚本中已正确嵌入 SDK{err}。"
        )


# ---------- 协议辅助 --------------------------------------------------------

FRAME_BEGIN = "<<<GBT-BEGIN>>>"
FRAME_END = "<<<GBT-END>>>"


def emit_frame(data: Dict[str, Any]) -> None:
    """写出被分隔符包裹的单帧 JSON（UTF-8，不转义非 ASCII）。"""
    text = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    sys.stdout.write(FRAME_BEGIN)
    sys.stdout.write("\n")
    sys.stdout.write(text)
    sys.stdout.write("\n")
    sys.stdout.write(FRAME_END)
    sys.stdout.write("\n")
    sys.stdout.flush()


def read_payload() -> Dict[str, Any]:
    """从 stdin 读取 UTF-8 JSON 载荷（Rust 端写完后 close stdin）。"""
    raw = sys.stdin.read()
    if not raw:
        raise RuntimeError("stdin 无输入 payload")
    return json.loads(raw)


@contextmanager
def redirect_sdk_stdout_to_stderr() -> Iterator[None]:
    """保护 stdout 不被 SDK/第三方库污染——它们 print 的一切重定向到 stderr。"""
    original = sys.stdout
    sys.stdout = sys.stderr
    try:
        yield
    finally:
        sys.stdout = original


# ---------- 通用工具 --------------------------------------------------------


def round3(v: Any) -> float:
    x = float(v)
    if math.isnan(x) or math.isinf(x):
        return 0.0
    return round(x, 3)


def unwrap_status(ret: Any) -> Any:
    if isinstance(ret, tuple) and len(ret) >= 2:
        return ret[-1]
    return ret


def status_text(ret: Any) -> str:
    st = unwrap_status(ret)
    return getattr(st, "errmsg", str(st))


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _coord_from_pose(pose: Any) -> str:
    try:
        lr = pose.poseData.cartData.baseCart.posture.arm_left_right
    except Exception:
        return "R"
    if isinstance(lr, str):
        s = lr.strip().upper()
        if s in ("L", "LEFT"):
            return "L"
        if s in ("R", "RIGHT"):
            return "R"
    n = _safe_int(lr, 1)
    return "L" if n < 0 else "R"


def _apply_coord_to_pose(pose: Any, coord: str) -> None:
    try:
        lr = pose.poseData.cartData.baseCart.posture.arm_left_right
    except Exception:
        return
    c = str(coord or "").strip().upper()
    value = -1 if c == "L" else 1
    try:
        pose.poseData.cartData.baseCart.posture.arm_left_right = value
    except Exception:
        try:
            pose.poseData.cartData.baseCart.posture.arm_left_right = "L" if value < 0 else "R"
        except Exception:
            pose.poseData.cartData.baseCart.posture.arm_left_right = lr


def _coord_from_pose_register(pose_register: Any) -> str:
    try:
        lr = pose_register.poseRegisterData.cartData.posture.arm_left_right
    except Exception:
        return "R"
    if isinstance(lr, str):
        s = lr.strip().upper()
        if s in ("L", "LEFT"):
            return "L"
        if s in ("R", "RIGHT"):
            return "R"
    n = _safe_int(lr, 1)
    return "L" if n < 0 else "R"


def _apply_coord_to_pose_register(pose_register: Any, coord: str) -> None:
    try:
        old_lr = pose_register.poseRegisterData.cartData.posture.arm_left_right
    except Exception:
        return
    c = str(coord or "").strip().upper()
    value = -1 if c == "L" else 1
    try:
        pose_register.poseRegisterData.cartData.posture.arm_left_right = value
    except Exception:
        try:
            pose_register.poseRegisterData.cartData.posture.arm_left_right = "L" if value < 0 else "R"
        except Exception:
            pose_register.poseRegisterData.cartData.posture.arm_left_right = old_lr


def make_headers(register_type: str) -> List[str]:
    if register_type == "R":
        return ["type", "ID", "value"]
    if register_type == "P":
        return ["Type", "ID", "X", "Y", "Z", "A", "B", "C", "TF", "UF", "Coord"]
    if register_type == "PR":
        return ["TYPE", "ID", "X", "Y", "Z", "A", "B", "C", "coord"]
    raise ValueError("不支持的寄存器类型")


# 「读取全部」：从该 ID 起顺序尝试，连续失败达到上限则停止。
READ_ALL_FIRST_ID = 1
READ_ALL_CONSECUTIVE_FAIL_LIMIT = 10
READ_ALL_MAX_ID = 100000


def build_indexes(selector: Dict[str, Any]) -> List[int]:
    mode = selector.get("mode", "range")
    if mode == "all":
        raise RuntimeError("内部错误：「全部」模式应使用 read_*_all_scan，不应调用 build_indexes。")
    start_id = int(selector.get("startId", 0))
    end_id = int(selector.get("endId", start_id))
    if end_id < start_id:
        start_id, end_id = end_id, start_id
    return list(range(start_id, end_id + 1))


# ---------- SDK 交互 --------------------------------------------------------


def connect_arm(ip: str):
    _ensure_sdk_ready()
    log_py(f"SDK Arm.connect begin ip={ip!r}")
    with redirect_sdk_stdout_to_stderr():
        arm = Arm()
        ret = arm.connect(ip)
    if ret != StatusCodeEnum.OK:
        err = getattr(ret, "errmsg", ret)
        log_py(f"SDK Arm.connect failed: {err!r}")
        raise RuntimeError(f"连接机器人失败: {err}")
    log_py("SDK Arm.connect ok")
    return arm


def _safe_disconnect(arm: Any) -> None:
    try:
        with redirect_sdk_stdout_to_stderr():
            arm.disconnect()
    except Exception as exc:  # pragma: no cover
        log_py(f"SDK Arm.disconnect swallow: {exc!r}")


def verify_connect(ip: str) -> Dict[str, Any]:
    log_py(f"verify_connect begin ip={ip!r}")
    try:
        arm = connect_arm(ip)
    except Exception as exc:
        log_py(f"verify_connect exception: {exc!r}")
        return {"ok": False, "message": str(exc)}
    _safe_disconnect(arm)
    log_py("verify_connect disconnected")
    return {"ok": True, "message": "连接成功"}


def read_r(arm, indexes: List[int]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with redirect_sdk_stdout_to_stderr():
        for idx in indexes:
            value, ret = arm.register.read_R(idx)
            if ret == StatusCodeEnum.OK:
                rows.append({"type": "R", "ID": idx, "value": round3(value)})
    return rows


def read_pr(arm, indexes: List[int]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with redirect_sdk_stdout_to_stderr():
        for idx in indexes:
            pose, ret = arm.register.read_PR(idx)
            if ret == StatusCodeEnum.OK:
                pos = pose.poseRegisterData.cartData.position
                coord = _coord_from_pose_register(pose)
                rows.append(
                    {
                        "TYPE": "PR",
                        "ID": idx,
                        "X": round3(pos.x),
                        "Y": round3(pos.y),
                        "Z": round3(pos.z),
                        "A": round3(pos.a),
                        "B": round3(pos.b),
                        "C": round3(pos.c),
                        "coord": coord,
                    }
                )
    return rows


def read_p(arm, program_name: str, indexes: List[int]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with redirect_sdk_stdout_to_stderr():
        for idx in indexes:
            pose, ret = arm.program_pose.read(program_name, idx)
            if ret == StatusCodeEnum.OK:
                pos = pose.poseData.cartData.baseCart.position
                tf = _safe_int(getattr(pose.poseData.cartData, "tf", 0), 0)
                uf = _safe_int(getattr(pose.poseData.cartData, "uf", 0), 0)
                coord = _coord_from_pose(pose)
                rows.append(
                    {
                        "Type": "P",
                        "ID": idx,
                        "X": round3(pos.x),
                        "Y": round3(pos.y),
                        "Z": round3(pos.z),
                        "A": round3(pos.a),
                        "B": round3(pos.b),
                        "C": round3(pos.c),
                        "TF": tf,
                        "UF": uf,
                        "Coord": coord,
                    }
                )
    return rows


def read_r_all_scan(arm) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    consec_fail = 0
    idx = READ_ALL_FIRST_ID
    with redirect_sdk_stdout_to_stderr():
        while idx <= READ_ALL_MAX_ID and consec_fail < READ_ALL_CONSECUTIVE_FAIL_LIMIT:
            value, ret = arm.register.read_R(idx)
            if ret == StatusCodeEnum.OK:
                rows.append({"type": "R", "ID": idx, "value": round3(value)})
                consec_fail = 0
            else:
                consec_fail += 1
            idx += 1
    return rows


def read_pr_all_scan(arm) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    consec_fail = 0
    idx = READ_ALL_FIRST_ID
    with redirect_sdk_stdout_to_stderr():
        while idx <= READ_ALL_MAX_ID and consec_fail < READ_ALL_CONSECUTIVE_FAIL_LIMIT:
            pose, ret = arm.register.read_PR(idx)
            if ret == StatusCodeEnum.OK:
                pos = pose.poseRegisterData.cartData.position
                coord = _coord_from_pose_register(pose)
                rows.append(
                    {
                        "TYPE": "PR",
                        "ID": idx,
                        "X": round3(pos.x),
                        "Y": round3(pos.y),
                        "Z": round3(pos.z),
                        "A": round3(pos.a),
                        "B": round3(pos.b),
                        "C": round3(pos.c),
                        "coord": coord,
                    }
                )
                consec_fail = 0
            else:
                consec_fail += 1
            idx += 1
    return rows


def read_p_all_scan(arm, program_name: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    consec_fail = 0
    idx = READ_ALL_FIRST_ID
    with redirect_sdk_stdout_to_stderr():
        while idx <= READ_ALL_MAX_ID and consec_fail < READ_ALL_CONSECUTIVE_FAIL_LIMIT:
            pose, ret = arm.program_pose.read(program_name, idx)
            if ret == StatusCodeEnum.OK:
                pos = pose.poseData.cartData.baseCart.position
                tf = _safe_int(getattr(pose.poseData.cartData, "tf", 0), 0)
                uf = _safe_int(getattr(pose.poseData.cartData, "uf", 0), 0)
                coord = _coord_from_pose(pose)
                rows.append(
                    {
                        "Type": "P",
                        "ID": idx,
                        "X": round3(pos.x),
                        "Y": round3(pos.y),
                        "Z": round3(pos.z),
                        "A": round3(pos.a),
                        "B": round3(pos.b),
                        "C": round3(pos.c),
                        "TF": tf,
                        "UF": uf,
                        "Coord": coord,
                    }
                )
                consec_fail = 0
            else:
                consec_fail += 1
            idx += 1
    return rows


def read_preview(ip: str, req: Dict[str, Any]) -> Dict[str, Any]:
    reg_type = req["registerType"]
    selector = req.get("selector", {})
    mode = selector.get("mode", "range")
    log_py(
        f"read_preview begin type={reg_type!r} ip={ip!r} mode={mode!r} "
        f"program={req.get('programName')!r}"
    )
    arm = connect_arm(ip)
    try:
        if mode == "all":
            if reg_type == "R":
                rows = read_r_all_scan(arm)
            elif reg_type == "PR":
                rows = read_pr_all_scan(arm)
            elif reg_type == "P":
                program_name = req.get("programName")
                if not program_name:
                    raise RuntimeError("读取 P 点时 programName 不能为空。")
                rows = read_p_all_scan(arm, program_name)
            else:
                raise RuntimeError("不支持的寄存器类型。")
        elif reg_type == "R":
            rows = read_r(arm, build_indexes(selector))
        elif reg_type == "PR":
            rows = read_pr(arm, build_indexes(selector))
        elif reg_type == "P":
            program_name = req.get("programName")
            if not program_name:
                raise RuntimeError("读取 P 点时 programName 不能为空。")
            rows = read_p(arm, program_name, build_indexes(selector))
        else:
            raise RuntimeError("不支持的寄存器类型。")
        log_py(f"read_preview ok row_count={len(rows)}")
        return {"rows": rows}
    finally:
        _safe_disconnect(arm)
        log_py("read_preview disconnected")


def write_r(arm, row: Dict[str, Any], policy: str) -> Tuple[bool, str]:
    idx = int(row["ID"])
    value = round3(row["value"])
    with redirect_sdk_stdout_to_stderr():
        _, ret = arm.register.read_R(idx)
    exists = ret == StatusCodeEnum.OK
    if exists and policy == "skip":
        return True, "skip"
    with redirect_sdk_stdout_to_stderr():
        ret = unwrap_status(arm.register.write_R(idx, value))
    if ret != StatusCodeEnum.OK:
        return False, status_text(ret)
    return True, "write"


def build_pose_register_from_row(row: Dict[str, Any]):
    pose_register = PoseRegister()
    pose_register.id = int(row["ID"])
    pose_register.poseRegisterData.pt = PoseType.CART
    pos = pose_register.poseRegisterData.cartData.position
    pos.x = round3(row["X"])
    pos.y = round3(row["Y"])
    pos.z = round3(row["Z"])
    pos.a = round3(row["A"])
    pos.b = round3(row["B"])
    pos.c = round3(row["C"])
    coord_val = row.get("coord", row.get("coord（L/R）", "R"))
    _apply_coord_to_pose_register(pose_register, str(coord_val))
    return pose_register


def write_pr(arm, row: Dict[str, Any], policy: str) -> Tuple[bool, str]:
    idx = int(row["ID"])
    with redirect_sdk_stdout_to_stderr():
        old, ret = arm.register.read_PR(idx)
    exists = ret == StatusCodeEnum.OK
    if exists and policy == "skip":
        return True, "skip"
    if exists:
        pose_register = old
        pos = pose_register.poseRegisterData.cartData.position
        pos.x = round3(row["X"])
        pos.y = round3(row["Y"])
        pos.z = round3(row["Z"])
        pos.a = round3(row["A"])
        pos.b = round3(row["B"])
        pos.c = round3(row["C"])
        coord_val = row.get("coord", row.get("coord（L/R）", "R"))
        _apply_coord_to_pose_register(pose_register, str(coord_val))
    else:
        pose_register = build_pose_register_from_row(row)
    with redirect_sdk_stdout_to_stderr():
        ret = unwrap_status(arm.register.write_PR(pose_register))
    if ret != StatusCodeEnum.OK:
        return False, status_text(ret)
    return True, "write"


def write_p(arm, program_name: str, row: Dict[str, Any], policy: str) -> Tuple[bool, str]:
    idx = int(row["ID"])
    with redirect_sdk_stdout_to_stderr():
        pose, ret = arm.program_pose.read(program_name, idx)
    exists = ret == StatusCodeEnum.OK
    if exists and policy == "skip":
        return True, "skip"
    if exists:
        target_pose = pose
    else:
        if not hasattr(arm.program_pose, "add"):
            return False, "当前 SDK 不支持 program_pose.add，无法新增程序点。"
        if ProgramPose is None:
            return False, "未找到 ProgramPose 类型，无法新增程序点。"
        target_pose = ProgramPose()
        target_pose.id = idx
        target_pose.poseData.pt = PoseType.CART

    pos = target_pose.poseData.cartData.baseCart.position
    pos.x = round3(row["X"])
    pos.y = round3(row["Y"])
    pos.z = round3(row["Z"])
    pos.a = round3(row["A"])
    pos.b = round3(row["B"])
    pos.c = round3(row["C"])
    tf_val = row.get("TF")
    uf_val = row.get("UF")
    target_pose.poseData.cartData.tf = _safe_int(
        tf_val, _safe_int(getattr(target_pose.poseData.cartData, "tf", 0), 0)
    )
    target_pose.poseData.cartData.uf = _safe_int(
        uf_val, _safe_int(getattr(target_pose.poseData.cartData, "uf", 0), 0)
    )
    coord_val = row.get("Coord", row.get("Coord（L/R）", "R"))
    _apply_coord_to_pose(target_pose, str(coord_val))

    with redirect_sdk_stdout_to_stderr():
        if exists:
            ret = unwrap_status(arm.program_pose.write(program_name, idx, target_pose))
        else:
            ret = unwrap_status(arm.program_pose.add(program_name, idx, target_pose))
    if ret != StatusCodeEnum.OK:
        return False, status_text(ret)
    return True, "write"


def apply_rows(ip: str, req: Dict[str, Any]) -> Dict[str, Any]:
    reg_type = req["registerType"]
    policy = req.get("conflictPolicy", "skip")
    rows: List[Dict[str, Any]] = req.get("rows", [])
    log_py(
        f"apply_rows begin ip={ip!r} type={reg_type!r} policy={policy!r} row_count={len(rows)} "
        f"program={req.get('programName')!r}"
    )
    arm = connect_arm(ip)
    success = 0
    skipped = 0
    failed: List[str] = []
    try:
        for row in rows:
            if reg_type == "R":
                ok, tag = write_r(arm, row, policy)
            elif reg_type == "PR":
                ok, tag = write_pr(arm, row, policy)
            elif reg_type == "P":
                program_name = req.get("programName")
                if not program_name:
                    raise RuntimeError("写入 P 点时 programName 不能为空。")
                ok, tag = write_p(arm, program_name, row, policy)
            else:
                raise RuntimeError("不支持的寄存器类型。")

            if ok and tag == "skip":
                skipped += 1
            elif ok:
                success += 1
            else:
                failed.append(f"ID={row.get('ID')}: {tag}")
    finally:
        _safe_disconnect(arm)
        log_py("apply_rows disconnected")

    if failed:
        if (
            reg_type == "P"
            and success == 0
            and skipped == 0
            and all(("PROGRAM_NOT_FOUND" in f) or ("找不到对应的程序" in f) for f in failed)
        ):
            return {
                "ok": False,
                "message": "找不到对应程序，请检查程序名是否正确。",
                "details": [],
            }
        log_py(
            f"apply_rows end partial_fail success={success} skipped={skipped} failed={len(failed)}"
        )
        return {
            "ok": False,
            "message": f"完成：成功 {success}，跳过 {skipped}，失败 {len(failed)}。",
            "details": failed,
        }
    log_py(f"apply_rows end ok success={success} skipped={skipped}")
    return {
        "ok": True,
        "message": f"完成：成功 {success}，跳过 {skipped}，失败 0。",
        "details": [],
    }


def _cell_for_export(row: Dict[str, Any], key: str, reg_type: str) -> Any:
    if key in row:
        return row[key]
    if reg_type == "P" and key == "Coord":
        return row.get("Coord（L/R）", "")
    if reg_type == "PR" and key == "coord":
        return row.get("coord（L/R）", "")
    return row.get(key, "")


def export_excel(register_type: str, rows: List[Dict[str, Any]], output_path: str) -> Dict[str, Any]:
    if Workbook is None:
        raise RuntimeError(
            f"未安装 openpyxl：{_OPENPYXL_ERR!r}" if _OPENPYXL_ERR else "未安装 openpyxl。"
        )
    log_py(f"export_excel begin type={register_type!r} rows={len(rows)} path_len={len(output_path)}")
    headers = make_headers(register_type)
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # 超过 5000 行启用流式写入（write_only），避免整表驻留内存。
    use_write_only = len(rows) > 5000
    wb = Workbook(write_only=use_write_only)
    if use_write_only:
        ws = wb.create_sheet(title=register_type)
        ws.append(headers)
        for row in rows:
            record = [_cell_for_export(row, key, register_type) for key in headers]
            record = [round3(v) if isinstance(v, (int, float)) else v for v in record]
            ws.append(record)
    else:
        ws = wb.active
        ws.title = register_type
        ws.append(headers)
        for row in rows:
            record = [_cell_for_export(row, key, register_type) for key in headers]
            record = [round3(v) if isinstance(v, (int, float)) else v for v in record]
            ws.append(record)

    wb.save(output_file)
    log_py(f"export_excel ok path={output_file} write_only={use_write_only}")
    return {"ok": True, "message": f"已保存到 {output_file}"}


def fetch_robot_meta(ip: str) -> Dict[str, Any]:
    log_py(f"fetch_robot_meta begin ip={ip!r}")
    arm = connect_arm(ip)
    try:
        with redirect_sdk_stdout_to_stderr():
            model_info, ret_m = arm.get_arm_model_info()
            ver_info, ret_v = arm.get_controller_version()
        model_str = (
            str(model_info) if ret_m == StatusCodeEnum.OK and model_info is not None else ""
        )
        ver_str = str(ver_info) if ret_v == StatusCodeEnum.OK and ver_info is not None else ""
        log_py(f"fetch_robot_meta ok model_len={len(model_str)} ver_len={len(ver_str)}")
        return {"model": model_str, "controllerVersion": ver_str}
    finally:
        _safe_disconnect(arm)
        log_py("fetch_robot_meta disconnected")


def export_template(register_type: str, output_path: str) -> Dict[str, Any]:
    if Workbook is None:
        raise RuntimeError(
            f"未安装 openpyxl：{_OPENPYXL_ERR!r}" if _OPENPYXL_ERR else "未安装 openpyxl。"
        )
    log_py(f"export_template begin type={register_type!r} path_len={len(output_path)}")
    wb = Workbook()
    ws = wb.active
    ws.title = register_type
    ws.append(make_headers(register_type))
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_file)
    log_py(f"export_template ok path={output_file}")
    return {"ok": True, "message": f"模板已保存到 {output_file}"}


# ---------- 入口 ------------------------------------------------------------


def _dispatch(payload: Dict[str, Any]) -> Dict[str, Any]:
    action = payload.get("action")
    if action == "read_preview":
        return read_preview(payload["ip"], payload["request"])
    if action == "apply_rows":
        return apply_rows(payload["ip"], payload["request"])
    if action == "export_excel":
        return export_excel(
            payload["registerType"], payload.get("rows", []), payload["outputPath"]
        )
    if action == "export_template":
        return export_template(payload["registerType"], payload["outputPath"])
    if action == "fetch_robot_meta":
        return fetch_robot_meta(payload["ip"])
    if action == "verify_connect":
        return verify_connect(payload["ip"])
    raise RuntimeError(f"未知 action: {action!r}")


def main() -> int:
    try:
        payload = read_payload()
    except Exception as exc:
        log_py(f"read_payload failed: {exc!r}")
        emit_frame({"ok": False, "code": "BAD_PAYLOAD", "message": f"Sidecar 入参解析失败: {exc}"})
        return 0

    action = payload.get("action", "?")
    log_py(f"main action={action!r} keys={list(payload.keys())}")
    try:
        result = _dispatch(payload)
    except Exception as exc:
        log_py(f"main action={action!r} exception: {exc!r}\n{traceback.format_exc()}")
        emit_frame(
            {
                "ok": False,
                "code": "ACTION_FAILED",
                "message": str(exc),
            }
        )
        return 0

    if not isinstance(result, dict):
        emit_frame(
            {
                "ok": False,
                "code": "BAD_RESULT",
                "message": "Sidecar 内部错误：dispatch 返回非字典。",
            }
        )
        return 0

    log_py(f"main action={action!r} done ok_field={result.get('ok')!r}")
    emit_frame(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
