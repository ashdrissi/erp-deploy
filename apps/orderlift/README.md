# orderlift

Custom Frappe app for Orderlift ERP — developed by Syntax Line.

Provides the active custom modules on top of ERPNext:
- Item Master extensions (cost history, logistics fields)
- Sales commissions & market price tracking
- Logistics intelligence (container/truck optimizer)
- Branded PDF print formats
- Analytics dashboards & reports

Current delivery focus:
- Active modules: Sales/Pricing, Logistics, analytics dashboards, branded UX, invite-only B2B portal, and dashboard operations hubs
- Roadmap modules for now: CRM business workflows, SAV advanced SLA workflow, SIG, and HR advanced extensions

## Installation

```bash
bench get-app /path/to/orderlift
bench --site erp.ecomepivot.com install-app orderlift
bench --site erp.ecomepivot.com migrate
bench build --app orderlift
```
