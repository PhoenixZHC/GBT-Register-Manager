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
import socket
import sys
import tempfile
import traceback
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Set, Tuple

# ---------- 环境准备 --------------------------------------------------------

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", newline="")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", newline="")
# 协议帧走原始 fd 直写，避免子进程管道全缓冲导致进度事件批量到达前端。
_PROTOCOL_FD = sys.stdout.fileno()

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
    from Agilebot import (
        Arm,
        PoseRegister,
        PoseType,
        Posture,
        ProgramPose,
        StatusCodeEnum,
    )
except Exception as _sdk_err:  # pragma: no cover
    Arm = None  # type: ignore[assignment]
    PoseRegister = None  # type: ignore[assignment]
    PoseType = None  # type: ignore[assignment]
    Posture = None  # type: ignore[assignment]
    ProgramPose = None  # type: ignore[assignment]
    StatusCodeEnum = None  # type: ignore[assignment]
    _SDK_IMPORT_ERR: Exception | None = _sdk_err
else:
    _SDK_IMPORT_ERR = None


def _ensure_sdk_ready() -> None:
    if Arm is None or StatusCodeEnum is None:
        if _SDK_IMPORT_ERR is not None:
            log_py(f"SDK import failed: {_SDK_IMPORT_ERR!r}")
        gbt_raise("GBT_SDK_NOT_FOUND")


# ---------- 协议辅助 --------------------------------------------------------

FRAME_BEGIN = "<<<GBT-BEGIN>>>"
FRAME_END = "<<<GBT-END>>>"


def gbt_raise(code: str) -> None:
    """抛出仅含 `GBT_*` 错误码的异常，供 main() 写入 sidecar 帧。"""
    raise RuntimeError(code)


def sidecar_error_code(exc: BaseException) -> str:
    msg = str(exc).strip()
    if msg.startswith("GBT_") and " " not in msg:
        return msg
    return "GBT_INTERNAL_ERROR"


def emit_frame(data: Dict[str, Any]) -> None:
    """写出被分隔符包裹的单帧 JSON（UTF-8，不转义非 ASCII）。"""
    text = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    chunk = f"{FRAME_BEGIN}\n{text}\n{FRAME_END}\n".encode("utf-8")
    os.write(_PROTOCOL_FD, chunk)


ProgressCallback = Callable[[int, Optional[int], int], None]


def emit_progress(action: str, current: int, total: Optional[int], matched: int) -> None:
    emit_frame(
        {
            "kind": "progress",
            "action": action,
            "current": current,
            "total": total,
            "matched": matched,
        }
    )


def read_payload() -> Dict[str, Any]:
    """从 stdin 读取 UTF-8 JSON 载荷（Rust 端写完后 close stdin）。"""
    raw = sys.stdin.read()
    if not raw:
        raise RuntimeError("GBT_INTERNAL_ERROR")
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
        raise ValueError("Non-finite numeric value")
    return round(x, 3)


def unwrap_status(ret: Any) -> Any:
    if isinstance(ret, tuple) and len(ret) >= 2:
        return ret[-1]
    return ret


def status_text(ret: Any) -> str:
    st = unwrap_status(ret)
    return getattr(st, "errmsg", str(st))


def status_indicates_exists(ret: Any) -> bool:
    st = unwrap_status(ret)
    raw = " ".join(
        str(x)
        for x in (
            getattr(st, "name", ""),
            getattr(st, "value", ""),
            getattr(st, "errmsg", ""),
            st,
        )
        if x is not None
    ).lower()
    return any(
        token in raw
        for token in (
            "exist",
            "exists",
            "already",
            "duplicate",
            "conflict",
            "已存在",
            "已经存在",
            "存在",
            "重複",
            "重复",
        )
    )


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


def _coord_to_left_right(coord: str) -> int:
    """Excel 里 L/R 映射到 SDK `arm_left_right`：L → -1，R/其他 → 1。"""
    c = str(coord or "").strip().upper()
    return -1 if c == "L" else 1


def _new_posture(coord: str) -> Any:
    """按 SDK PR/P 示例构造 Posture：显式 new 一个实例并写入需要的字段。

    避免对未初始化 posture 做属性链赋值造成的 "静默丢失"。
    对 SDK 未显式给默认值的 `arm_back_front` 一并补成 1（示例取值），
    保证机器人侧拿到可用的完整姿态。
    """
    if Posture is None:
        return None
    posture = Posture()
    try:
        posture.arm_left_right = _coord_to_left_right(coord)
    except Exception:
        pass
    try:
        # 与 PR.py 示例保持一致；若 SDK 对该字段有其它取值也不会抛异常。
        posture.arm_back_front = 1
    except Exception:
        pass
    return posture


