"""控制柜二层发现。仅由 discovery action 加载，不在应用启动时探测驱动。"""
from __future__ import annotations

import ctypes
from collections import Counter
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import string
import sys
import time

REQUEST_TYPE = 0xEEEA
RESPONSE_TYPE = 0xEEEB
SOURCE = "send_broadcast.go"
MAX_PAYLOAD = 8192
MAX_RESULTS = 1024
SCAN_DURATION = 120.0
SEND_SLOTS = (0, 2, 4, *range(14, 115, 10))


def diagnostic(event, **fields):
    print("[discovery] " + json.dumps({"event": event, **fields}, ensure_ascii=True), file=sys.stderr, flush=True)


def request_payload(request_id):
    return json.dumps({"id": request_id, "src": SOURCE, "cmd": "get_controller_ips", "param": ""}, separators=(",", ":")).encode("utf-8")


def normalize_mac(value):
    if not isinstance(value, str):
        return None
    mac = value.strip().replace("-", ":").lower()
    if not re.fullmatch(r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", mac):
        return None
    if mac == "00:00:00:00:00:00" or int(mac[:2], 16) & 1:
        return None
    return mac


def parse_response(payload, request_id, counters=None):
    def reject(reason):
        if counters is not None:
            counters[reason] += 1
        return []
    if not payload or len(payload) > MAX_PAYLOAD:
        return reject("payload_size")
    try:
        # 只允许帧末尾的零填充，不截取任意 JSON 子串。
        msg = json.loads(payload.rstrip(b"\x00").decode("utf-8"))
        if not isinstance(msg, dict):
            return reject("invalid_shape")
        if msg.get("id") != request_id or msg.get("dest") != SOURCE:
            return reject("request_mismatch")
        data = msg.get("data")
        if not isinstance(data, dict) or data.get("code") != 1000:
            return reject("response_code")
        result = data.get("res")
        if not isinstance(result, dict) or not isinstance(result.get("ip"), str):
            return reject("invalid_shape")
        raw_mac = result.get("mac")
        mac = normalize_mac(raw_mac) or ""
        mac_status = "valid" if mac else ("missing" if raw_mac is None or raw_mac == "" else "invalid")
        if not mac and counters is not None:
            counters["mac_" + mac_status] += 1
        rows = []
        seen = set()
        for item in result["ip"].splitlines():
            try:
                addr = ipaddress.ip_address(item.strip())
                # 原版 net.ParseIP 将 IPv4-mapped IPv6 输出为 IPv4。
                if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
                    addr = addr.ipv4_mapped
            except ValueError:
                continue
            if addr.is_unspecified or addr.is_multicast or addr.is_loopback or str(addr) == "255.255.255.255":
                continue
            if str(addr) in seen:
                continue
            seen.add(str(addr))
            row = {"ip": str(addr), "mac": mac, "macStatus": mac_status, "connectable": addr.version == 4}
            for key in ("mask", "gateway"):
                try:
                    row[key] = str(ipaddress.IPv4Address(result.get(key, "")))
                except (ValueError, TypeError):
                    pass
            rows.append(row)
        return rows if rows else reject("no_valid_ip")
    except (ValueError, TypeError, UnicodeError, RecursionError):
        return reject("invalid_json")


class Results:
    def __init__(self):
        self.rows = {}

    def add(self, row, interface_id):
        key = (row["mac"], row["ip"], "" if row["mac"] else interface_id)
        if key not in self.rows:
            if len(self.rows) >= MAX_RESULTS:
                raise RuntimeError("result_limit")
            self.rows[key] = dict(row, key=json.dumps(key, separators=(",", ":")), interfaceIds=[])
        current = self.rows[key]
        if interface_id in current["interfaceIds"]:
            return None
        current["interfaceIds"].append(interface_id)
        return dict(current, interfaceIds=list(current["interfaceIds"]))


def driver_status():
    if sys.platform != "win32":
        return "unsupported"
    import winreg
    installed = False
    admin_only = False
    for key_name in (r"SOFTWARE\Npcap", r"SYSTEM\CurrentControlSet\Services\npcap", r"SYSTEM\CurrentControlSet\Services\npcap\Parameters"):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_name) as key:
                installed = True
                try:
                    admin_only |= bool(winreg.QueryValueEx(key, "AdminOnly")[0])
                except FileNotFoundError:
                    pass
        except FileNotFoundError:
            pass
        except PermissionError:
            return "permission"
    dll = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "Npcap" / "wpcap.dll"
    if not dll.is_file():
        return "unavailable" if installed else "missing"
    if admin_only and not ctypes.windll.shell32.IsUserAnAdmin():
        return "permission"
    # Npcap 库可能尝试启动服务；在加载前只读确认服务已运行，避免隐式启动。
    if not service_running():
        return "unavailable"
    try:
        with os.add_dll_directory(str(dll.parent)):
            ctypes.CDLL(str(dll))
    except OSError:
        return "unavailable"
    return "ready"


