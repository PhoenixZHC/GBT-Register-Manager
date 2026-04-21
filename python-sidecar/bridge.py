import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from openpyxl import Workbook

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
SDK_EXAMPLE_DIR = PROJECT_DIR / "Python_v2.0.1.0" / "example"

try:
    from Agilebot import Arm, PoseRegister, PoseType, StatusCodeEnum
except Exception:  # pragma: no cover
    Arm = None
    PoseRegister = None
    PoseType = None
    StatusCodeEnum = None


def round3(v: Any) -> float:
    x = float(v)
    if math.isnan(x) or math.isinf(x):
        return 0.0
    return round(x, 3)


def log_py(msg: str) -> None:
    """写入 stderr，与 stdout 单行 JSON 分离，供 Rust / 终端排查。"""
    print(f"[GBT-PY] {msg}", file=sys.stderr, flush=True)


def output(data: Dict[str, Any]) -> None:
    """只向 stdout 输出一行 JSON；用 ASCII 转义非 ASCII，避免 Windows 控制台编码导致 Rust 端 UTF-8 解析失败。"""
    line = json.dumps(data, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    sys.stdout.buffer.write(line.encode("ascii"))


def make_headers(register_type: str) -> List[str]:
    if register_type == "R":
        return ["type", "ID", "value"]
    if register_type == "P":
        return ["Type", "ID", "X", "Y", "Z", "A", "B", "C", "TF", "UF", "Coord"]
    if register_type == "PR":
        return ["TYPE", "ID", "X", "Y", "Z", "A", "B", "C", "coord"]
    raise ValueError("不支持的寄存器类型")


# 「读取全部」：从该 ID 起顺序尝试，连续失败达到上限则停止（认为后面无有效寄存器）。
READ_ALL_FIRST_ID = 1
READ_ALL_CONSECUTIVE_FAIL_LIMIT = 10
# 防止异常情况下无限扫描
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


def connect_arm(ip: str):
    if Arm is None:
        raise RuntimeError("未找到 Agilebot SDK，请确认 Python 环境与 SDK 安装。")
    log_py(f"SDK Arm.connect begin ip={ip!r}")
    arm = Arm()
    ret = arm.connect(ip)
    if ret != StatusCodeEnum.OK:
        err = getattr(ret, "errmsg", ret)
        log_py(f"SDK Arm.connect failed: {err!r}")
        raise RuntimeError(f"连接机器人失败: {err}")
    log_py("SDK Arm.connect ok")
    return arm


def verify_connect(ip: str) -> Dict[str, Any]:
    """仅用于首屏连接校验：尝试连接后立即断开，避免与后续 read/apply 各开各的连接冲突。"""
    log_py(f"verify_connect begin ip={ip!r}")
    try:
        arm = connect_arm(ip)
        try:
            log_py("verify_connect ok, disconnecting")
            return {"ok": True, "message": "连接成功"}
        finally:
            arm.disconnect()
            log_py("verify_connect disconnected")
    except Exception as exc:  # pragma: no cover
        log_py(f"verify_connect exception: {exc!r}")
        return {"ok": False, "message": str(exc)}


def read_r(arm, indexes: List[int]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for idx in indexes:
        value, ret = arm.register.read_R(idx)
        if ret == StatusCodeEnum.OK:
            rows.append({"type": "R", "ID": idx, "value": round3(value)})
    return rows


def read_pr(arm, indexes: List[int]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for idx in indexes:
        pose, ret = arm.register.read_PR(idx)
        if ret == StatusCodeEnum.OK:
            pos = pose.poseRegisterData.cartData.position
            # SDK 示例中未展示 TF/UF，PR 按用户定义仅输出坐标和左右手系
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
                    "coord": "L",
                }
            )
    return rows


def read_p(arm, program_name: str, indexes: List[int]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for idx in indexes:
        pose, ret = arm.program_pose.read(program_name, idx)
        if ret == StatusCodeEnum.OK:
            pos = pose.poseData.cartData.baseCart.position
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
                    "TF": 0,
                    "UF": 0,
                    "Coord": "L",
                }
            )
    return rows


def read_r_all_scan(arm) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    consec_fail = 0
    idx = READ_ALL_FIRST_ID
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
    while idx <= READ_ALL_MAX_ID and consec_fail < READ_ALL_CONSECUTIVE_FAIL_LIMIT:
        pose, ret = arm.register.read_PR(idx)
        if ret == StatusCodeEnum.OK:
            pos = pose.poseRegisterData.cartData.position
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
                    "coord": "L",
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
    while idx <= READ_ALL_MAX_ID and consec_fail < READ_ALL_CONSECUTIVE_FAIL_LIMIT:
        pose, ret = arm.program_pose.read(program_name, idx)
        if ret == StatusCodeEnum.OK:
            pos = pose.poseData.cartData.baseCart.position
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
                    "TF": 0,
                    "UF": 0,
                    "Coord": "L",
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
            indexes = build_indexes(selector)
            rows = read_r(arm, indexes)
        elif reg_type == "PR":
            indexes = build_indexes(selector)
            rows = read_pr(arm, indexes)
        elif reg_type == "P":
            program_name = req.get("programName")
            if not program_name:
                raise RuntimeError("读取 P 点时 programName 不能为空。")
            indexes = build_indexes(selector)
            rows = read_p(arm, program_name, indexes)
        else:
            raise RuntimeError("不支持的寄存器类型。")
        log_py(f"read_preview ok row_count={len(rows)}")
        return {"rows": rows}
    finally:
        arm.disconnect()
        log_py("read_preview disconnected")