def _apply_coord_to_pose(pose: Any, coord: str) -> None:
    """把 Excel 里的 coord (L/R) 写到 P 点的 `baseCart.posture.arm_left_right`。

    如果 `posture` 字段本身为空/不可写，则 new 一个 Posture 挂上去，
    避免静默丢失（见 SDK program_pose.py 和 PR.py 示例）。
    """
    value = _coord_to_left_right(coord)
    cart_data = pose.poseData.cartData.baseCart
    try:
        cart_data.posture.arm_left_right = value
        return
    except Exception:
        pass
    try:
        cart_data.posture = _new_posture(coord)
    except Exception:
        log_py("_apply_coord_to_pose 无法设置 posture，保留 SDK 默认值")


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
    """把 Excel 里的 coord (L/R) 写到 PR 寄存器 `cartData.posture.arm_left_right`。

    PR.py 示例明确要求：新建 PoseRegister 后需 new 一个 Posture 再挂到
    `poseRegisterData.cartData.posture`，否则属性链写入会静默丢失。
    """
    value = _coord_to_left_right(coord)
    cart_data = pose_register.poseRegisterData.cartData
    try:
        cart_data.posture.arm_left_right = value
        return
    except Exception:
        pass
    try:
        cart_data.posture = _new_posture(coord)
    except Exception:
        log_py("_apply_coord_to_pose_register 无法设置 posture，保留 SDK 默认值")


def make_headers(register_type: str) -> List[str]:
    if register_type == "R":
        return ["type", "ID", "value"]
    if register_type == "P":
        prefix = ["Type", "ID", "PoseType"]
    if register_type == "PR":
        prefix = ["TYPE", "ID", "PoseType"]
    if register_type not in ("P", "PR"):
        raise ValueError("GBT_UNSUPPORTED_REGISTER_TYPE")
    return (prefix + list("XYZABC") + [f"J{i}" for i in range(1, 10)]
            + (["TF", "UF", "Coord"] if register_type == "P" else ["coord"])
            + ["WristFlip", "ArmUpDown", "ArmBackFront"]
            + [f"Turn{i}" for i in range(1, 10)] + ["Name", "Comment"])


# P 寄存器（程序位姿）服务的 HTTP 端口，与 R/PR 所用端口不同。
P_SERVICE_PORT = 5606

# 兼容旧版「全部」扫描：连续空编号达到上限才停止，通信错误仍中止。
READ_ALL_FIRST_ID = 1
READ_ALL_CONSECUTIVE_FAIL_LIMIT = 10
READ_ALL_MAX_ID = 100000


def _normalize_id(value: Any) -> Optional[int]:
    try:
        idx = int(value)
    except Exception:
        return None
    if idx < READ_ALL_FIRST_ID or idx > READ_ALL_MAX_ID:
        return None
    return idx


def valid_integer(value, minimum=0, maximum=100000):
    if isinstance(value, bool) or value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError("Invalid integer")
    number = float(value)
    if not math.isfinite(number) or not number.is_integer() or not minimum <= number <= maximum:
        raise ValueError("Integer out of range")
    return int(number)


def validate_rows(reg_type, rows, policy):
    if reg_type not in ("R", "PR", "P") or policy not in ("skip", "overwrite"):
        raise ValueError("Invalid register type or policy")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 50000:
        raise ValueError("Invalid row count")
    seen = set()
    output = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid row")
        item = dict(row)
        idx = valid_integer(row.get("ID"))
        if idx in seen:
            raise ValueError("Duplicate ID")
        seen.add(idx)
        item["ID"] = idx
        kind = row_pose_type(row) if reg_type != "R" else ""
        keys = (["value"] if reg_type == "R" else
                ([f"J{i}" for i in range(1, 10)] if kind == "JOINT" else list("XYZABC")))
        for key in keys:
            value = row.get(key)
            if value is None or isinstance(value, bool) or (isinstance(value, str) and not value.strip()):
                raise ValueError("Missing numeric value")
            item[key] = round3(value) if reg_type == "R" else finite_pose_number(value)
        if reg_type != "R":
            key = "Coord" if reg_type == "P" else "coord"
            coord = str(row.get(key, row.get(key + "（L/R）", ""))).strip().upper()
            if coord not in (("L", "R", "U") if "PoseType" in row else ("L", "R")):
                raise ValueError("Invalid L/R posture")
            item[key] = coord
            if "PoseType" in row:
                item["PoseType"] = kind
                inactive = list("XYZABC") if kind == "JOINT" else [f"J{i}" for i in range(1, 10)]
                if any(row.get(k) is not None and str(row[k]).strip() for k in inactive):
                    raise ValueError("Inactive coordinates must be blank")
                for key in ("WristFlip", "ArmUpDown", "ArmBackFront"):
                    item[key] = valid_integer(row.get(key), -1, 1)
                for i in range(1, 10):
                    item[f"Turn{i}"] = valid_integer(row.get(f"Turn{i}"), -2147483648, 2147483647)
                for key in ("Name", "Comment"):
                    if row.get(key) is not None and not isinstance(row[key], str):
                        raise ValueError("Invalid point text")
                    item[key] = row.get(key) or ""
        if reg_type == "P":
            for key in ("TF", "UF"):
                item[key] = valid_integer(row.get(key))
        output.append(item)
    return output


