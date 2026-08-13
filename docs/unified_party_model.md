# Unified Party Model

Lead, Prospect, and Customer use the same Orderlift party structure. Users choose
the doctype manually; business type does not force Lead or Prospect.

## Shared Data

- `custom_company` is the primary internal company on all three doctypes.
- `custom_internal_company_access` lists every approved internal company that may
  use the party.
- Customer uses native `tax_id`; Lead and Prospect use `custom_tax_id`. All are
  labelled `ICE / Tax ID` in the form.
- Contacts and addresses remain native Frappe `Contact` and `Address` records
  linked through Dynamic Link rows.

## Forms

The shared party form script groups these actions on Lead, Prospect, and Customer:

- Create Opportunity
- Add Address
- Add Contact
- Check Duplicates
- Convert to Customer (Lead and Prospect)

The inline address popup supports billing, shipping, and site/installation flags.
Site addresses flow through Opportunity, Pricing Sheet, Quotation, Sales Order,
Delivery Note, Sales Invoice, and Project where those documents expose the field.

## Conversion

Lead/Prospect conversion reuses an existing Customer by linked lineage, ICE/Tax ID,
or exact customer name before creating a new Customer. It copies CRM segments,
internal companies, ICE/Tax ID, Contacts, and Addresses.

Sales Orders created from Quotations enforce one compatible source party and use
the converted Customer. Projects inherit Customer, source Opportunity, CRM
classification, ICE/Tax ID, and site address from Sales Order or Opportunity.

## Company Access Requests

Cross-company reuse is requested through `Party Company Access Request`. Approval
requires the `party_company_access_approval` role capability and must be completed
by a user other than the requester.
