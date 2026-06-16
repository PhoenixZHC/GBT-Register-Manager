# Agilebot robot toolbox

<div align="right">

[简体中文](README.md) | [English](README_en.md)

</div>

## Overview

This desktop app is the **Agilebot** robot **toolbox**: after a successful controller connection, you can **batch-edit R, PR, and P registers** (Excel import/export, batch create) and, over **SFTP**, **export controller / teach-pendant logs by calendar date** and **export program data (`robot_data`)** from the cabinet—without manual WinSCP steps. While connecting, a **Connecting…** message stays visible until the link is up and robot header info is loaded; the header can show **controller / teach pendant IPs**, **robot model**, and the **Agilebot.Robot.SDK.A** pip version on the cabinet (via SSH, same controller credentials as SFTP in `src-tauri/src/sftp_export.rs`). A **Plugin installation** page uploads **.gbtapp** packages and **.whl** wheels to the cabinet **Extension_Service (HTTP 5615)**.

Current app version: `v1.2.8`

## Compatible SDK

Agilebot Python SDK | v2.0.1.0

## Feature list

1. **R / P / PR registers**: Numeric **R**, pose register **PR**, and program pose **P**; **P** requires the **program name** exactly as on the controller.

| Type | Meaning | Extra input |
|------|---------|-------------|
| **R** | Numeric register | — |
| **PR** | Pose register | — |
| **P** | Program pose point | **Program name** |

2. **Batch create**: Create registers of the selected type in a contiguous range by **start ID** and **count**; **P** requires a program name and is subject to **Limitations** below.

3. **Register data export**: Read from the robot by **ID range** or **All**, preview in a table, and **export to Excel**. **All** reads sequentially from register **ID 1**; when **10 consecutive** reads fail, scanning stops and all successfully read records so far are returned (suited to data that is contiguous from ID 1).

4. **Register data import**: **Import Excel**, preview, then **write to the robot**; if target IDs already exist, choose **overwrite**, **skip existing**, or **cancel**. **Export template** (headers only) is supported for offline editing.

5. **Logs / programs & data export** (requires a **real** connection—not the debug bypass IP):
   - **Export controller logs**: For the selected calendar date, collect pure timestamp files `YYYYMMDDHHmmss.log` under `/root/log`, and service `.log` files whose names contain the selected date under `/root/app_log`, then ZIP them together. Shows **total file count** and **live progress** (scan → download → ZIP).
   - **Export teach pendant logs**: For the selected calendar date, collect service `.log` files whose names contain the selected date under the pendant’s `/root/app_log` (requires **teach pendant IP** saved at connect time), with the same progress UI.
   - **Export program data**: Recursively download `/root/robot_data` from the cabinet to a ZIP (date-independent); remote files are counted first, then downloaded and zipped with step-by-step progress.  
   SFTP credentials are set in `src-tauri/src/sftp_export.rs` (controller and pendant passwords).

6. **Languages**: Use the header switcher for **中文**, **English**, **日本語**, **한국어**, **Русский**.

7. **Connection & header**: After **Connect**, a **Connecting…** message stays until the session is ready and model / SDK metadata is fetched. The header shows **controller IP**, **teach pendant IP** when provided at connect time, **model**, and the **`Agilebot.Robot.SDK.A`** **public** version (SSH: `cd /opt/python3.12/bin && ./pip3.12 list`; if the full version is `2.0.1.0+0998ac28…`, the UI shows **`2.0.1.0`** only—the part before **`+`**). For GBT-P/C/S with a teach pendant IP, the read targets the pendant. Requires TCP **22** to the host; credentials in `sftp_export.rs`. If SSH or pip fails, the SDK line may show **—** without blocking register operations.

8. **Plugin installation** (requires a **real** connection—not the debug bypass IP): Pick a local **.gbtapp** or **.whl** and upload to the cabinet **Extension_Service** (default **HTTP 5615**). This PC must reach that port; not available in debug mode.

## Typical workflow

1. Open the app, enter the **controller cabinet IP** (optional **teach pendant IP**), and click **Connect** (the sidecar uses the SDK **local proxy** path for reliable access to **P** registers and related service ports; **Connecting…** is shown until ready, then a success message).
2. In the left sidebar, choose **Batch create**, **Register data export**, **Register data import**, **Logs / programs & data export**, or **Plugin installation**.
3. On register pages: select **R**, **P**, or **PR** first; for **P**, enter the **program name** wherever required.
4. **Register table export only**: set a range or **All** → **Read from robot** → check the table → **Export to Excel** if needed.
5. **Write from sheet**: **Import Excel** (or edit after read) → **Write to robot** → resolve conflicts if prompted.
6. **Logs / programs & data**: On **Logs / programs & data export**, pick the date (for log exports) → click the desired button → choose the ZIP path in the save dialog.
7. **Plugin installation**: On **Plugin installation**, pick a local **.gbtapp** or **.whl** → run the matching **Install** action (this PC must reach cabinet **5615**).
8. When finished, click **Disconnect** in the header.