def is_missing_register(ret, controller_register=False):
    # 通用 SDK 不存在状态，以及实机 R/PR 读取未分配编号的精确业务码。
    # 不能只匹配 -254 或 INVALID_ARG：其他控制柜错误必须继续报错。
    missing = getattr(StatusCodeEnum, "NOT_FOUND", None)
    if missing is not None and ret == missing:
        return True
    detail = getattr(ret, "errmsg", None)
    return (controller_register
            and getattr(ret, "name", None) == "REG_MANAGER_INVALID_ARG"
            and isinstance(detail, dict)
            and detail.get("name") == "REG_MANAGER_INVALID_ARG"
            and detail.get("inner_code") == "0001000200A40007")


def ensure_read_status(ret, program_pose=False):
    if program_pose and ret == StatusCodeEnum.PROGRAM_NOT_FOUND:
        gbt_raise("GBT_PROGRAM_NOT_FOUND")
    missing = getattr(StatusCodeEnum, "PROGRAM_POSE_NOT_FOUND", None) if program_pose else None
    if ret != StatusCodeEnum.OK and not is_missing_register(ret, controller_register=not program_pose) and not (missing is not None and ret == missing):
        log_py(f"Register read failed: {status_text(ret)}")
        gbt_raise("GBT_REGISTER_READ_FAILED")


def build_indexes(selector: Dict[str, Any]) -> List[int]:
    if selector.get("mode", "range") != "range":
        gbt_raise("GBT_RANGE_REQUIRED")
    try:
        start_id = valid_integer(selector.get("startId"))
        end_id = valid_integer(selector.get("endId"))
        if end_id < start_id or end_id - start_id >= 10000:
            raise ValueError("Invalid range")
    except (ValueError, TypeError, OverflowError):
        gbt_raise("GBT_INVALID_REGISTER_DATA")
    return list(range(start_id, end_id + 1))


# ---------- SDK 交互 --------------------------------------------------------


def _extract_connect_params(payload: Dict[str, Any]) -> Dict[str, Any]:
    """从 payload 中抽取连接参数，兼容新旧调用。"""
    controller_ip = (
        payload.get("controllerIp")
        or payload.get("ip")
        or ""
    )
    teach_panel_ip = payload.get("teachPanelIp") or None
    if isinstance(teach_panel_ip, str) and not teach_panel_ip.strip():
        teach_panel_ip = None
    local_proxy = bool(payload.get("localProxy", False))
    return {
        "controller_ip": controller_ip,
        "teach_panel_ip": teach_panel_ip,
        "local_proxy": local_proxy,
    }


def connect_arm(controller_ip: str, teach_panel_ip: Any = None, local_proxy: bool = False):
    """连接机器人（SDK 4.1.1）。

    - controller_ip: 控制柜 IP（必填）
    - teach_panel_ip: 示教器 IP（可选，仅工业机器人常用；协作/四轴可不填）
    - local_proxy: 是否在本机启动代理服务。机器人软件 < v7.7 或无示教器时必须 True。
    """
    _ensure_sdk_ready()
    log_py(
        f"SDK Arm.connect begin controller_ip={controller_ip!r} "
        f"teach_panel_ip={teach_panel_ip!r} local_proxy={local_proxy!r}"
    )
    with redirect_sdk_stdout_to_stderr():
        try:
            arm = Arm(local_proxy=local_proxy)
        except TypeError:
            if local_proxy:
                log_py("Arm(local_proxy=...) 不受当前 SDK 版本支持，回退 Arm()")
            arm = Arm()
        if teach_panel_ip:
            ret = arm.connect(controller_ip, teach_panel_ip)
        else:
            ret = arm.connect(controller_ip)
    if ret != StatusCodeEnum.OK:
        err = getattr(ret, "errmsg", ret)
        log_py(f"SDK Arm.connect failed: {err!r}")
        gbt_raise("GBT_CONNECT_FAILED")
    log_py("SDK Arm.connect ok")
    return arm


def _check_p_service(ip: str) -> None:
    """检查 P 寄存器服务（program_pose HTTP API）端口是否可达。

    P 寄存器使用独立的 HTTP 服务（端口 {P_SERVICE_PORT}），与 R/PR 寄存器所用通道不同。
    若端口不可达，提前报出友好错误，而非让 SDK 抛出晦涩的 HTTPConnectionPool 异常。
    """
    log_py(f"_check_p_service begin ip={ip!r} port={P_SERVICE_PORT}")
    try:
        sock = socket.create_connection((ip, P_SERVICE_PORT), timeout=3.0)
        sock.close()
        log_py(f"_check_p_service ok ip={ip!r} port={P_SERVICE_PORT}")
    except OSError as exc:
        log_py(f"_check_p_service failed ip={ip!r} port={P_SERVICE_PORT} exc={exc!r}")
        gbt_raise("GBT_P_SERVICE_UNREACHABLE")


