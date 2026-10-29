"""原版兼容回归；全部使用合成报文/模拟句柄，不连接机器人。"""
import inspect
import json
import sys
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import controller_discovery as discovery


def response(mac=None, ip="10.0.0.2"):
    return json.dumps({"id": "test1234", "dest": discovery.SOURCE,
        "data": {"code": 1000, "res": {"ip": ip, "mac": mac}}}).encode()


class ParityTests(unittest.TestCase):
    def test_valid_ip_survives_missing_or_nonstandard_mac(self):
        for mac in (None, "", "unknown", "001122334455", "ff:ff:ff:ff:ff:ff"):
            with self.subTest(mac=mac):
                rows = discovery.parse_response(response(mac), "test1234")
                self.assertEqual([r["ip"] for r in rows], ["10.0.0.2"])
                self.assertEqual(rows[0]["mac"], "")
                self.assertIn(rows[0]["macStatus"], ("missing", "invalid"))

    def test_ipv6_is_visible_but_not_offered_as_ipv4_connection(self):
        rows = discovery.parse_response(response(ip="10.0.0.2\nfe80::1234\n"), "test1234")
        self.assertEqual([r["ip"] for r in rows], ["10.0.0.2", "fe80::1234"])
        self.assertFalse(rows[1]["connectable"])

    def test_bad_mac_results_keep_interface_identity(self):
        results = discovery.Results()
        row = {"ip": "10.0.0.2", "mac": "", "macStatus": "missing"}
        a = results.add(row, "a")
        b = results.add(row, "b")
        self.assertEqual(len(results.rows), 2)
        self.assertNotEqual(a["key"], b["key"])
        self.assertIsNone(results.add(row, "a"))

    def test_compact_request_matches_original_serialization(self):
        self.assertEqual(discovery.request_payload("test1234"),
            b'{"id":"test1234","src":"send_broadcast.go","cmd":"get_controller_ips","param":""}')

    def test_parser_rejection_counters_distinguish_failure_reasons(self):
        counters = Counter()
        self.assertEqual(discovery.parse_response(b"bad-json", "test1234", counters), [])
        self.assertEqual(discovery.parse_response(response(), "another", counters), [])
        self.assertEqual(counters["invalid_json"], 1)
        self.assertEqual(counters["request_mismatch"], 1)

    def test_auto_scan_receives_late_reply_and_attempts_every_interface(self):
        from scapy.layers.l2 import Ether
        from scapy.packet import Raw
        elapsed = [0.0]
        sockets = [MagicMock(), MagicMock()]
        send_times = []
        for sock in sockets:
            sock.send.side_effect = lambda packet: send_times.append(elapsed[0]) or len(bytes(packet))
        delivered = set()
        packet = Ether(type=discovery.RESPONSE_TYPE) / Raw(load=response("02:11:22:33:44:55"))
        def receive(sock, ether):
            if elapsed[0] >= 119 and id(sock) not in delivered:
                delivered.add(id(sock))
                return packet
            return None
        def sleep(seconds):
            elapsed[0] += seconds
        events = []
        interfaces = [{"id": x, "name": x, "mac": "02:11:22:33:44:55"} for x in ("wifi", "new-usb")]
        with patch.object(discovery, "driver_status", return_value="ready"), \
                patch.object(discovery, "load_backend", return_value=(None, Ether, Raw)), \
                patch.object(discovery, "interfaces", return_value=interfaces), \
                patch.object(discovery, "open_socket", side_effect=sockets), \
                patch.object(discovery, "receive_packet", side_effect=receive), \
                patch.object(discovery.secrets, "choice", side_effect=list("test1234")):
            # 旧接口也运行真实循环，从实际行为差异获得失败证据。
            args = (["wifi", "new-usb"], events.append) if "interface_ids" in inspect.signature(discovery.scan).parameters else (events.append,)
            discovery.scan(*args, clock=lambda: elapsed[0], sleep=sleep)
        self.assertGreaterEqual(elapsed[0], 120)
        self.assertLess(elapsed[0], 120.1)
        devices = [e["device"] for e in events if e["kind"] == "device"]
        self.assertEqual(set(devices[-1]["interfaceIds"]), {"wifi", "new-usb"})
        self.assertEqual(len(send_times), 28)
        self.assertGreater(max(send_times), 113)
        for sock in sockets:
            sock.close.assert_called_once()

    def test_mac_fallback_is_unambiguous_and_does_not_guess(self):
        iface = SimpleNamespace(network_name=r"\Device\NPF_{ABC}", ips={4: ["10.0.0.1"]})
        adapters = [{"guid": "{ABC}", "mac": "02:11:22:33:44:55", "ips": []}]
        self.assertEqual(discovery.fallback_mac(iface, adapters), "02:11:22:33:44:55")
        adapters = [{"guid": "other", "mac": "02:11:22:33:44:55", "ips": ["10.0.0.1"]}]
        self.assertEqual(discovery.fallback_mac(iface, adapters), "02:11:22:33:44:55")
        adapters.append({"guid": "ambiguous", "mac": "02:11:22:33:44:66", "ips": ["10.0.0.1"]})
        self.assertIsNone(discovery.fallback_mac(iface, adapters))

    def test_each_scan_refreshes_inventory_and_retries_recovered_interface(self):
        from scapy.layers.l2 import Ether
        from scapy.packet import Raw
        wifi = {"id": "wifi", "name": "wifi", "mac": "02:11:22:33:44:55"}
        usb = {"id": "usb", "name": "usb", "mac": "02:11:22:33:44:66"}
        opened = []
        round_number = [0]
        def open_interface(conf, iface):
            opened.append(iface["id"])
            if iface["id"] == "usb" and round_number[0] == 1:
                raise PermissionError("test only")
            sock = MagicMock()
            sock.send.return_value = 100
            return sock
        with patch.object(discovery, "driver_status", return_value="ready"), \
                patch.object(discovery, "load_backend", return_value=(None, Ether, Raw)), \
                patch.object(discovery, "interfaces", side_effect=[[wifi], [wifi, usb], [wifi, usb]]) as inventory, \
                patch.object(discovery, "open_socket", side_effect=open_interface), \
                patch.object(discovery, "receive_packet", return_value=None):
            all_events = []
            for number in range(3):
                round_number[0] = number
                elapsed = [0.0]
                def sleep(seconds):
                    elapsed[0] += seconds
                events = []
                discovery.scan(events.append, duration=0.05, clock=lambda: elapsed[0], sleep=sleep)
                all_events.append(events)
        self.assertEqual(inventory.call_count, 3)
        self.assertEqual(opened, ["wifi", "wifi", "usb", "wifi", "usb"])
        self.assertTrue(any(e["kind"] == "warning" for e in all_events[1]))
        self.assertFalse(any(e["kind"] == "warning" for e in all_events[2]))
        self.assertEqual(all_events[1][-1]["kind"], "finished")

    def test_no_interfaces_is_error_not_empty_success(self):
        events = []
        with patch.object(discovery, "driver_status", return_value="ready"), \
                patch.object(discovery, "load_backend", return_value=(None, None, None)), \
                patch.object(discovery, "interfaces", return_value=[]):
            discovery.scan(events.append)
        self.assertEqual(events[-1], {"kind": "error", "code": "no_interfaces"})

    def test_missing_source_mac_is_visible_and_never_fabricated(self):
        events = []
        with patch.object(discovery, "driver_status", return_value="ready"), \
                patch.object(discovery, "load_backend", return_value=(None, None, None)), \
                patch.object(discovery, "interfaces", return_value=[{"id": "unknown", "name": "unknown", "mac": ""}]), \
                patch.object(discovery, "open_socket") as opened:
            discovery.scan(events.append)
        opened.assert_not_called()
        self.assertIn({"kind": "warning", "code": "missing_mac", "interfaceId": "unknown"}, events)
        self.assertEqual(events[-1]["kind"], "error")

    def test_relaxed_mac_does_not_relax_protocol_validation(self):
        for field, value in (("id", "old"), ("dest", "unrelated"), ("data", {"code": 7, "res": {"ip": "10.0.0.2"}})):
            data = json.loads(response())
            data[field] = value
            self.assertEqual(discovery.parse_response(json.dumps(data).encode(), "test1234"), [])
        self.assertEqual(discovery.parse_response(response(ip="not-an-ip"), "test1234"), [])


if __name__ == "__main__":
    unittest.main()