## Excel layout

- Use the **first worksheet**; **row 1** = headers, **from row 2** = data.
- Prefer **Export template** in the app to avoid header mistakes.

**R** headers: `type`, `ID`, `value`  

**P** headers: `Type`, `ID`, `X`, `Y`, `Z`, `A`, `B`, `C`, `TF`, `UF`, `Coord`  

**PR** headers: `TYPE`, `ID`, `X`, `Y`, `Z`, `A`, `B`, `C`, `coord`  

## Limitations (read before production use)

- **“Read all”:** There is no small fixed ID window. Scanning starts at **ID 1** in order; each failed read adds to a **consecutive failure** count (a successful read resets it). After **10 consecutive failures**, scanning stops and only earlier successful reads are kept. If register IDs are **not contiguous** and there are large gaps, the result may stop before the real maximum ID—use a **custom range** instead. To avoid overly long scans, the implementation also stops at an **ID ceiling of 100000**.

- **`/root/app_log` date matching:** The selected calendar day is matched as an `YYYYMMDD` token inside the filename. The token must not be immediately adjacent to other digits on both sides, to avoid false positives (e.g. `service_202605111.log` is not treated as May 11).

## Development & testing

- **On-hardware verification:** Validated on a real controller / teach-pendant setup (register read/write and batch flows, Excel import/export, date-based log and `robot_data` export, `.gbtapp` / `.whl` plugin install).
- From **`src-tauri`**, run: `cargo test -p gbt-register-manager sftp_export --lib` to re-check SFTP log filename rules for controller **`/root/log`** (pure timestamp) vs **`/root/app_log`** (service logs containing the date).

## Building the Python sidecar

- See **[BUILD.md](BUILD.md)** at the repo root. Release builds require `npm run sidecar:build` to produce `gbt-bridge-<target>.exe`.
- The Agilebot SDK **wheel path in `python-sidecar/requirements.txt` is relative to the repository root** (`build_sidecar.ps1` runs `pip install -r python-sidecar/requirements.txt` from the root). Place the matching **`.whl`** under **`Python_v2.0.1.0/`** in the repo as named in `requirements.txt`, or edit that line for your environment.

## Changelog

### V1.2.8 (2026-06-16)

- Version bumped to **1.2.8**.
- **Build optimization:** Tauri dependencies slimmed to the `wry` core feature; DevTools moved to the Cargo `devtools` feature. `npm run tauri:dev` and `npm run tauri:build` explicitly pass `--features devtools`, keeping F12 / Ctrl+Shift+I debugging while reducing the default dependency surface.
- **Installer metadata:** MSI/NSIS shortDescription, longDescription, and copyright unified in English as **Agilebot robot toolbox**, matching the window title and product positioning.

### V1.2.7 (2026-06-16)

- Version bumped to **1.2.7**.
- **Export progress UX:** Controller logs, teach-pendant logs, and program data (`robot_data`) export now show staged progress—**Preparing export, scanning files…** → **Scan complete: N file(s) to export** → **Exporting i/N; exported j** → **Creating ZIP**—then a completion toast with the exported count. The progress toast updates in place and transitions smoothly to success/failure.
- **Scan-then-download:** SFTP export scans all matching remote files first for an accurate total, then downloads file by file with live progress, so the denominator stays consistent with what is actually exported.
- **i18n:** Export progress strings updated across Chinese, English, Japanese, Korean, and Russian.

### V1.2.6 (2026-06-16)

- Version bumped to **1.2.6**.
- **Fix: backend Chinese errors shown raw in the UI** — Rust, Python sidecar, and SFTP now return `GBT_*` codes; the UI maps them to the selected language instead of showing backend Chinese or tracebacks.
- **Fix: progress events not scoped to session** — `register-progress` events carry and validate `sessionId` and `opId`; stale progress after disconnect/reconnect or op switch no longer updates the current UI.
- **Fix: no mutex on concurrent connect / register I/O** — Connect, disconnect, register read/write, and SFTP export are serialized (`robot_op` lock); concurrent ops show “another operation in progress”.
- **Fix: connect button double-click** — `connectBusy` ignores repeat clicks while a connect is in flight.
- **Fix: no progress during conflict-check `readRegisters`** — Import and batch-create conflict scans now show read progress like the main read/write flow.
- **Fix: `applyResultMessage` used success template on failure** — When `!res.ok`, the UI shows the error code or `applyFailed` summary instead of a success-style “N rows done” message.
- **Fix: non-atomic export pre-count vs download** — Log and `robot_data` export enumerate-and-download in one pass (total grows as files download), replacing a separate full count phase that could disagree with what was actually downloaded.