def write_r(arm, row: Dict[str, Any], policy: str) -> Tuple[bool, str]:
    idx = int(row["ID"])
    value = round3(row["value"])
    old, ret = arm.register.read_R(idx)
    exists = ret == StatusCodeEnum.OK
    if exists and policy == "skip":
        return True, "skip"
    ret = arm.register.write_R(idx, value)
    if ret != StatusCodeEnum.OK:
        return False, getattr(ret, "errmsg", str(ret))
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
    return pose_register


def write_pr(arm, row: Dict[str, Any], policy: str) -> Tuple[bool, str]:
    idx = int(row["ID"])
    old, ret = arm.register.read_PR(idx)
    exists = ret == StatusCodeEnum.OK
    if exists and policy == "skip":
        return True, "skip"
    pose_register = build_pose_register_from_row(row)
    ret = arm.register.write_PR(pose_register)
    if ret != StatusCodeEnum.OK:
        return False, getattr(ret, "errmsg", str(ret))
    return True, "write"


def write_p(arm, program_name: str, row: Dict[str, Any], policy: str) -> Tuple[bool, str]:
    idx = int(row["ID"])
    pose, ret = arm.program_pose.read(program_name, idx)
    exists = ret == StatusCodeEnum.OK
    if exists and policy == "skip":
        return True, "skip"
    if not exists:
        return False, "当前 SDK 示例未提供新增程序点 API，仅支持修改已存在点位。"
    pos = pose.poseData.cartData.baseCart.position
    pos.x = round3(row["X"])
    pos.y = round3(row["Y"])
    pos.z = round3(row["Z"])
    pos.a = round3(row["A"])
    pos.b = round3(row["B"])
    pos.c = round3(row["C"])
    ret = arm.program_pose.write(program_name, idx, pose)
    if ret != StatusCodeEnum.OK:
        return False, getattr(ret, "errmsg", str(ret))
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
        arm.disconnect()
        log_py("apply_rows disconnected")

    if failed:
        log_py(f"apply_rows end partial_fail success={success} skipped={skipped} failed={len(failed)}")
        return {
            "ok": False,
            "message": f"完成：成功 {success}，跳过 {skipped}，失败 {len(failed)}。{'; '.join(failed[:5])}",
            "details": failed,
        }
    log_py(f"apply_rows end ok success={success} skipped={skipped}")
    return {"ok": True, "message": f"完成：成功 {success}，跳过 {skipped}，失败 0。", "details": []}


def _cell_for_export(row: Dict[str, Any], key: str, reg_type: str) -> Any:
    if key in row:
        return row[key]
    if reg_type == "P" and key == "Coord":
        return row.get("Coord（L/R）", "")
    if reg_type == "PR" and key == "coord":
        return row.get("coord（L/R）", "")
    return row.get(key, "")


def export_excel(register_type: str, rows: List[Dict[str, Any]], output_path: str) -> Dict[str, Any]:
    log_py(f"export_excel begin type={register_type!r} rows={len(rows)} path_len={len(output_path)}")
    wb = Workbook()
    ws = wb.active
    ws.title = register_type
    headers = make_headers(register_type)
    ws.append(headers)
    for row in rows:
        record = []
        for key in headers:
            value = _cell_for_export(row, key, register_type)
            if isinstance(value, (int, float)):
                value = round3(value)
            record.append(value)
        ws.append(record)
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_file)
    log_py(f"export_excel ok path={output_file}")
    return {"ok": True, "message": f"已保存到 {output_file}"}


def fetch_robot_meta(ip: str) -> Dict[str, Any]:
    """连接后读取机型与运动控制器版本（SDK 示例：get_arm_model_info / get_controller_version）。"""
    log_py(f"fetch_robot_meta begin ip={ip!r}")
    arm = connect_arm(ip)
    try:
        model_info, ret_m = arm.get_arm_model_info()
        ver_info, ret_v = arm.get_controller_version()
        model_str = str(model_info) if ret_m == StatusCodeEnum.OK and model_info is not None else ""
        ver_str = str(ver_info) if ret_v == StatusCodeEnum.OK and ver_info is not None else ""
        log_py(f"fetch_robot_meta ok model_len={len(model_str)} ver_len={len(ver_str)}")
        return {"model": model_str, "controllerVersion": ver_str}
    finally:
        arm.disconnect()
        log_py("fetch_robot_meta disconnected")


def export_template(register_type: str, output_path: str) -> Dict[str, Any]:
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


def main() -> None:
    if len(sys.argv) < 2:
        log_py("main abort: missing argv JSON")
        output({"ok": False, "message": "缺少 JSON 参数"})
        return
    payload = json.loads(sys.argv[1])
    action = payload.get("action")
    log_py(f"main action={action!r} keys={list(payload.keys())}")
    try:
        if action == "read_preview":
            result = read_preview(payload["ip"], payload["request"])
        elif action == "apply_rows":
            result = apply_rows(payload["ip"], payload["request"])
        elif action == "export_excel":
            result = export_excel(
                payload["registerType"], payload.get("rows", []), payload["outputPath"]
            )
        elif action == "export_template":
            result = export_template(payload["registerType"], payload["outputPath"])
        elif action == "fetch_robot_meta":
            result = fetch_robot_meta(payload["ip"])
        elif action == "verify_connect":
            result = verify_connect(payload["ip"])
        else:
            raise RuntimeError("未知 action")
        log_py(f"main action={action!r} done ok_field={result.get('ok')!r}")
        output(result)
    except Exception as exc:  # pragma: no cover
        log_py(f"main action={action!r} exception: {exc!r}")
        output({"ok": False, "message": str(exc)})


if __name__ == "__main__":
    main()
