# QC, Native QI, and SAV Ticket Linkage

## Overview

Three separate quality-related systems exist in the Orderlift deployment. They solve different problems and should remain decoupled, with SAV Ticket as the sole bridge between them.

## The Three Systems

### 1. SIG QC — Custom Installation Checklists

**Domain:** Field installation process quality

- Lives on `Project.custom_qc_checklist` (child table: Installation QC Item)
- Uses `QC Checklist Template` for pre-built templates
- Purpose: Technicians verify installation steps — bolt torque, alignment, electrical checks, site cleanliness
- Workflow: Project created → checklist populated from template → technician fills on-site → `compute_qc_status()` sets pass/fail
- Key file: `orderlift_sig/utils/project_qc.py`
- Current state: 2 QC Checklist Templates configured

**Answers:** "Was the installation done correctly?"

### 2. Native ERPNext Quality Inspection — Stock Acceptance/Rejection

**Domain:** Physical goods quality

- Standard ERPNext DocTypes: `Quality Inspection` + `Quality Inspection Template`
- Purpose: Inspect goods on receipt (Purchase Receipt) or dispatch (Delivery Note) — dimensions, material defects, quantity variance
- Workflow: Stock transaction triggers QI → inspector records measurements → accepted/rejected → stock movement completes
- Current state: 0 records. Not yet active.

**Answers:** "Is this physical part acceptable?"

### 3. SAV Ticket — Customer Complaints / After-Service

**Domain:** Customer-facing issue tracking

- Custom DocType: `SAV Ticket`
- Already has linkage fields:
  - `quality_inspection` — Link to Quality Inspection
  - `quality_inspection_template` — Link to Quality Inspection Template
- Purpose: Track customer complaints, warranty claims, defect investigations, corrective actions
- Dashboard: `SAV Dashboard` page with KPIs, defect breakdowns, recurring issues, warranty exposure

**Answers:** "What did the customer complain about and what is the root cause?"

## Linkage Architecture

```
┌─────────────────────┐
│  SIG QC (Project)   │  ← installation process quality
│  custom_qc_checklist│
└──────────┬──────────┘
           │ failed checklist → defect found
           │
           ▼
┌─────────────────────┐     ┌──────────────────────┐
│   SAV Ticket        │────→│ Native QI            │
│  (complaint/claim)  │     │ (stock defect)        │
│                     │←────│ Quality Inspection    │
│  - warranty check   │     └──────────────────────┘
│  - root cause       │
│  - corrective action│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Project (SIG)      │  ← corrective installation
│  Installation QC    │  ← re-inspection after fix
└─────────────────────┘
```

**Design principle:** SIG QC and Native QI never talk to each other directly. SAV Ticket is the only bridge. This keeps domain boundaries clean and avoids tangled N×N dependencies.

## Flow Scenarios

### Scenario A — Installation Defect

1. Project QC checklist fails (e.g., "motor alignment" marked fail)
2. SAV Ticket created from Project → linked via `project` field
3. Technician dispatched → fixes issue → re-runs QC checklist → passes
4. SAV Ticket closed with resolution notes

### Scenario B — Stock/Part Defect

1. Customer reports broken part
2. SAV Ticket created → `quality_inspection` field links to a new Quality Inspection record
3. QI confirms defect → rejected part → replacement shipped via Delivery Note
4. SAV Ticket tracks full chain: complaint → QI → replacement → customer confirmation

### Scenario C — Mixed (Installation + Stock)

1. SAV Ticket opened for "machine not working"
2. Investigation reveals: bad part (stock QI) + wrong installation (SIG QC)
3. SAV Ticket links to both Quality Inspection and Project QC checklist
4. Root cause traced: defective batch from supplier → triggers supplier complaint

## Proposed Implementation Plan

### Phase 1 — Foundation (Prerequisites)

1. Create at least one QI Template on a test Item
2. Run a Purchase Receipt or Delivery Note through the native QI flow
3. Verify QI records are created and linked correctly
4. Add Quality Inspection and Quality Inspection Template to Main Dashboard sidebar (Warehouse & Stock section)

### Phase 2 — SAV → QI Auto-Creation

1. Add server-side hook on SAV Ticket creation or defect type selection
2. When defect involves a physical part, auto-create a Quality Inspection record
3. Populate SAV Ticket's `quality_inspection` field with the new QI record
4. Respect warranty boundary: non-warranty tickets should not auto-create QI (customer-paid repairs, not product defects)
5. Key files to modify:
   - `orderlift_sav/doctype/sav_ticket/sav_ticket.py` — on_validate or before_insert hook
   - `orderlift_sav/doctype/sav_ticket/auto_fill.py` — QI creation logic

### Phase 3 — SAV → Project QC Visibility

1. When SAV defect traces back to installation, link the `project` field
2. Surface failed QC checklist items in the SAV Ticket form view
3. Optionally add a "Re-inspection" button that triggers a new QC checklist on the linked Project

### Phase 4 — Dashboard Cross-References

1. Add root cause breakdown to SAV Dashboard: stock quality vs installation quality vs other
2. Add linked_executions section showing connected QI records and Project QC results
3. Track MTTR (mean time to resolution) split by root cause type

## Warnings and Gotchas

- **QI is not active yet** (0 records). Do not build SAV→QI linkage until at least one test flow works end-to-end. Otherwise it's dead code.
- **SAV Ticket's `quality_inspection` field exists but has no population logic.** It's a Link field waiting to be wired.
- **Warranty boundary matters.** Non-warranty SAV tickets are customer-paid. Auto-creating QI for those conflates product defects with wear-and-tear.
- **Don't merge QC systems.** SIG QC (process) and Native QI (product) serve different domains. Merging them fights ERPNext's stock flow and overcomplicates the installation checklist.
- **Dashboard value depends on data.** Root cause split is useful only after you have real SAV Tickets flowing through the system.

## Related Files

| File | Purpose |
|------|---------|
| `orderlift_sig/utils/project_qc.py` | SIG QC population, save, status computation |
| `orderlift_sav/doctype/sav_ticket/sav_ticket.json` | SAV Ticket DocType definition (has quality_inspection fields) |
| `orderlift_sav/doctype/sav_ticket/sav_ticket.py` | SAV Ticket server logic |
| `orderlift_sav/doctype/sav_ticket/auto_fill.py` | Auto-fill logic (warranty, customer tier, transaction date) |
| `orderlift_sav/page/sav_dashboard/sav_dashboard.py` | Dashboard backend (KPIs, breakdowns) |
| `orderlift_sav/page/sav_dashboard/sav_dashboard.js` | Dashboard frontend rendering |