### V1.2.5 (2026-06-15)

- Version bumped to **1.2.5**.
- **i18n fix:** Restored full Japanese, Korean, and Russian UI and dialog strings (including 1.2.4 `response` / `progress` keys); switching language no longer falls back to English for most of the app.
- **Read/write progress fix:** Register read/write progress now updates incrementally (`current/total`) instead of staying on “Reading…” / “Writing…” until the operation completes.
- **Log & program-data export progress:** Controller logs, teach-pendant logs, and `robot_data` export now count matching remote files first, then show live download and ZIP progress.

### V1.2.4 (2026-06-15)

- Version bumped to **1.2.4**.
- **Localized messages:** Expected operation results such as register write, batch create, export, disconnect, and wheel install now render in the selected UI language instead of showing backend Chinese text directly.
- **Read/write progress:** Register read and write operations now keep a live progress message visible until the operation finishes or fails.
### V1.2.2 (2026-05-13)

- Version bumped to **1.2.2**.
- **On-hardware testing:** Passed on a real cabinet (connect + header info, registers, logs / program-data export, plugin install).

### V1.2.1 (2026-05-13)

- **SDK version:** Run `./pip3.12 list` under `/opt/python3.12/bin` over SSH and parse **`Agilebot.Robot.SDK.A`**; the header shows the **public** segment only (strip **`+`** and the local suffix).

### V1.2.0 (2026-05-12)

- Version bumped to **1.2.0**.
- **Connection UX:** **Connecting…** stays visible until the link is ready and model / SDK metadata is loaded, then a success toast.
- **Header:** Controller IP, optional teach pendant IP, model; **Python SDK** version over SSH (no legacy controller “software” line in the header).
- **Plugin installation:** New **Plugin installation** sidebar entry; upload **.gbtapp** and **.whl** to cabinet Extension_Service (**HTTP 5615**).
- **Build:** Fixed SDK wheel path in `python-sidecar/requirements.txt` to be relative to the **repo root** so `pip` run from the root no longer resolves `../` to the drive root. See [BUILD.md](BUILD.md).

### V1.1.1 (2026-05-11)

- Version bumped to **1.1.1**.
- **Docs:** Feature list now matches SFTP log filtering (`/root/log` vs `/root/app_log`); added development & testing notes.
- **Automated tests:** `cargo test -p gbt-register-manager sftp_export --lib` passed (log filename matching).

### V1.1.0 (2026-05-11)

- Version bumped to **1.1.0**.
- **UI & docs:** Sidebar and register pages use **Register data export / Register data import**; the SFTP area is **Logs / programs & data export**; the log export screen no longer shows the filename-pattern hint; README and BUILD notes updated.
- **Logs and program-data export:** Controller `/root/log` keeps the pure timestamp filename rule; controller / teach-pendant `/root/app_log` supports service-name-plus-date filenames; program data is exported from `/root/robot_data`.
- **Windows builds:** `ssh2` no longer uses `vendored-openssl` (no Perl / OpenSSL-from-source); libssh2 uses **WinCNG** on MSVC.

### V1.0.2 (2026-04-23)

- Product renamed to **捷勃特机器人工具箱** / **Agilebot robot toolbox** (installer and window titles updated).
- **Logs / data export:** After connect, ZIP export for controller and pendant logs by date, and full `robot_data` export from the cabinet (SFTP; see feature list).
- Version bumped to **V1.0.2**.

### V1.0.1 (2026-04-23)

- **Connection:** Separate **controller cabinet IP** and optional **teach pendant IP**; the Python sidecar talks to the controller through the SDK **local proxy** (`local_proxy`) for stable **P** register access (service ports such as **5606**).
- **Fix:** For **PR / P**, if the SDK `Posture` object was not initialized, **coord** and related fields could be **silently dropped** when writing or applying coordinates—the sidecar now initializes pose objects before assignment.
- **Build & release:** Windows bundles ship as **MSI** and **NSIS**; post-build rename script for installers; **publisher** set to **Agilebot**.
- **UI:** Avoided **vue-i18n** reserved interpolation tokens (e.g. progress strings use `{total}`).

### V1.0.0 (2026-04-22)

- First release: IP connect, robot model and controller version display, **R / P / PR** read/write, batch create, Excel import/export and blank templates, write conflict handling (overwrite / skip / cancel), multi-language UI.

- **Read all:** scans from **ID 1** in order and stops after **10 consecutive** read failures, returning all successful reads so far (no longer a fixed 0–199 window).

---