def _safe_disconnect(arm: Any) -> None:
    try:
        with redirect_sdk_stdout_to_stderr():
            arm.disconnect()
    except Exception as exc:  # pragma: no cover
        log_py(f"SDK Arm.disconnect swallow: {exc!r}")


def verify_connect(conn: Dict[str, Any]) -> Dict[str, Any]:
    log_py(
        f"verify_connect begin controller_ip={conn['controller_ip']!r} "
        f"teach_panel_ip={conn['teach_panel_ip']!r} local_proxy={conn['local_proxy']!r}"
    )
    try:
        arm = connect_arm(**conn)
    except Exception as exc:
        log_py(f"verify_connect exception: {exc!r}")
        return {"ok": False, "code": "GBT_CONNECT_FAILED", "message": str(exc)}
    _safe_disconnect(arm)
    log_py("verify_connect disconnected")
    return {"ok": True, "code": "connect_ok"}


def read_r(arm, indexes: List[int], progress: Optional[ProgressCallback] = None) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with redirect_sdk_stdout_to_stderr():
        for pos, idx in enumerate(indexes, start=1):
            # 先上报“正在读取第 pos 条”，再实际读取；matched 为此前已匹配条数。
            if progress:
                progress(pos, len(indexes), len(rows))
            value, ret = arm.register.read_R(idx)
            ensure_read_status(ret)
            if ret == StatusCodeEnum.OK:
                rows.append({"type": "R", "ID": idx, "value": round3(value)})
    return rows


def ensure_supported_pose(data: Any) -> None:
    if getattr(data, "pt", None) not in (PoseType.CART, PoseType.JOINT):
        gbt_raise("GBT_UNSUPPORTED_POSE_TYPE")


def finite_pose_number(value: Any) -> float:
    if value is None or isinstance(value, bool) or (isinstance(value, str) and not value.strip()):
        raise ValueError("Missing pose value")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Non-finite pose value")
    return number


def row_pose_type(row: Dict[str, Any]) -> str:
    # 仅真正缺少列的旧表格默认 CART，新格式的空类型不作猜测。
    kind = str(row.get("PoseType", "CART")).strip().upper()
    if kind not in ("CART", "JOINT"):
        raise ValueError("Unknown pose type")
    return kind


def pose_to_row(pose: Any, reg_type: str, idx: int) -> Dict[str, Any]:
    data = pose.poseData if reg_type == "P" else pose.poseRegisterData
    ensure_supported_pose(data)
    cart = data.cartData.baseCart if reg_type == "P" else data.cartData
    kind = "JOINT" if data.pt == PoseType.JOINT else "CART"
    row = {key: None for key in make_headers(reg_type)}
    row.update({"Type" if reg_type == "P" else "TYPE": reg_type, "ID": idx, "PoseType": kind,
                "Name": pose.name, "Comment": pose.comment})
    if kind == "JOINT":
        for i in range(1, 10):
            row[f"J{i}"] = finite_pose_number(getattr(data.joint, f"j{i}"))
    else:
        for key in "XYZABC":
            row[key] = finite_pose_number(getattr(cart.position, key.lower()))
    posture = cart.posture
    lr = valid_integer(posture.arm_left_right, -1, 1)
    row["Coord" if reg_type == "P" else "coord"] = {-1: "L", 0: "U", 1: "R"}[lr]
    for key, attr in (("WristFlip", "wrist_flip"), ("ArmUpDown", "arm_up_down"), ("ArmBackFront", "arm_back_front")):
        row[key] = valid_integer(getattr(posture, attr), -1, 1)
    if len(posture.turn_cycle) != 9:
        raise ValueError("Invalid turn cycle length")
    for i, value in enumerate(posture.turn_cycle, 1):
        row[f"Turn{i}"] = valid_integer(value, -2147483648, 2147483647)
    if reg_type == "P":
        row.update(TF=valid_integer(data.cartData.tf), UF=valid_integer(data.cartData.uf))
    return row


