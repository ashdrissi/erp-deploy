# orderlift

Custom Frappe app for Orderlift ERP — developed by Syntax Line.

Provides all custom modules on top of ERPNext v15:
- Item Master extensions (cost history, logistics fields)
- Sales commissions & market price tracking
- B2B client portal with dynamic pricing
- Logistics intelligence (container/truck optimizer)
- CRM with configurable stage notifications
- SAV (after-sales service) ticketing
- SIG (geo-location & project tracking)
- HR extensions
- Branded PDF print formats
- Analytics dashboards & reports

## Installation

```bash
bench get-app /path/to/orderlift
bench --site erp.ecomepivot.com install-app orderlift
bench --site erp.ecomepivot.com migrate
bench build --app orderlift
```
