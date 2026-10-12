"""只加载待测函数；SDK、网络与写入全部使用隔离替身。"""
import ast
import contextlib
import math
from pathlib import Path
from types import SimpleNamespace
import typing
import unittest
from unittest.mock import MagicMock


class RegisterSafetyTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse((Path(__file__).parents[1] / "bridge.py").read_text(encoding="utf-8-sig"))
        self.ns = dict(vars(typing), math=math, StatusCodeEnum=SimpleNamespace(OK=0, NOT_FOUND=-28, PROGRAM_POSE_NOT_FOUND=-10, PROGRAM_NOT_FOUND=-11),
                       log_py=lambda *a: None, emit_progress=lambda *a: None,
                       READ_ALL_FIRST_ID=1, READ_ALL_CONSECUTIVE_FAIL_LIMIT=10, READ_ALL_MAX_ID=100000,
                       redirect_sdk_stdout_to_stderr=contextlib.nullcontext, ProgressCallback=typing.Callable)
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name not in ("main", "redirect_sdk_stdout_to_stderr")]
        module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)] + functions, type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), "isolated-bridge", "exec"), self.ns)
        self.reg = SimpleNamespace(read_R=MagicMock(return_value=(None, -28)), write_R=MagicMock(return_value=0),
                                   read_PR=MagicMock(return_value=(None, -28)), write_PR=MagicMock(return_value=0))
        self.arm = SimpleNamespace(register=self.reg)
        self.ns.update(connect_arm=MagicMock(return_value=self.arm), _safe_disconnect=MagicMock())
        # 测试不输出协议或写日志。
        self.ns.update(log_py=lambda *a: None, emit_progress=lambda *a: None)

    def apply(self, rows):
        return self.ns["apply_rows"]({"controller_ip": "isolated"}, {"registerType": "R", "rows": rows})

    def test_skip_never_writes_on_read_error(self):
        for name in ("R", "PR"):
            getattr(self.reg, "read_" + name).return_value = (None, 99)
            with self.assertRaisesRegex(RuntimeError, "GBT_REGISTER_READ_FAILED"):
                self.ns["write_" + name.lower()](self.arm, {"ID": 1, "value": 5}, "skip")
            getattr(self.reg, "write_" + name).assert_not_called()

    def test_missing_program_has_specific_error_in_range_and_all(self):
        self.arm.program_pose = SimpleNamespace(read=MagicMock(return_value=(None, -11)),
            read_all_poses=MagicMock(return_value=(None, -11)), add=MagicMock(), write=MagicMock())
        for name, args in (("read_p", (self.arm, "missing", [1, 2])),
                           ("read_p_pose_map", (self.arm, "missing"))):
            with self.subTest(path=name), self.assertRaisesRegex(RuntimeError, "GBT_PROGRAM_NOT_FOUND"):
                self.ns[name](*args)
        self.arm.program_pose.add.assert_not_called()
        self.arm.program_pose.write.assert_not_called()

    def test_missing_pose_remains_empty_but_p_communication_error_aborts(self):
        self.arm.program_pose = SimpleNamespace(read=MagicMock(return_value=(None, -10)))
        self.assertEqual(self.ns["read_p"](self.arm, "existing", [1]), [])
        self.arm.program_pose.read.return_value = (None, 99)
        with self.assertRaisesRegex(RuntimeError, "GBT_REGISTER_READ_FAILED"):
            self.ns["read_p"](self.arm, "existing", [1])

    def test_missing_program_write_rejected_without_writing(self):
        self.arm.program_pose = SimpleNamespace(read_all_poses=MagicMock(return_value=(None, -11)),
            add=MagicMock(), write=MagicMock())
        ok, tag = self.ns["write_p"](self.arm, "missing", {"ID": 1}, "skip")
        self.assertFalse(ok)
        self.assertIn("GBT_PROGRAM_NOT_FOUND", tag)
        self.arm.program_pose.add.assert_not_called()
        self.arm.program_pose.write.assert_not_called()

    def test_explicit_missing_allows_write_and_existing_skips(self):
        self.assertEqual(self.ns["write_r"](self.arm, {"ID": 1, "value": 5}, "skip"), (True, "write"))
        self.reg.read_R.return_value = (5, 0)
        self.assertEqual(self.ns["write_r"](self.arm, {"ID": 1, "value": 9}, "skip"), (True, "skip"))
        self.assertEqual(self.reg.write_R.call_count, 1)

    def test_bad_batch_rejected_before_connect_or_write(self):
        for row in ({"ID": 2, "value": "bad"}, {"ID": 2, "value": "NaN"}, {"ID": 2, "value": "Infinity"},
                    {"ID": 2.9, "value": 5}, {"ID": 1, "value": 5}, {"ID": 2, "value": None}):
            with self.assertRaisesRegex(RuntimeError, "GBT_INVALID_REGISTER_DATA"):
                self.apply([{"ID": 1, "value": 10}, row])
        self.ns["connect_arm"].assert_not_called()
        self.reg.write_R.assert_not_called()

    def test_invalid_pose_fields_rejected(self):
        row = dict(ID=1, X=0, Y=0, Z=0, A=0, B=0, C=0, Coord="L", TF=0, UF=0)
        for changed in (dict(Coord="unknown"), dict(TF=1.5), dict(UF="bad")):
            with self.assertRaises(ValueError):
                self.ns["validate_rows"]("P", [dict(row, **changed)], "skip")

    def test_runtime_exception_preserves_confirmed_results_and_stops(self):
        self.reg.write_R.side_effect = [0, OSError("connection lost")]
        result = self.apply([{"ID": i, "value": 10} for i in (1, 2, 3)])
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "GBT_WRITE_INTERRUPTED")
        self.assertEqual(result["stats"], {"success": 1, "skipped": 0, "failed": 1})
        self.assertIn("not attempted=1", result["details"][0])
        self.assertEqual(self.reg.write_R.call_count, 2)
        self.ns["_safe_disconnect"].assert_called_once()

    def test_sparse_range_includes_later_register(self):
        self.reg.read_R.side_effect = lambda i: (42, 0) if i == 20 else (None, -28)
        rows = self.ns["read_r"](self.arm, self.ns["build_indexes"]({"startId": 1, "endId": 20}))
        self.assertEqual(rows, [{"type": "R", "ID": 20, "value": 42.0}])
        self.assertEqual(self.reg.read_R.call_count, 20)

    def test_range_read_error_is_not_empty_success(self):
        self.reg.read_R.return_value = (None, 99)
        with self.assertRaisesRegex(RuntimeError, "GBT_REGISTER_READ_FAILED"):
            self.ns["read_r"](self.arm, [1])

    def controller_empty(self):
        # GBT-S6A-600 / 1.5.7 实机空 R/PR 返回；不能用通用 -254 放行。
        return SimpleNamespace(name="REG_MANAGER_INVALID_ARG", code=-254,
                               errmsg={"inner_code": "0001000200A40007", "name": "REG_MANAGER_INVALID_ARG"})

    def test_controller_empty_range_keeps_later_rows(self):
        self.reg.read_R.side_effect = lambda i: (42, 0) if i == 20 else (None, self.controller_empty())
        self.assertEqual(self.ns["read_r"](self.arm, list(range(1, 21))),
                         [{"type": "R", "ID": 20, "value": 42.0}])
        self.reg.read_PR.return_value = (None, self.controller_empty())
        self.assertEqual(self.ns["read_pr"](self.arm, [50]), [])

    def test_controller_empty_allows_new_r_and_pr(self):
        self.reg.read_R.return_value = (None, self.controller_empty())
        self.assertEqual(self.ns["write_r"](self.arm, {"ID": 50, "value": 5}, "skip"), (True, "write"))
        pose = object()
        self.ns["build_pose_register_from_row"] = MagicMock(return_value=pose)
        self.reg.read_PR.return_value = (None, self.controller_empty())
        self.assertEqual(self.ns["write_pr"](self.arm, {"ID": 50}, "skip"), (True, "write"))
        self.reg.write_PR.assert_called_once_with(pose)

    def test_other_controller_errors_and_p_errors_still_abort(self):
        for status in (SimpleNamespace(name="OTHER_ERROR", code=-254, errmsg={}),
                       SimpleNamespace(name="REG_MANAGER_INVALID_ARG", code=-254, errmsg={"inner_code": "other"}),
                       SimpleNamespace(name="REG_MANAGER_INVALID_ARG", code=-254, errmsg="invalid")):
            with self.assertRaisesRegex(RuntimeError, "GBT_REGISTER_READ_FAILED"):
                self.ns["ensure_read_status"](status)
        with self.assertRaisesRegex(RuntimeError, "GBT_REGISTER_READ_FAILED"):
            self.ns["ensure_read_status"](self.controller_empty(), program_pose=True)

    def test_all_restored_stops_after_ten_empty_ids(self):
        for reg_type in ("R", "PR"):
            self.ns["read_" + reg_type.lower()] = MagicMock(side_effect=lambda arm, ids: [{"ID": ids[0]}] if ids[0] in (1, 10, 21) else [])
            result = self.ns["read_preview"]({"controller_ip": "isolated"}, {"registerType": reg_type, "selector": {"mode": "all"}})
            self.assertEqual(result["rows"], [{"ID": 1}, {"ID": 10}])
            self.assertEqual(self.ns["read_" + reg_type.lower()].call_count, 20)

    def test_all_does_not_turn_network_error_into_scan_end(self):
        self.reg.read_R.side_effect = [(1, 0), (None, 99)]
        with self.assertRaisesRegex(RuntimeError, "GBT_REGISTER_READ_FAILED"):
            self.ns["read_preview"]({"controller_ip": "isolated"}, {"registerType": "R", "selector": {"mode": "all"}})

    def test_r5_to_r10_gap_survives_range_all_and_excel_export(self):
        from openpyxl import Workbook, load_workbook
        self.ns.update(Workbook=Workbook, Path=Path)
        self.reg.read_R.side_effect = lambda i: (i + 0.125, 0) if i in (5, 10) else (None, self.controller_empty())
        for mode in ("range", "all"):
            rows = self.ns["read_preview"]({"controller_ip": "isolated"}, {
                "registerType": "R", "selector": {"mode": mode, "startId": 5, "endId": 10}})["rows"]
            self.assertEqual([r["ID"] for r in rows], [5, 10])
            output = Path(__file__).resolve().parents[2] / ".local-testing" / ("isolated-r5-r10-" + mode + ".xlsx")
            self.ns["export_excel"]("R", rows, str(output))
            wb = load_workbook(output, read_only=True, data_only=True)
            try:
                self.assertEqual(list(wb.active.values), [("type", "ID", "value"), ("R", 5, 5.125), ("R", 10, 10.125)])
            finally:
                wb.close()

    def test_nine_empty_ids_continue_but_ten_stop_all_only(self):
        for later, expected_all in ((15, [5, 15]), (16, [5])):
            self.reg.read_R.side_effect = lambda i: (i, 0) if i in (5, later) else (None, self.controller_empty())
            self.assertEqual([r["ID"] for r in self.ns["read_registers_all_scan"](self.arm, "R")], expected_all)
            self.assertEqual([r["ID"] for r in self.ns["read_r"](self.arm, list(range(5, later + 1)))], [5, later])

    def test_unknown_read_mode_rejected_before_connect(self):
        with self.assertRaisesRegex(RuntimeError, "GBT_RANGE_REQUIRED"):
            self.ns["read_preview"]({"controller_ip": "isolated"}, {"registerType": "R", "selector": {"mode": "bad"}})
        self.ns["connect_arm"].assert_not_called()

    def test_invalid_ranges_rejected(self):
        for first, last in ((-1, 10), (1.5, 10), (1, 10001), (10, 1)):
            with self.assertRaisesRegex(RuntimeError, "GBT_INVALID_REGISTER_DATA"):
                self.ns["build_indexes"]({"startId": first, "endId": last})


if __name__ == "__main__":
    unittest.main()