def apply_pose_row(pose: Any, row: Dict[str, Any], reg_type: str) -> None:
    # 显式设置目标类型；这是写入用户指定的点数据，不进行运动学坐标转换。
    data = pose.poseData if reg_type == "P" else pose.poseRegisterData
    cart = data.cartData.baseCart if reg_type == "P" else data.cartData
    kind = row_pose_type(row)
    data.pt = PoseType.JOINT if kind == "JOINT" else PoseType.CART
    if kind == "JOINT":
        for i in range(1, 10):
            setattr(data.joint, f"j{i}", finite_pose_number(row[f"J{i}"]))
    else:
        for key in "XYZABC":
            setattr(cart.position, key.lower(), finite_pose_number(row[key]))
    if cart.posture is None:
        cart.posture = Posture()
    coord_key = "Coord" if reg_type == "P" else "coord"
    coord = str(row.get(coord_key, row.get(coord_key + "（L/R）", "R"))).strip().upper()
    cart.posture.arm_left_right = {"L": -1, "U": 0, "R": 1}[coord]
    if "PoseType" in row:
        for key, attr in (("WristFlip", "wrist_flip"), ("ArmUpDown", "arm_up_down"), ("ArmBackFront", "arm_back_front")):
            setattr(cart.posture, attr, int(row[key]))
        cart.posture.turn_cycle = [int(row[f"Turn{i}"]) for i in range(1, 10)]
        pose.name, pose.comment = row.get("Name") or "", row.get("Comment") or ""
    if reg_type == "P":
        data.cartData.tf, data.cartData.uf = int(row["TF"]), int(row["UF"])


def checked_pose_row(pose: Any, reg_type: str, idx: int) -> Dict[str, Any]:
    try:
        return pose_to_row(pose, reg_type, idx)
    except RuntimeError:
        raise
    except Exception as exc:
        log_py(f"malformed {reg_type} id={idx}: {exc!r}")
        gbt_raise("GBT_REGISTER_READ_FAILED")


def read_pr(arm, indexes: List[int], progress: Optional[ProgressCallback] = None) -> List[Dict[str, Any]]:
    rows = []
    with redirect_sdk_stdout_to_stderr():
        for step, idx in enumerate(indexes, start=1):
            if progress:
                progress(step, len(indexes), len(rows))
            try:
                pose, ret = arm.register.read_PR(idx)
            except Exception as exc:
                log_py(f"read_pr failed id={idx} exc={exc!r}")
                gbt_raise("GBT_REGISTER_READ_FAILED")
            ensure_read_status(ret)
            if ret == StatusCodeEnum.OK:
                rows.append(checked_pose_row(pose, "PR", idx))
    return rows


def read_p(arm, program_name: str, indexes: List[int], progress: Optional[ProgressCallback] = None) -> List[Dict[str, Any]]:
    rows = []
    with redirect_sdk_stdout_to_stderr():
        for step, idx in enumerate(indexes, start=1):
            if progress:
                progress(step, len(indexes), len(rows))
            try:
                pose, ret = arm.program_pose.read(program_name, idx)
            except Exception as exc:
                log_py(f"read_p failed program={program_name!r} id={idx} exc={exc!r}")
                gbt_raise("GBT_REGISTER_READ_FAILED")
            ensure_read_status(ret, program_pose=True)
            if ret == StatusCodeEnum.OK:
                rows.append(checked_pose_row(pose, "P", idx))
    return rows


def read_registers_all_scan(arm, reg_type: str, progress: Optional[ProgressCallback] = None) -> List[Dict[str, Any]]:
    """恢复 R/PR 旧版扫描规则；不能保证覆盖长空档之后的记录。"""
    reader = read_r if reg_type == "R" else read_pr
    rows: List[Dict[str, Any]] = []
    consecutive_empty = 0
    for idx in range(READ_ALL_FIRST_ID, READ_ALL_MAX_ID + 1):
        found = reader(arm, [idx])
        rows.extend(found)
        consecutive_empty = 0 if found else consecutive_empty + 1
        if progress:
            progress(idx, None, len(rows))
        if consecutive_empty >= READ_ALL_CONSECUTIVE_FAIL_LIMIT:
            break
    return rows


def read_p_pose_map(
    arm,
    program_name: str,
    id_filter: Optional[Set[int]] = None,
    strict: bool = True,
) -> Dict[int, Any]:
    """Read all program poses and index them by valid pose.id."""
    with redirect_sdk_stdout_to_stderr():
        poses, ret = arm.program_pose.read_all_poses(program_name)
    if ret == StatusCodeEnum.PROGRAM_NOT_FOUND:
        gbt_raise("GBT_PROGRAM_NOT_FOUND")
    if ret != StatusCodeEnum.OK:
        log_py(f"read_p_pose_map failed program={program_name!r}: {status_text(ret)}")
        if not strict:
            raise RuntimeError(status_text(ret))
        gbt_raise("GBT_INTERNAL_ERROR")
    out: Dict[int, Any] = {}
    for pose in poses:
        idx = _normalize_id(getattr(pose, "id", None))
        if idx is None:
            log_py(f"read_p_pose_map skip invalid pose id={getattr(pose, 'id', '?')!r}")
            continue
        if id_filter is not None and idx not in id_filter:
            continue
        out[idx] = pose
    return out


def read_p_all_scan(arm, program_name: str, progress: Optional[ProgressCallback] = None,
                    id_filter: Optional[Set[int]] = None) -> List[Dict[str, Any]]:
    pose_map = read_p_pose_map(arm, program_name, id_filter)
    rows = []
    for step, idx in enumerate(sorted(pose_map), start=1):
        rows.append(checked_pose_row(pose_map[idx], "P", idx))
        if progress:
            progress(step, len(pose_map), len(rows))
    return rows