def service_running():
    from ctypes import wintypes
    api = ctypes.WinDLL("advapi32", use_last_error=True)
    api.OpenSCManagerW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
    api.OpenSCManagerW.restype = wintypes.HANDLE
    api.OpenServiceW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.DWORD]
    api.OpenServiceW.restype = wintypes.HANDLE
    api.CloseServiceHandle.argtypes = [wintypes.HANDLE]
    class Status(ctypes.Structure):
        _fields_ = [(name, wintypes.DWORD) for name in ("type", "state", "accepted", "exit", "specific", "checkpoint", "wait")]
    api.QueryServiceStatus.argtypes = [wintypes.HANDLE, ctypes.POINTER(Status)]
    manager = api.OpenSCManagerW(None, None, 1)
    if not manager:
        return False
    service = None
    try:
        service = api.OpenServiceW(manager, "npcap", 4)
        if not service:
            return False
        status = Status()
        return bool(api.QueryServiceStatus(service, ctypes.byref(status))) and status.state == 4
    finally:
        if service:
            api.CloseServiceHandle(service)
        api.CloseServiceHandle(manager)


def error_status(exc):
    print(f"[discovery] {type(exc).__name__}: {exc}", file=sys.stderr)
    if isinstance(exc, PermissionError) or "access is denied" in str(exc).lower() or "permission" in str(exc).lower():
        return "permission"
    if isinstance(exc, ImportError):
        return "component_missing"
    return "unavailable"


def load_backend():
    # Scapy 对 Windows 网卡的探测严格延迟到此处。
    from scapy.all import conf, Ether, Raw
    conf.use_pcap = True
    if not conf.use_pcap:
        raise OSError("Npcap backend unavailable")
    return conf, Ether, Raw


def fallback_mac(iface, adapters):
    """优先 GUID，次选唯一 IP 交集；不猜测、不借用另一张网卡的 MAC。"""
    name = str(iface.network_name).lower()
    exact = [a for a in adapters if a.get("guid") and name.endswith(str(a["guid"]).lower())]
    ips = getattr(iface, "ips", {})
    ips = {ip for values in ips.values() for ip in values} if isinstance(ips, dict) else set(ips)
    candidates = exact or [a for a in adapters if ips.intersection(a.get("ips", []))]
    if len(candidates) == 1:
        return normalize_mac(candidates[0].get("mac"))
    return None


def interfaces(conf):
    found = {}
    adapters = None
    for iface in conf.ifaces.values():
        flags = int(getattr(iface, "flags", 0))
        mac = normalize_mac(getattr(iface, "mac", None))
        # PCAP_IF_LOOPBACK=1，PCAP_IF_UP=2；旧版驱动 flags=0 时由打开接口验证。
        if flags & 1 or (flags and not flags & 2):
            diagnostic("interface_skipped", interfaceId=str(iface.network_name), flags=flags)
            continue
        name = str(iface.network_name)
        if not mac:
            if adapters is None:
                try:
                    from scapy.arch.windows import get_windows_if_list
                    adapters = get_windows_if_list()
                except Exception as exc:
                    diagnostic("mac_lookup_failed", code=error_status(exc))
                    adapters = []
            mac = fallback_mac(iface, adapters)
        found[name] = {"id": name, "name": str(iface.description or iface.name), "mac": mac or ""}
        diagnostic("interface", **found[name], flags=flags)
    return list(found.values())


def open_socket(conf, iface):
    sock = conf.L2socket(iface=iface["id"], promisc=False, filter="ether proto 0xEEEB")
    try:
        if sock.pcap_fd.datalink() != 1:
            raise OSError("Not an Ethernet interface")
        sock.pcap_fd.setnonblock(True)
        return sock
    except Exception:
        sock.close()
        raise


def receive_packet(sock, ether):
    # Scapy 2.6.1 的 next() 会吞掉负返回码，且按原始长度而非捕获长度复制。
    # 直接读取同一 Npcap 句柄的返回码和 caplen，再交给 Scapy 解码。
    from scapy.libs.winpcapy import pcap_next_ex
    fd = sock.pcap_fd
    code = pcap_next_ex(fd.pcap, ctypes.byref(fd.header), ctypes.byref(fd.pkt_data))
    if code == 0:
        return None
    if code < 0:
        raise OSError("Npcap read failed")
    size = fd.header.contents.caplen
    if size < 14 or size > MAX_PAYLOAD + 14:
        return None
    return ether(ctypes.string_at(fd.pkt_data, size))


