# Finance Account Governance

## Goal
- Keep native ERPNext finance documents visible and usable: Sales Invoice, Purchase Invoice, and Payment Entry.
- Keep backend accounts and Cost Centers technical and minimal per Company.
- Only superadmin roles manage accounts, Cost Centers, or their backend fields.
- Business reporting should use Company, Project, Sales Order, CRM Business Type, and CRM Segment instead of a large chart of accounts.

## Access Rule
- Superadmin identities: built-in `Administrator` and the `System Manager` role.
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
- A paid Purchase Invoice requires only a Mode of Payment; its hidden cash/bank account is resolved from the selected Mode of Payment and Company defaults.
- An unpaid Purchase Invoice remains outstanding and can be settled later through a Payment Entry.
- Payment Entry defaults customer receive payments to receivable + bank/cash, and supplier pay payments to bank/cash + payable.
- Payment Entry preserves a valid same-company party account selected from the source document. The selected Mode of Payment account remains authoritative for the bank/cash side.
- Sales Order, Sales Invoice, Purchase Invoice, and Payment Entry rows default Cost Center from Company setup.
- For non-superadmins, account and Cost Center fields are hidden/read-only in the form and protected server-side after save.
- For non-superadmins, backend account and Cost Center values supplied through API/import are normalized during validation. Payment Entry party accounts are retained when they are valid for the selected Company and source document.

## Modes of Payment
- Every enabled Mode of Payment receives one default account row for every Company, including the parent Company.
- Cash modes use the Company's default cash account. Bank and other non-cash modes use the Company's default bank account.
- This setup is maintained when a Company is created or updated and during `after_migrate`.
- `Wire Transfer`, `Bank Draft`, `Cheque`, and `Credit Card` therefore use `Sortie - OL`, `Sortie - OMD`, `Sortie - OMI`, or `Sortie - OTR` according to Company. `Cash` uses the corresponding `Cash - ABBR` ledger.
- Payment Entry resolves the Mode of Payment company row before falling back to Company bank/cash defaults.

## Source-Currency Payments
- Creating a Payment Entry from a Sales Invoice, Purchase Invoice, Sales Order, or Purchase Order carries the source document currency into the payment.
- Users enter `Payment Amount in Source Currency` and may edit `Source to Company Exchange Rate`. The rate means one unit of source currency expressed in Company currency.
- `Converted Amount in Company Currency`, native paid/received amounts, and reference allocations are recalculated before validation and stored in the currencies required by the selected ledgers.
- Partial payments are supported. Same-currency payments always use an exchange rate of `1`.
- All references on one source-currency Payment Entry must use the same currency. Deductions are not supported in this mode and must be recorded separately.

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