def read_preview(conn: Dict[str, Any], req: Dict[str, Any]) -> Dict[str, Any]:
    reg_type = req["registerType"]
    selector = req.get("selector", {})
    mode = selector.get("mode", "range")
    if mode != "all":
        build_indexes(selector)
    program_name = req.get("programName")
    controller_ip = conn["controller_ip"]
    log_py(
        f"read_preview begin type={reg_type!r} controller_ip={controller_ip!r} "
        f"mode={mode!r} program={program_name!r}"
    )

    # P 寄存器使用独立 HTTP 端口，提前检查可达性，避免返回误导性的空列表。
    if reg_type == "P":
        if not program_name:
            gbt_raise("GBT_P_READ_NEED_PROGRAM")
        _check_p_service(controller_ip)

    arm = connect_arm(**conn)
    progress = lambda current, total, matched: emit_progress("read", current, total, matched)
    try:
        if mode == "all":
            if reg_type == "P":
                rows = read_p_all_scan(arm, program_name, progress)
            elif reg_type in ("R", "PR"):
                rows = read_registers_all_scan(arm, reg_type, progress)
            else:
                gbt_raise("GBT_UNSUPPORTED_REGISTER_TYPE")
        elif reg_type == "R":
            rows = read_r(arm, build_indexes(selector), progress)
        elif reg_type == "PR":
            rows = read_pr(arm, build_indexes(selector), progress)
        elif reg_type == "P":
            rows = read_p(arm, program_name, build_indexes(selector), progress)
        else:
            gbt_raise("GBT_UNSUPPORTED_REGISTER_TYPE")
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
    ensure_read_status(ret)
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
    apply_pose_row(pose_register, row, "PR")
    return pose_register


def ensure_pr_metadata_write(arm: Any, row: Dict[str, Any], old: Any) -> None:
    # SDK 新版 PR 数值接口不传名称/注释；不能把未发送的变更报为成功。
    if getattr(arm.register, "use_new_api", False) is True and "PoseType" in row:
        for column, attr in (("Name", "name"), ("Comment", "comment")):
            if (row.get(column) or "") != (getattr(old, attr, "") or ""):
                gbt_raise("GBT_POSE_METADATA_UNSUPPORTED")


def write_pr(arm, row: Dict[str, Any], policy: str) -> Tuple[bool, str]:
    idx = int(row["ID"])
    with redirect_sdk_stdout_to_stderr():
        old, ret = arm.register.read_PR(idx)
    ensure_read_status(ret)
    exists = ret == StatusCodeEnum.OK
    if exists and policy == "skip":
        return True, "skip"
    ensure_pr_metadata_write(arm, row, old if exists else None)
    if exists:
        pose_register = old
        ensure_supported_pose(getattr(pose_register, "poseRegisterData", None))
        apply_pose_row(pose_register, row, "PR")
    else:
        pose_register = build_pose_register_from_row(row)
    with redirect_sdk_stdout_to_stderr():
        ret = unwrap_status(arm.register.write_PR(pose_register))
    if ret != StatusCodeEnum.OK:
        if status_indicates_exists(ret):
            if policy == "skip":
                return True, "skip"
            return False, "ID already exists on robot"
        return False, status_text(ret)
    return True, "write"


def write_p(arm, program_name: str, row: Dict[str, Any], policy: str) -> Tuple[bool, str]:
    idx = int(row["ID"])
    try:
        pose_map = read_p_pose_map(arm, program_name, {idx}, strict=False)
    except Exception as exc:
        log_py(f"P read before write failed id={idx}: {exc!r}")
        return False, "GBT_PROGRAM_NOT_FOUND" if str(exc) == "GBT_PROGRAM_NOT_FOUND" else "GBT_P_READ_FAILED"
    pose = pose_map.get(idx)
    exists = pose is not None
    if exists and policy == "skip":
        return True, "skip"
    if exists:
        target_pose = pose
        ensure_supported_pose(getattr(target_pose, "poseData", None))
    else:
        if not hasattr(arm.program_pose, "add"):
            return False, "当前 SDK 不支持 program_pose.add，无法新增程序点。"
        if ProgramPose is None:
            return False, "未找到 ProgramPose 类型，无法新增程序点。"
        target_pose = ProgramPose()
        target_pose.id = idx

    apply_pose_row(target_pose, row, "P")

    try:
        with redirect_sdk_stdout_to_stderr():
            if exists:
                ret = unwrap_status(arm.program_pose.write(program_name, idx, target_pose))
            else:
                ret = unwrap_status(arm.program_pose.add(program_name, idx, target_pose))
    except Exception as exc:
        log_py(f"P write result unknown id={idx}: {exc!r}")
        return False, "GBT_P_WRITE_UNKNOWN"
    if ret != StatusCodeEnum.OK:
        if getattr(ret, "name", "") in ("CONNECTION_TIMEOUT", "WRITE_PROGRAM_POSE_FAILED"):
            log_py(f"P write result unknown id={idx}: {status_text(ret)}")
            return False, "GBT_P_WRITE_UNKNOWN"
        return False, status_text(ret)
    return True, "write"


