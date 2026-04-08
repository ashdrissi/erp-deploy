import sys
import types
import unittest
from unittest.mock import patch


def _raise(message, *args, **kwargs):
    raise Exception(message)


frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda msg: msg
frappe_stub.whitelist = lambda *args, **kwargs: (lambda fn: fn)
frappe_stub.throw = _raise
frappe_stub.parse_json = lambda value: value
frappe_stub.session = types.SimpleNamespace(user="tech@example.com")
frappe_stub.utils = types.SimpleNamespace(now_datetime=lambda: "NOW")
frappe_stub.get_doc = None
sys.modules["frappe"] = frappe_stub


from orderlift.orderlift_sig.utils import project_qc


class _Row(types.SimpleNamespace):
    pass


class _Project(types.SimpleNamespace):
    def save(self, ignore_permissions=False):
        self.saved = True


class TestSigQcStatus(unittest.TestCase):
    def test_set_qc_status_complete(self):
        project = _Project(custom_qc_checklist=[_Row(is_verified=1, is_mandatory=1), _Row(is_verified=1, is_mandatory=0)])
        project_qc._set_qc_status(project)
        self.assertEqual(project.custom_qc_status, "Complete")

    def test_set_qc_status_blocked(self):
        project = _Project(custom_qc_checklist=[_Row(is_verified=1, is_mandatory=1), _Row(is_verified=0, is_mandatory=1)])
        project_qc._set_qc_status(project)
        self.assertEqual(project.custom_qc_status, "Blocked")

    def test_set_qc_status_not_started_without_rows(self):
        project = _Project(custom_qc_checklist=[])
        project_qc._set_qc_status(project)
        self.assertEqual(project.custom_qc_status, "Not Started")


class TestSigQcPersistence(unittest.TestCase):
    def test_apply_qc_row_state_updates_remarks_and_verification(self):
        row = _Row(is_verified=0, remarks="", verified_by=None, verified_on=None)
        project_qc._apply_qc_row_state(row, is_verified=True, remarks="  checked ok  ", user="tech@example.com", timestamp="NOW")
        self.assertEqual(row.is_verified, 1)
        self.assertEqual(row.remarks, "checked ok")
        self.assertEqual(row.verified_by, "tech@example.com")
        self.assertEqual(row.verified_on, "NOW")

    def test_save_qc_checklist_persists_remarks_and_status(self):
        rows = [
            _Row(name="ROW-1", is_verified=0, is_mandatory=1, remarks="", verified_by=None, verified_on=None),
            _Row(name="ROW-2", is_verified=0, is_mandatory=1, remarks="", verified_by=None, verified_on=None),
        ]
        project = _Project(name="PROJ-1", custom_qc_checklist=rows, custom_qc_status="Not Started", saved=False)

        with patch.object(project_qc.frappe, "get_doc", return_value=project):
            result = project_qc.save_qc_checklist(
                "PROJ-1",
                [
                    {"name": "ROW-1", "is_verified": 1, "remarks": "mandatory done"},
                    {"name": "ROW-2", "is_verified": 0, "remarks": "waiting parts"},
                ],
            )

        self.assertTrue(project.saved)
        self.assertEqual(project.custom_qc_status, "Blocked")
        self.assertEqual(rows[0].remarks, "mandatory done")
        self.assertEqual(rows[0].verified_by, "tech@example.com")
        self.assertEqual(rows[1].remarks, "waiting parts")
        self.assertIsNone(rows[1].verified_by)
        self.assertEqual(result["verified"], 1)
        self.assertEqual(result["total"], 2)

    def test_sync_qc_item_verification_updates_single_row_remarks(self):
        rows = [
            _Row(name="ROW-1", is_verified=0, is_mandatory=0, remarks="", verified_by=None, verified_on=None),
        ]
        project = _Project(name="PROJ-1", custom_qc_checklist=rows, custom_qc_status="Not Started", saved=False)

        with patch.object(project_qc.frappe, "get_doc", return_value=project):
            result = project_qc.sync_qc_item_verification("PROJ-1", "ROW-1", 1, remarks="done")

        self.assertTrue(project.saved)
        self.assertEqual(rows[0].remarks, "done")
        self.assertEqual(rows[0].verified_by, "tech@example.com")
        self.assertEqual(result["qc_status"], "Complete")


if __name__ == "__main__":
    unittest.main()
