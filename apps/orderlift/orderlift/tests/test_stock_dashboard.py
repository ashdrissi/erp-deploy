import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2]
PY_SOURCE = (APP_ROOT / "orderlift/orderlift_logistics/page/stock_dashboard/stock_dashboard.py").read_text()
JS_SOURCE = (APP_ROOT / "orderlift/orderlift_logistics/page/stock_dashboard/stock_dashboard.js").read_text()
ACC_SOURCE = (APP_ROOT / "orderlift/orderlift/page/access_command_center/access_command_center.py").read_text()


class TestStockDashboard(unittest.TestCase):
    def test_dashboard_resolves_active_company_server_side(self):
        self.assertIn("company = resolve_current_company(user=user)", PY_SOURCE)
        self.assertIn("requested_company != company", PY_SOURCE)
        self.assertIn('warehouse_filters["company"] = company', PY_SOURCE)

    def test_empty_stock_scope_fails_closed(self):
        self.assertIn("if not company or not allowed_warehouses:", PY_SOURCE)
        self.assertIn('"warehouses": [],', PY_SOURCE)
        self.assertIn('return " AND 1 = 0"', PY_SOURCE)

    def test_dashboard_exposes_read_only_drill_down_apis(self):
        for marker in (
            "def get_item_stock_details(",
            "def get_stock_movement_history(",
            "def get_stock_entry_history(",
            "def get_stock_entry_details(",
        ):
            self.assertIn(marker, PY_SOURCE)

    def test_valuation_is_conditionally_serialized(self):
        self.assertIn('"can_view_valuation": can_manage_stock_rates(user)', PY_SOURCE)
        self.assertIn('if context.get("can_view_valuation"):', PY_SOURCE)
        self.assertNotIn('payload = {"valuation_rate":', PY_SOURCE)

    def test_cancelled_stock_ledger_rows_are_excluded(self):
        self.assertIn('conditions = ["sle.is_cancelled = 0"]', PY_SOURCE)

    def test_stock_overview_sorting_uses_allowlist(self):
        self.assertIn("STOCK_OVERVIEW_SORTS = {", PY_SOURCE)
        self.assertIn("STOCK_OVERVIEW_SORTS.get", PY_SOURCE)
        self.assertIn("MOVEMENT_SORTS.get", PY_SOURCE)

    def test_item_click_opens_custom_detail_dialog(self):
        self.assertIn("openItemDetailDialog(page, item, warehouse)", JS_SOURCE)
        self.assertNotIn('routeStockReport("Stock Balance"', JS_SOURCE)

    def test_custom_read_only_history_dialogs_are_wired(self):
        self.assertIn("openMovementHistoryDialog({})", JS_SOURCE)
        self.assertIn("openStockEntryHistoryDialog({})", JS_SOURCE)
        self.assertIn("get_stock_entry_details", JS_SOURCE)

    def test_removed_stock_shortcuts_stay_removed(self):
        self.assertNotIn('scut("cart", __("Reorder Levels")', JS_SOURCE)
        self.assertNotIn('scut("rotate", __("Stock Balance (Qty)")', JS_SOURCE)
        self.assertNotIn('data-stock-route="stock-balance">${__("Open Stock Balance")}', JS_SOURCE)

    def test_available_quantity_label_is_explicit(self):
        self.assertIn('label: __("Available After SO")', JS_SOURCE)
        self.assertIn('${__("Available After SO")}', JS_SOURCE)
        self.assertIn("get_effective_demand_by_item", PY_SOURCE)
        self.assertIn("actual_qty - demand_qty", PY_SOURCE)

    def test_sorting_is_wired_to_column_headers(self):
        self.assertIn("function sortableStockHeader", JS_SOURCE)
        self.assertIn('data-stock-sort-column="${field}"', JS_SOURCE)
        self.assertNotIn("data-stock-sort-dir", JS_SOURCE)

    def test_header_uses_daily_document_actions(self):
        self.assertIn('__("New Purchase Receipt")', JS_SOURCE)
        self.assertIn('__("New Delivery Note")', JS_SOURCE)
        self.assertIn('__("New Stock Entry")', JS_SOURCE)
        self.assertNotIn('__("New Transfer")', JS_SOURCE)

    def test_stock_balance_header_is_compact(self):
        self.assertIn('__("Stock Balance")', JS_SOURCE)
        self.assertIn('class="sdb-stock-head-actions"', JS_SOURCE)
        self.assertNotIn('Current quantities from ERPNext Bin.', JS_SOURCE)

    def test_warehouse_metric_is_not_labeled_as_physical_capacity(self):
        self.assertIn('__("Stocked Item Coverage")', JS_SOURCE)
        self.assertNotIn('__("Capacity")', JS_SOURCE)

    def test_access_command_center_has_stock_backing_doctypes(self):
        self.assertIn(
            '"stock.dashboard": ("Bin", "Item", "Warehouse", "Stock Ledger Entry", "Stock Entry", "Stock Demand Plan")',
            ACC_SOURCE,
        )

    def test_confirmed_order_planning_is_visible(self):
        self.assertIn('"stock_planning": stock_planning', PY_SOURCE)
        self.assertIn("def _get_stock_demand_planning", PY_SOURCE)
        self.assertIn('__("Confirmed Order Stock Planning")', JS_SOURCE)
        self.assertIn('/app/stock-planning-settings-control', JS_SOURCE)
        self.assertIn("renderStockPlanning(page, d.stock_planning || {})", JS_SOURCE)


if __name__ == "__main__":
    unittest.main()