def check():
    status = driver_status()
    diagnostic("driver_check", status=status)
    result = {"status": status, "interfaces": [], "warnings": []}
    if status != "ready":
        return result
    try:
        conf, _, _ = load_backend()
        for iface in interfaces(conf):
            if not iface["mac"]:
                result["warnings"].append({"code": "missing_mac", "interfaceId": iface["id"], "name": iface["name"]})
                continue
            try:
                sock = open_socket(conf, iface)
                sock.close()
                result["interfaces"].append(iface)
            except Exception as exc:
                result["warnings"].append({"code": error_status(exc), "interfaceId": iface["id"], "name": iface["name"]})
        if not result["interfaces"]:
            errors = result["warnings"]
            result["status"] = ("permission" if any(e["code"] == "permission" for e in errors) else "unavailable") if errors else "no_interfaces"
    except Exception as exc:
        result["status"] = error_status(exc)
    return result


def scan(emit, duration=SCAN_DURATION, clock=time.monotonic, sleep=time.sleep):
    status = driver_status()
    diagnostic("scan_driver", status=status)
    if status != "ready":
        emit({"kind": "error", "code": status})
        return
    sockets = {}
    statistics = {}
    try:
        conf, Ether, Raw = load_backend()
        available = {item["id"]: item for item in interfaces(conf)}
        emit({"kind": "interfaces", "interfaces": list(available.values())})
        for interface_id, iface in available.items():
            if not iface["mac"]:
                emit({"kind": "warning", "code": "missing_mac", "interfaceId": interface_id})
                continue
            try:
                sockets[interface_id] = (open_socket(conf, iface), iface)
                statistics[interface_id] = Counter()
                diagnostic("opened", interfaceId=interface_id)
            except Exception as exc:
                emit({"kind": "warning", "code": error_status(exc), "interfaceId": interface_id})
        if not sockets:
            emit({"kind": "error", "code": "no_interfaces"})
            return
        request_id = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))
        results = Results()
        started = clock()
        sent = set()
        # 所有接口已打开并设置过滤器，再发送请求；非阻塞轮询保证无报文时也能超时。
        while clock() - started < duration and sockets:
            elapsed = clock() - started
            for slot in SEND_SLOTS:
                if elapsed >= slot and slot not in sent:
                    sent.add(slot)
                    for iid, (sock, iface) in list(sockets.items()):
                        try:
                            sent_count = sock.send(Ether(src=iface["mac"], dst="ff:ff:ff:ff:ff:ff", type=REQUEST_TYPE) / Raw(load=request_payload(request_id)))
                            if sent_count is not None and sent_count < 0:
                                raise OSError("Npcap send failed")
                            statistics[iid]["sent"] += 1
                            diagnostic("sent", interfaceId=iid, elapsed=round(elapsed, 3), sourceMac=iface["mac"], requestId=request_id)
                        except Exception as exc:
                            emit({"kind": "warning", "code": error_status(exc), "interfaceId": iid})
                            sock.close()
                            del sockets[iid]
            for iid, (sock, _) in list(sockets.items()):
                try:
                    for _ in range(32):
                        packet = receive_packet(sock, Ether)
                        if packet is None:
                            break
                        statistics[iid]["received"] += 1
                        if not packet.haslayer(Ether) or packet[Ether].type != RESPONSE_TYPE:
                            continue
                        for row in parse_response(bytes(packet[Ether].payload), request_id, statistics[iid]):
                            updated = results.add(row, iid)
                            if updated:
                                statistics[iid]["accepted"] += 1
                                diagnostic("accepted", interfaceId=iid, elapsed=round(clock() - started, 3), macStatus=row["macStatus"])
                                emit({"kind": "device", "device": updated})
                        # 首次拒绝/后续每 100 帧汇总，停止前也有诊断，避免坏包刷屏。
                        if statistics[iid]["received"] == 1 or statistics[iid]["received"] % 100 == 0:
                            diagnostic("receive_summary", interfaceId=iid, counters=dict(statistics[iid]))
                except Exception as exc:
                    code = "result_limit" if str(exc) == "result_limit" else error_status(exc)
                    emit({"kind": "warning", "code": code, "interfaceId": iid})
                    sock.close()
                    del sockets[iid]
            sleep(0.02)
        if sockets:
            emit({"kind": "finished", "reason": "timeout"})
        else:
            emit({"kind": "error", "code": "unavailable"})
    except Exception as exc:
        emit({"kind": "error", "code": error_status(exc)})
    finally:
        for iid, counters in statistics.items():
            diagnostic("summary", interfaceId=iid, counters=dict(counters))
        for sock, _ in sockets.values():
            sock.close()
