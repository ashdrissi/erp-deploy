# Finance Account Governance

## Goal
- Keep native ERPNext finance documents visible and usable: Sales Invoice, Purchase Invoice, and Payment Entry.
- Keep backend accounts and Cost Centers technical and minimal per Company.
- Only superadmin roles manage accounts, Cost Centers, or their backend fields.
- Business reporting should use Company, Project, Sales Order, CRM Business Type, and CRM Segment instead of a large chart of accounts.

## Access Rule
- Superadmin roles: `Administrator`, `System Manager`, `Developer`.
- Superadmins can create/edit `Account` and `Cost Center` records and backend finance fields.
- Business users, including `Orderlift Admin`, cannot create/edit backend accounts or Cost Centers.

## Default Accounts Per Company
When Company finance defaults are ensured, Orderlift creates or resolves a minimal account set where possible.
This runs for new/updated Companies and during `after_migrate` for existing active non-group Companies.

- Accounts Receivable
- Accounts Payable
- Bank
- Cash
- Sales Revenue
- Purchases / COGS
- Operating Expenses
- Salary Expense
- Payroll Payable
- VAT Input
- VAT Output
- Rounding / Write Off

Do not create accounts per project, sales order, business type, CRM segment, customer, supplier, or employee.

## Default Cost Center Per Company
- Orderlift resolves or creates one non-group default Cost Center per active non-group Company, preferring `Main - ABBR`.
- The Company default Cost Center is set when the field exists.
- Do not use Cost Center as a business reporting dimension or create Cost Centers per project, sales order, business type, CRM segment, customer, supplier, or employee.

## Document Behavior
- Sales Invoice defaults `debit_to` and item income/expense accounts from Company setup.
- Purchase Invoice defaults `credit_to` and item expense accounts from Company setup.
- Payment Entry defaults customer receive payments to receivable + bank/cash, and supplier pay payments to bank/cash + payable.
- Sales Order, Sales Invoice, Purchase Invoice, and Payment Entry rows default Cost Center from Company setup.
- For non-superadmins, account and Cost Center fields are hidden/read-only in the form and protected server-side after save.
- For non-superadmins, any same-company account or Cost Center manually supplied through API/import is reset to the Company default during validation.

## Missing Setup
If required Company accounts or Cost Center are missing, finance document validation blocks submission with:

`Company accounting setup is incomplete ... Contact Superadmin.`

## Reporting Direction
Custom finance dashboards should calculate from documents and context:

- Sales Order = booked amount
- Sales Invoice = invoiced amount
- Payment Entry = paid/collected amount
- Purchase Invoice = supplier/project cost
- HR allocation = project labor cost
- Other cost = project/company operating cost

Reports should filter by Company, Project, Sales Order, CRM Business Type, CRM Segment, Customer/Supplier, and period.

The `Sale Financial Dashboard` is the operational business-finance view for this model. It filters by Company, CRM Business Type, CRM Segment, transaction currency, Sales Order status, Project status, date range, and text search while keeping backend Account and Cost Center structure hidden from business users.
