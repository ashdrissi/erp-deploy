import json
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2]
MANAGER_JS = (
    APP_ROOT
    / "orderlift"
    / "orderlift_sales"
    / "page"
    / "sale_financial_dashboard"
    / "sale_financial_dashboard.js"
)
MANAGER_JSON = MANAGER_JS.with_suffix(".json")
DETAIL_JS = (
    APP_ROOT
    / "orderlift"
    / "orderlift_finance"
    / "page"
    / "sale_financial_workspace"
    / "sale_financial_workspace.js"
)
DETAIL_JSON = DETAIL_JS.with_suffix(".json")
SHARED_CSS = APP_ROOT / "orderlift" / "public" / "css" / "financial_workspace_20260815c.css"
MODULES = APP_ROOT / "orderlift" / "modules.txt"
MENU_ACCESS = APP_ROOT / "orderlift" / "menu_access.py"
ROLE_SETUP = APP_ROOT / "orderlift" / "scripts" / "setup_startup_roles.py"
MANAGER_PY = MANAGER_JS.with_suffix(".py")


class TestFinancialWorkspaceFrontend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manager = MANAGER_JS.read_text()
        cls.detail = DETAIL_JS.read_text()
        cls.css = SHARED_CSS.read_text()
        cls.menu_access = MENU_ACCESS.read_text()
        cls.role_setup = ROLE_SETUP.read_text()

    def test_manager_preserves_route_and_uses_cash_flow_portfolio_contract(self):
        self.assertIn('frappe.pages["sale-financial-dashboard"]', self.manager)
        self.assertIn(
            '"orderlift.orderlift_finance.cash_flow.get_portfolio_data"',
            self.manager,
        )
        self.assertIn("filters: JSON.stringify(STATE.filters)", self.manager)
        self.assertNotIn("get_dashboard_data", self.manager)
        for key in (
            "summary",
            "profitability_rows",
            "cash_flow_rows",
            "project_rows",
            "standalone_order_rows",
            "customer_rows",
            "monthly_rows",
            "data_quality_rows",
        ):
            self.assertIn(key, self.manager)

    def test_manager_has_required_views_filters_and_summary_metrics(self):
        for label in (
            "Overview",
            "Profitability",
            "Projects",
            "Standalone Orders",
            "Customers",
            "Cash Flow",
            "Monthly",
            "Data Quality",
            "Collected",
            "Paid",
            "Net",
            "Funding Gap",
            "At Risk",
            "Overdue",
            "Completeness",
            "Expected Profit",
        ):
            self.assertIn(label, self.manager)
        filter_block = self.manager.split("const FILTER_KEYS = [", 1)[1].split("];", 1)[0]
        for key in (
            "search",
            "status",
            "customer",
            "project_type",
            "business_type",
            "segment",
            "risk_status",
            "revenue_forecast_status",
            "cost_forecast_status",
            "currency",
            "horizon",
            "from_date",
            "to_date",
        ):
            self.assertIn(f'"{key}"', filter_block)
        self.assertNotIn('"company"', filter_block)
        self.assertIn('params.delete("company")', self.manager)
        self.assertIn('"workflow_statuses"', self.manager)
        self.assertIn("horizonLabel(data)", self.manager)
        self.assertIn('return __("13W")', self.manager)
        self.assertIn('return __("12M")', self.manager)
        self.assertIn('return __("Lifetime")', self.manager)

    def test_primary_cell_actions_route_supported_contexts_and_customers(self):
        self.assertIn('frappe.set_route("sale-financial-workspace"', self.manager)
        self.assertIn('contextType: "project"', self.manager)
        self.assertIn('contextType: "sales_order"', self.manager)
        self.assertIn('documentType: "Customer"', self.manager)
        self.assertIn('frappe.set_route("Form", doctype, name)', self.manager)
        self.assertIn('class="ofw-primary-action" data-open-context', self.manager)
        self.assertIn('class="ofw-primary-action" data-open-document', self.manager)
        self.assertNotIn('role="link"', self.manager)
        self.assertNotIn('<tr ${open}>', self.manager)

    def test_detail_page_uses_route_or_query_context_and_detail_contract(self):
        self.assertIn('frappe.pages["sale-financial-workspace"]', self.detail)
        self.assertIn(
            '"orderlift.orderlift_finance.cash_flow.get_cash_flow_detail"',
            self.detail,
        )
        self.assertIn('route[1] || readQuery("context_type")', self.detail)
        self.assertIn('route[2] || readQuery("context_name")', self.detail)
        for argument in ("context_type", "context_name", "horizon", "from_date", "to_date"):
            self.assertIn(f"{argument}:", self.detail)
        for key in (
            "identity",
            "kpis",
            "profitability",
            "buckets",
            "events",
            "receivables",
            "payables",
            "documents",
            "alerts",
            "data_quality",
        ):
            self.assertIn(key, self.detail)
        self.assertIn('params.delete("company")', self.detail)
        self.assertIn('horizon: readQuery("horizon") || "13_weeks"', self.detail)
        self.assertIn("syncStateFromLocation()", self.detail)

    def test_detail_has_required_views_chart_ledger_alerts_and_source_actions(self):
        for label in (
            "Overview",
            "Profitability",
            "Cash Flow",
            "Receivables",
            "Payables & Commitments",
            "Documents",
            "Data Quality",
            "Decision Alerts",
            "Event Ledger",
            "Expected Profit",
            "Actual Profit to Date",
        ):
            self.assertIn(label, self.detail)
        self.assertIn("<svg viewBox=", self.detail)
        self.assertIn("This table is the text alternative for the chart.", self.detail)
        self.assertIn("boundedEvents(data)", self.detail)
        self.assertIn("bucket.events", self.detail)
        self.assertIn("Overdue carried forward", self.detail)
        self.assertIn("Overdue commitments are carried into the first selected period.", self.detail)
        self.assertIn("intervalTerms(data)", self.detail)
        self.assertIn('interval.singular', self.detail)
        self.assertIn('interval.adjective', self.detail)
        self.assertNotIn("Exact weekly values", self.detail)
        self.assertIn('class="ofw-alerts"', self.detail)
        self.assertIn('data-open-document', self.detail)
        self.assertIn('frappe.set_route("Form"', self.detail)
        self.assertIn("moneyFocusPanel", self.detail)
        self.assertIn("profitabilityPanel", self.detail)
        self.assertIn("set_forecast_finality", self.detail)
        self.assertIn('data-set-forecast="${key}"', self.detail)

    def test_overviews_use_compact_focus_lists_instead_of_split_wide_tables(self):
        self.assertIn("focusPanel(projects", self.manager)
        self.assertIn("focusPanel(orders", self.manager)
        self.assertIn('class="ofw-focus-row"', self.manager)
        self.assertIn('class="ofw-money-row"', self.detail)
        self.assertIn("hideFrappeHeader(wrapper)", self.manager)
        self.assertIn("hideFrappeHeader(wrapper)", self.detail)
        self.assertIn(".ofw-overview-grid", self.css)
        self.assertIn("align-items: start", self.css)
        self.assertIn("text-overflow: ellipsis", self.css)
        self.assertIn(".ofw-finance-groups", self.css)
        self.assertIn(".ofw-closure-grid", self.css)
        self.assertIn(".ofw-incomplete", self.css)
        self.assertIn('__("Incomplete")', self.manager)
        self.assertIn('__("Incomplete")', self.detail)

    def test_pages_share_permissions_and_scoped_dynamic_stylesheet(self):
        manager_page = json.loads(MANAGER_JSON.read_text())
        detail_page = json.loads(DETAIL_JSON.read_text())
        manager_roles = {row["role"] for row in manager_page["roles"]}
        detail_roles = {row["role"] for row in detail_page["roles"]}

        self.assertEqual(detail_roles, manager_roles)
        self.assertEqual(
            manager_roles,
            {"Orderlift Admin", "System Manager", "Finance User", "Finance Admin"},
        )
        self.assertEqual(detail_page["name"], "sale-financial-workspace")
        self.assertEqual(detail_page["module"], "Orderlift Finance")
        self.assertIn("Orderlift Finance", MODULES.read_text().splitlines())
        self.assertIn(
            '"sale-financial-workspace": "finance.sale_financial_dashboard"',
            self.menu_access,
        )
        self.assertIn(
            'PAGE_ROLES = ("Orderlift Admin", "System Manager", "Finance User", "Finance Admin")',
            MANAGER_PY.read_text(),
        )
        executive_block = self.role_setup.split('"Orderlift Executive": [', 1)[1].split("],", 1)[0]
        self.assertNotIn('"finance.sale_financial_dashboard"', executive_block)
        self.assertIn('"finance.sales_payment_follow_up"', executive_block)
        for source in (self.manager, self.detail):
            self.assertIn("financial_workspace_20260815c.css", source)
            self.assertIn('document.createElement("link")', source)
            self.assertIn('link.rel = "stylesheet"', source)
        self.assertIn(".ofw-root", self.css)
        self.assertNotIn("backdrop-filter", self.css)

    def test_accessibility_responsiveness_and_explicit_states_are_present(self):
        for source in (self.manager, self.detail):
            self.assertIn('aria-pressed="${active}"', source)
            self.assertNotIn('aria-controls=', source)
            self.assertNotIn('role="tabpanel"', source)
            self.assertIn("ArrowRight", source)
            self.assertIn("ArrowLeft", source)
            self.assertIn('aria-live="polite"', source)
            self.assertIn('aria-busy="${STATE.loading ? "true" : "false"}"', source)
            self.assertIn("skeleton()", source)
            self.assertIn("emptyState(", source)
            self.assertIn("errorState()", source)
            self.assertIn('data-refresh', source)
        self.assertIn("@media (max-width: 900px)", self.css)
        self.assertIn("@media (max-width: 767px)", self.css)
        self.assertIn("min-height: 44px", self.css)
        self.assertIn(":focus-visible", self.css)
        self.assertIn("prefers-reduced-motion", self.css)
        self.assertIn("overflow-x: hidden", self.css)
        self.assertIn("position: sticky", self.css)
        self.assertIn(".ofw-primary-action", self.css)
        self.assertIn(".ofw-chart-plot", self.css)
        self.assertIn("min-width: 720px", self.css)

    def test_request_state_empty_state_completeness_and_html_sinks_are_guarded(self):
        for source in (self.manager, self.detail):
            self.assertIn("requestGeneration", source)
            self.assertIn("requestGeneration !== STATE.requestGeneration", source)
            self.assertIn("syncStateFromLocation()", source)
            self.assertIn("safeRouteName", source)
            self.assertIn("safeDoctype", source)
        self.assertIn("function hasPortfolioData(data)", self.manager)
        self.assertNotIn("Boolean(data.summary", self.manager)
        self.assertIn("completenessMetric(data, aliases)", self.detail)
        self.assertIn("data.kpis || {}, data.identity || {}, data", self.detail)
        self.assertIn("return (data.data_quality || []).length ? 0 : 100", self.detail)
        self.assertIn("(data.data_quality || []).length", self.detail)
        self.assertIn("function safeTitle", self.detail)
        self.assertIn("function moneyText", self.detail)
        self.assertIn("function money(value, currency) { return esc(moneyText", self.detail)
        self.assertIn("return esc(`${code} ${number(amount)}`.trim())", self.manager)

    def test_data_quality_rows_offer_validated_source_actions(self):
        self.assertIn('column("source", "Source Record"', self.manager)
        self.assertIn('col("document", "Document"', self.detail)
        for source in (self.manager, self.detail):
            self.assertIn('data-open-document', source)
            self.assertIn("SOURCE_DOCTYPES", source)


if __name__ == "__main__":
    unittest.main()
