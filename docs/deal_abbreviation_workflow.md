# Deal Abbreviation Workflow

## Purpose

`custom_deal_abbreviation` is an optional short code that identifies one commercial deal across CRM, sales, projects, logistics, purchasing, stock, invoicing, and SAV documents.

## Entry And Editing

- Enter 2 to 12 letters or numbers on the Opportunity. The value is stored in uppercase.
- Opportunity is the authoritative source.
- Sales Order and Project may edit the value when linked to exactly one readable Opportunity. The edit updates that Opportunity and its related documents.
- Other related documents show the value read-only.
- `MIXED` is reserved for documents linked to Opportunities with different deal abbreviations.

## Naming

New related documents append the code to their normal ERPNext name:

```text
CRM-OPP-2026-dist-00001~ABC
SAL-QTN-2026-00001~ABC
SAL-ORD-2026-00001~ABC
PUR-ORD-2026-00001~ABC
```

Existing document names are not changed when a code is entered or edited. Their top-panel `Deal / CODE` flag and stored field show the current value.

## Access

The feature does not grant access, create shares, or change company/ownership permission filters. Users only see the flag on documents they can already open. Sales Order and Project edit-back requires write access to that anchor document and read access to its single source Opportunity.
