"""核验指定冻结组件，既不广播也不连接机器人。"""
import json
import subprocess
import sys
import unittest
from pathlib import Path
from PyInstaller.archive.readers import CArchiveReader

TARGET = Path(sys.argv.pop(1)).resolve()


class FrozenDiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.archive = CArchiveReader(str(TARGET))
        cls.pyz = cls.archive.open_embedded_archive("PYZ.pyz")
        cls.module = {"__name__": "frozen_discovery_verification"}
        exec(cls.pyz.extract("controller_discovery"), cls.module)

    def test_contains_current_scanner_and_scapy(self):
        self.assertIn("scapy", self.pyz.toc)
        self.assertEqual(self.module["SCAN_DURATION"], 120)
        self.assertEqual(len(self.module["SEND_SLOTS"]), 14)
        self.assertNotIn("interface_ids", self.module["scan"].__code__.co_varnames)

    def test_embedded_parser_keeps_ip_without_mac(self):
        payload = json.dumps({"id": "test1234", "dest": "send_broadcast.go", "data": {"code": 1000, "res": {"ip": "192.0.2.10"}}}).encode()
        row = self.module["parse_response"](payload, "test1234")[0]
        self.assertEqual(row["ip"], "192.0.2.10")
        self.assertEqual(row["macStatus"], "missing")

    def test_no_npcap_binaries_bundled(self):
        forbidden = {"wpcap.dll", "packet.dll", "npcap.sys", "npf.sys", "npcaphelper.exe"}
        for name in self.archive.toc:
            normalized = name.replace("\\", "/").lower()
            self.assertNotIn(normalized.split("/")[-1], forbidden)
            self.assertNotIn("/npcap/", normalized)

    def test_real_executable_check_returns_structured_status(self):
        result = subprocess.run([str(TARGET)], input=json.dumps({"action": "check_discovery"}),
            capture_output=True, text=True, encoding="utf-8", timeout=25)
        self.assertEqual(result.returncode, 0, result.stderr)
        frame = result.stdout.split("<<<GBT-BEGIN>>>")[1].split("<<<GBT-END>>>")[0]
        data = json.loads(frame)
        self.assertIn(data["status"], ("ready", "missing", "permission", "unavailable", "no_interfaces", "component_missing", "unsupported"))
        self.assertIsInstance(data["interfaces"], list)
        self.assertIsInstance(data["warnings"], list)
        print("Frozen driver status:", data["status"])


if __name__ == "__main__":
    unittest.main()
