# Pricing Admin Guide

## Core Objects

- `Pricing Scenario`: reusable expense configuration.
- `Pricing Scenario Expense`: ordered rules with type, basis, and scope.
- `Pricing Sheet`: article-level projection and quotation bridge.

## Expense Rule Design

- Use `sequence` to control order.
- `Percentage` applies as percent of `Base Price` or `Running Total`.
- `Fixed` supports `Per Unit`, `Per Line`, and `Per Sheet`.

## Guardrails

- `Minimum Margin Percent`: warning threshold.
- `Strict Margin Guard`: block save when warnings exist.
- Floor violations (`< 0`) are always flagged.

## Selling Settings (Optional)

- `Pricing Group Line Item`: item used for grouped quotations.
- `Pricing Group Description Prefix`: description prefix for grouped lines.

## Migration Notes

- Legacy scenarios are migrated via patch on `bench migrate`.
- New scenarios can be bootstrapped with starter expenses from UI.
