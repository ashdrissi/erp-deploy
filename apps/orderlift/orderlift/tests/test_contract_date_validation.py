import sys
import types
import unittest


def _raise(message, *args, **kwargs):
    raise Exception(message)


frappe_stub = types.ModuleType("frappe")
frappe_stub._ = lambda msg: msg
frappe_stub.throw = _raise

frappe_utils_stub = types.ModuleType("frappe.utils")
frappe_utils_stub.getdate = lambda value: value

sys.modules["frappe"] = frappe_stub
sys.modules["frappe.utils"] = frappe_utils_stub


from orderlift.crm.extensions.contract import ContractDateValidationMixin


class _Contract(types.SimpleNamespace, ContractDateValidationMixin):
    pass


class TestContractDateValidation(unittest.TestCase):
    def test_missing_start_date_does_not_crash(self):
        contract = _Contract(start_date=None, end_date="2026-03-31")
        contract.validate_dates()

    def test_end_date_before_start_date_raises(self):
        contract = _Contract(start_date="2026-04-01", end_date="2026-03-31")

        with self.assertRaisesRegex(Exception, "End Date cannot be before Start Date"):
            contract.validate_dates()

    def test_valid_date_range_passes(self):
        contract = _Contract(start_date="2026-03-01", end_date="2026-03-31")
        contract.validate_dates()


if __name__ == "__main__":
    unittest.main()
