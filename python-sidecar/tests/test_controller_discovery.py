import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from unittest.mock import MagicMock
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import controller_discovery as discovery


class ProtocolTests(unittest.TestCase):
    def response(self, **changes):
        value = {"id": "abc12345", "dest": "send_broadcast.go", "data": {
            "code": 1000, "res": {"ip": "10.9.8.7", "mac": "02:11:22:33:44:55"}}}
        value.update(changes)
        return json.dumps(value).encode()

    def test_request_preserves_wire_protocol(self):
        self.assertEqual(json.loads(discovery.request_payload("abc12345")), {
            "id": "abc12345", "src": "send_broadcast.go", "cmd": "get_controller_ips", "param": ""})

    def test_unknown_subnet_and_padding(self):
        rows = discovery.parse_response(self.response() + b"\x00\x00", "abc12345")
        self.assertEqual(rows[0]["ip"], "10.9.8.7")

    def test_unrelated_malformed_and_oversized_packets(self):
        for payload in (b"invalid", b"[]", self.response(id="old"), self.response(dest="other"),
                        self.response() + b"junk", b"x" * 9000):
            self.assertEqual(discovery.parse_response(payload, "abc12345"), [])

    def test_multiline_addresses_and_invalid_mac(self):
        data = {"code": 1000, "res": {"ip": "garbage\n10.0.0.1\n192.168.2.3\n10.0.0.1", "mac": "02-11-22-33-44-55"}}
        rows = discovery.parse_response(self.response(data=data), "abc12345")
        self.assertEqual([row["ip"] for row in rows], ["10.0.0.1", "192.168.2.3"])
        data["res"]["mac"] = "FF:FF:FF:FF:FF:FF"
        self.assertEqual(discovery.parse_response(self.response(data=data), "abc12345")[0]["macStatus"], "invalid")

    def test_merge_interfaces_keep_multiple_addresses(self):
        results = discovery.Results()
        row = discovery.parse_response(self.response(), "abc12345")[0]
        self.assertIsNotNone(results.add(row, "nic1"))
        self.assertIsNone(results.add(row, "nic1"))
        self.assertEqual(results.add(row, "nic2")["interfaceIds"], ["nic1", "nic2"])
        self.assertIsNotNone(results.add(dict(row, ip="10.1.1.1"), "nic1"))

    def test_missing_driver_does_not_import_scapy(self):
        with patch.object(discovery, "driver_status", return_value="missing"), patch.object(discovery, "load_backend") as load:
            self.assertEqual(discovery.check()["status"], "missing")
            load.assert_not_called()

    def test_classify_dependency_errors(self):
        with patch.object(discovery, "driver_status", return_value="ready"):
            for exc, expected in ((PermissionError(), "permission"), (OSError(), "unavailable"), (ImportError(), "component_missing")):
                with patch.object(discovery, "load_backend", side_effect=exc):
                    self.assertEqual(discovery.check()["status"], expected)

    def test_link_local_and_no_ipv4_interfaces_are_not_filtered(self):
        iface = SimpleNamespace(flags=2, mac="02:11:22:33:44:55", network_name="nic", description="virtual Ethernet", name="nic", ip="169.254.1.1")
        conf = SimpleNamespace(ifaces={1: iface, 2: iface})
        self.assertEqual(len(discovery.interfaces(conf)), 1)
        iface.ip = ""
        self.assertEqual(len(discovery.interfaces(conf)), 1)
        iface.flags = 1
        self.assertEqual(discovery.interfaces(conf), [])

    def test_partial_interface_failure_is_reported(self):
        with patch.object(discovery, "driver_status", return_value="ready"), patch.object(discovery, "load_backend", return_value=(None, None, None)), patch.object(discovery, "interfaces", return_value=[{"id": "good", "name": "good", "mac": "02:11:22:33:44:55"}, {"id": "bad", "name": "bad", "mac": "02:11:22:33:44:55"}]), patch.object(discovery, "open_socket", side_effect=[MagicMock(), PermissionError()]):
            result = discovery.check()
        self.assertEqual(result["status"], "ready")
        self.assertEqual(len(result["interfaces"]), 1)
        self.assertEqual(result["warnings"][0]["code"], "permission")


class ScanTests(unittest.TestCase):
    def run_scan(self, send_error=None, receive_error=None, send_result=0):
        elapsed = [0.0]
        def sleep(seconds):
            elapsed[0] += seconds
        sock = MagicMock()
        sock.send.side_effect = send_error
        events = []
        with patch.object(discovery, "driver_status", return_value="ready"), patch.object(discovery, "load_backend", return_value=(None, MagicMock(), MagicMock())), patch.object(discovery, "interfaces", return_value=[{"id": "nic", "mac": "02:11:22:33:44:55"}]), patch.object(discovery, "open_socket", return_value=sock) as opened, patch.object(discovery, "receive_packet", return_value=None, side_effect=receive_error):
            def send(_):
                self.assertTrue(opened.called)
                if send_error:
                    raise send_error
                return send_result
            sock.send.side_effect = send
            discovery.scan(events.append, clock=lambda: elapsed[0], sleep=sleep)
        return [e for e in events if e["kind"] != "interfaces"], sock, elapsed[0]

    def test_silent_network_times_out_and_retries_are_bounded(self):
        events, sock, elapsed = self.run_scan()
        self.assertEqual(events, [{"kind": "finished", "reason": "timeout"}])
        self.assertEqual(sock.send.call_count, 14)
        self.assertGreaterEqual(elapsed, 120)
        self.assertLess(elapsed, 120.1)
        sock.close.assert_called_once()

    def test_send_failure_is_not_empty_success(self):
        events, sock, _ = self.run_scan(send_error=OSError("send failed"))
        self.assertEqual(events[-1]["kind"], "error")
        self.assertEqual(events[0]["kind"], "warning")
        sock.close.assert_called_once()

    def test_negative_send_return_is_not_empty_success(self):
        events, sock, _ = self.run_scan(send_result=-1)
        self.assertEqual(events[-1]["kind"], "error")
        self.assertEqual(sock.send.call_count, 1)
        sock.close.assert_called_once()

    def test_read_failure_is_not_empty_success(self):
        events, sock, _ = self.run_scan(receive_error=OSError("read failed"))
        self.assertEqual(events[-1]["kind"], "error")
        sock.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
