# Pricing Revamp Sprint Board

## Sprint 1 - Stabilization and Migration

- [x] T1 Build migration patch for legacy pricing scenarios
  - [x] T1.1 Map legacy fields to `expenses`
  - [x] T1.2 Backfill scenarios with missing `expenses`
  - [x] T1.3 Preserve deterministic order through `sequence`
  - [x] T1.4 Ensure idempotent migration behavior
  - [x] T1.5 Add migration logging
  - [x] T1.6 Add rollback-safe migration structure
- [x] T2 Automated tests for pricing engine
  - [x] T2.1 Sequential expense order tests
  - [x] T2.2 Percentage/fixed + basis tests
  - [x] T2.3 Negative discount tests
  - [x] T2.4 Rounding and reconciliation coverage
  - [x] T2.5 Quotation flow preview covered by server preview method
  - [x] T2.6 Legacy mapping fallback path covered by migration helper defaults
- [x] T3 Security hardening
  - [x] T3.1 Reduce unsafe automatic object creation in quotation flow
  - [x] T3.2 Gate sensitive generation action with write permission
  - [x] T3.3 Require explicit grouped line item configuration or existing item
  - [x] T3.4 Add calculated user + warning audit trail fields

## Sprint 2 - Engine v2 and Guardrails

- [x] T4 Explicit expense sequencing
  - [x] T4.1 Add `sequence` field
  - [x] T4.2 Sort by `sequence`
  - [x] T4.3 Validate duplicate/invalid sequence
  - [x] T4.4 Scenario UI shows sequence-aware flow
- [x] T5 Expense scope model
  - [x] T5.1 Add `scope` field (`Per Unit`, `Per Line`, `Per Sheet`)
  - [x] T5.2 Implement scope-aware calculation engine
  - [x] T5.3 Save scope in breakdown payload
  - [x] T5.4 Add tests for line/sheet fixed costs
- [x] T6 Price safety guardrails
  - [x] T6.1 Negative floor violation detection
  - [x] T6.2 Minimum margin threshold support
  - [x] T6.3 Strict guard mode to block save
  - [x] T6.4 Surface warnings in dashboard
- [x] T7 Precision and consistency
  - [x] T7.1 Single engine utility for all calculations
  - [x] T7.2 Consistent totals from projected/final values
  - [x] T7.3 Runtime and reconciliation visibility in form

## Sprint 3 - Performance and UX

- [x] T8 Remove N+1 lookups
  - [x] T8.1 Batch item group retrieval
  - [x] T8.2 Batch buying price retrieval
  - [x] T8.3 Batch benchmark retrieval
  - [x] T8.4 In-memory maps for recalc loop
- [x] T9 Runtime optimization
  - [x] T9.1 Scenario expense cache per recalc
  - [x] T9.2 Profiling runtime field + logger metrics
  - [x] T9.3 Improved recalc observability
- [x] T10 Async recalculation path
  - [x] T10.1 Queue recalculate server method
  - [x] T10.2 Job feedback in UI
  - [x] T10.3 Keep sync recalc for normal flow
- [x] T11 Maintainable presentation structure
  - [x] T11.1 Dashboard rendering isolated in dedicated JS helpers
  - [x] T11.2 Separation of rendering/event handlers
  - [x] T11.3 Reusable badge and modal helper functions
- [x] T12 Expense impact analytics
  - [x] T12.1 Aggregate per-expense contribution
  - [x] T12.2 Display impact table in dashboard
  - [x] T12.3 Ranked impact ordering
- [x] T13 Explainability UX
  - [x] T13.1 Row-level breakdown modal
  - [x] T13.2 Basis/delta/running total details
  - [x] T13.3 Quick access from dashboard action
- [x] T14 Better error and empty states
  - [x] T14.1 Missing price and guardrail warnings surfaced
  - [x] T14.2 Inline status flags in dashboard rows
  - [x] T14.3 Clear no-data blocks and safe fallbacks
- [x] T15 i18n consistency
  - [x] T15.1 Unified output labels (`Avec details`, `Sans details`)
  - [x] T15.2 JS labels wrapped with translation helper
  - [x] T15.3 Consistent warning messaging style

## Sprint 4 - Quotation Flow, Release, Handoff

- [x] T16 Configurable grouped quotation item
  - [x] T16.1 Add selling setting fields for grouped item/prefix
  - [x] T16.2 Validate configuration before grouped quotation generation
  - [x] T16.3 Remove blind auto-create path
- [x] T17 Quotation audit metadata
  - [x] T17.1 Add source scenario metadata on quotation items
  - [x] T17.2 Persist manual override flag
  - [x] T17.3 Keep source pricing sheet linkage
- [x] T18 Pre-generation review step
  - [x] T18.1 Server preview endpoint
  - [x] T18.2 Review dialog and warning display
  - [x] T18.3 Confirmed generation flow
- [x] T19 Deployment plan
  - [x] T19.1 Staging migration steps documented
  - [x] T19.2 Validation checklist documented
  - [x] T19.3 UAT checklist documented
  - [x] T19.4 Rollout and rollback steps documented
- [x] T20 Documentation and handoff
  - [x] T20.1 Admin configuration guide
  - [x] T20.2 Sales usage guide
  - [x] T20.3 Changelog + known limitations