def apply_rows(conn: Dict[str, Any], req: Dict[str, Any]) -> Dict[str, Any]:
    reg_type = req["registerType"]
    policy = req.get("conflictPolicy", "skip")
    try:
        rows = validate_rows(reg_type, req.get("rows", []), policy)
    except (ValueError, TypeError, KeyError, OverflowError):
        gbt_raise("GBT_INVALID_REGISTER_DATA")
    program_name = req.get("programName")
    controller_ip = conn["controller_ip"]
    log_py(
        f"apply_rows begin controller_ip={controller_ip!r} type={reg_type!r} "
        f"policy={policy!r} row_count={len(rows)} program={program_name!r}"
    )

    # P 寄存器使用独立 HTTP 端口，提前检查可达性，避免写入时抛出晦涩的 SDK 异常。
    if reg_type == "P":
        if not program_name:
            gbt_raise("GBT_P_WRITE_NEED_PROGRAM")
        _check_p_service(controller_ip)

    arm = connect_arm(**conn)
    success = 0
    skipped = 0
    failed: List[str] = []
    point_failures: List[Dict[str, Any]] = []
    try:
        # 在第一笔覆盖前校验整批既有点，避免后面的未知类型导致部分写入。
        if reg_type == "PR":
            for row in rows:
                with redirect_sdk_stdout_to_stderr():
                    pose, ret = arm.register.read_PR(int(row["ID"]))
                ensure_read_status(ret)
                if policy == "overwrite" or ret != StatusCodeEnum.OK:
                    ensure_pr_metadata_write(arm, row, pose if ret == StatusCodeEnum.OK else None)
                if ret == StatusCodeEnum.OK and policy == "overwrite":
                    ensure_supported_pose(getattr(pose, "poseRegisterData", None))
        elif policy == "overwrite" and reg_type == "P":
            poses = read_p_pose_map(arm, program_name, {int(row["ID"]) for row in rows})
            for pose in poses.values():
                ensure_supported_pose(getattr(pose, "poseData", None))
        total = len(rows)
        for pos, row in enumerate(rows, start=1):
            # 在写入当前寄存器之前先上报进度：current=正在写入的序号，matched=此前已完成的条数。
            # 这样前端会显示 “正在写入 1/10，已完成 0 条” -> “正在写入 2/10，已完成 1 条” ...
            emit_progress("write", pos, total, success + skipped)
            try:
                if reg_type == "R":
                    ok, tag = write_r(arm, row, policy)
                elif reg_type == "PR":
                    ok, tag = write_pr(arm, row, policy)
                elif reg_type == "P":
                    ok, tag = write_p(arm, program_name, row, policy)
                else:
                    gbt_raise("GBT_UNSUPPORTED_REGISTER_TYPE")
            except Exception as exc:
                # 停止后续写入；当前项结果可能未知，保留此前已确认的计数。
                log_py(f"apply_rows interrupted: {exc!r}")
                return {"ok": False, "code": "GBT_WRITE_INTERRUPTED",
                        "stats": {"success": success, "skipped": skipped, "failed": len(failed) + 1,
                                  **({"failures": point_failures + [{"id": row["ID"], "outcome": "unknown", "reason": "GBT_P_WRITE_UNKNOWN"}],
                                      "notAttempted": total - pos} if reg_type == "P" else {})},
                        "details": failed + [f"ID={row.get('ID')}: result unknown; not attempted={total - pos}"]}

            if ok and tag == "skip":
                skipped += 1
            elif ok:
                success += 1
            else:
                failed.append(f"ID={row.get('ID')}: {tag}")
                if reg_type == "P":
                    point_failures.append({"id": row["ID"], "outcome": "unknown" if tag == "GBT_P_WRITE_UNKNOWN" else "failed", "reason": tag})
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
                "code": "GBT_PROGRAM_NOT_FOUND",
                "details": failed,
                "stats": {"success": success, "skipped": skipped, "failed": len(failed), "failures": point_failures},
            }
        log_py(
            f"apply_rows end partial_fail success={success} skipped={skipped} failed={len(failed)}"
        )
        return {
            "ok": False,
            "stats": {"success": success, "skipped": skipped, "failed": len(failed), **({"failures": point_failures} if reg_type == "P" else {})},
            "details": failed,
        }
    log_py(f"apply_rows end ok success={success} skipped={skipped}")
    return {
        "ok": True,
        "stats": {"success": success, "skipped": skipped, "failed": 0},
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


def append_excel_record(ws: Any, record: List[Any]) -> None:
    # 名称/注释可能以等号开头，必须作为文字保存，不能变成 Excel 公式。
    from openpyxl.cell import WriteOnlyCell
    cells = []
    for value in record:
        cell = WriteOnlyCell(ws, value=value)
        if isinstance(value, str):
            cell.data_type = "s"
        cells.append(cell)
    ws.append(cells)


def export_excel(register_type: str, rows: List[Dict[str, Any]], output_path: str) -> Dict[str, Any]:
    if Workbook is None:
        if _OPENPYXL_ERR is not None:
            log_py(f"openpyxl missing: {_OPENPYXL_ERR!r}")
        gbt_raise("GBT_OPENPYXL_MISSING")
    log_py(f"export_excel begin type={register_type!r} rows={len(rows)} path_len={len(output_path)}")
    headers = make_headers(register_type)
    if register_type != "R" and rows and any("PoseType" not in row for row in rows):
        if any("PoseType" in row for row in rows):
            gbt_raise("GBT_INVALID_REGISTER_DATA")
        # 旧表格缺少姿态信息，原样导出旧格式，不能补默认值改变下次覆盖的语义。
        headers = (["Type", "ID"] + list("XYZABC") + ["TF", "UF", "Coord"] if register_type == "P"
                   else ["TYPE", "ID"] + list("XYZABC") + ["coord"])
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
            record = [round3(v) if register_type == "R" and isinstance(v, (int, float)) else v for v in record]
            append_excel_record(ws, record)
    else:
        ws = wb.active
        ws.title = register_type
        ws.append(headers)
        for row in rows:
            record = [_cell_for_export(row, key, register_type) for key in headers]
            record = [round3(v) if register_type == "R" and isinstance(v, (int, float)) else v for v in record]
            append_excel_record(ws, record)

    # 同目录临时文件确保同卷替换；任何生成或替换失败均保留原备份。
    try:
        with tempfile.TemporaryDirectory(prefix=".gbt-excel-", dir=output_file.parent) as staging:
            staged_file = Path(staging) / "export.xlsx"
            with staged_file.open("w+b") as saved:
                wb.save(saved)
                saved.flush()
                os.fsync(saved.fileno())
            os.replace(staged_file, output_file)
    finally:
        wb.close()
    log_py(f"export_excel ok path={output_file} write_only={use_write_only}")
    return {"ok": True, "code": "export_saved"}


def fetch_robot_meta(conn: Dict[str, Any]) -> Dict[str, Any]:
    log_py(
        f"fetch_robot_meta begin controller_ip={conn['controller_ip']!r} "
        f"teach_panel_ip={conn['teach_panel_ip']!r} local_proxy={conn['local_proxy']!r}"
    )
    arm = connect_arm(**conn)
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
    export_excel(register_type, [], output_path)
    return {"ok": True, "code": "template_saved"}


# ---------- 入口 ------------------------------------------------------------


def _dispatch(payload: Dict[str, Any]) -> Dict[str, Any]:
    action = payload.get("action")
    if action in ("check_discovery", "discover_controllers"):
        import controller_discovery
        if action == "check_discovery":
            return controller_discovery.check()
        controller_discovery.scan(emit_frame)
        return {"ok": True}
    if action == "read_preview":
        return read_preview(_extract_connect_params(payload), payload["request"])
    if action == "apply_rows":
        return apply_rows(_extract_connect_params(payload), payload["request"])
    if action == "export_excel":
        return export_excel(
            payload["registerType"], payload.get("rows", []), payload["outputPath"]
        )
    if action == "export_template":
        return export_template(payload["registerType"], payload["outputPath"])
    if action == "fetch_robot_meta":
        return fetch_robot_meta(_extract_connect_params(payload))
    if action == "verify_connect":
        return verify_connect(_extract_connect_params(payload))
    gbt_raise("GBT_INTERNAL_ERROR")


def main() -> int:
    try:
        payload = read_payload()
    except Exception as exc:
        log_py(f"read_payload failed: {exc!r}")
        emit_frame({"ok": False, "code": "GBT_INTERNAL_ERROR", "message": "GBT_INTERNAL_ERROR"})
        return 0

    action = payload.get("action", "?")
    log_py(f"main action={action!r} keys={list(payload.keys())}")
    try:
        result = _dispatch(payload)
    except Exception as exc:
        code = sidecar_error_code(exc)
        if code == "GBT_INTERNAL_ERROR":
            log_py(f"main action={action!r} exception: {exc!r}\n{traceback.format_exc()}")
        emit_frame({"ok": False, "code": code, "message": code})
        return 0

    if not isinstance(result, dict):
        emit_frame(
            {
                "ok": False,
                "code": "GBT_INTERNAL_ERROR",
                "message": "GBT_INTERNAL_ERROR",
            }
        )
        return 0

    log_py(f"main action={action!r} done ok_field={result.get('ok')!r}")
    emit_frame(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
