# Pricing Admin Guide

## Core Objects

- `Pricing Scenario`: reusable expense configuration.
- `Pricing Scenario Expense`: ordered rules with type, basis, and scope.
- `Pricing Sheet`: article-level projection and quotation bridge.
- `Customer Segmentation Engine`: one company-scoped segmentation configuration for dynamic customer tiers plus global tier and territory price modifiers.
- `Pricing Benchmark Policy`: margin and benchmark rules only; global tier and territory modifiers are managed from `Customer Segmentation Engine`.

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

## Customer Segmentation And Modifiers

- Open `Main Dashboard > Policies & Configs > Customer Segmentation Engine`.
- Multi-company users manage each company from the page tabs.
- Segmentation rules calculate dynamic customer `tier` values.
- Tier and territory modifiers apply in both dynamic Pricing Sheet calculations and static selling-list mode.
- Existing Benchmark Policy modifier rows are copied into the matching company engine on migrate; they are not deleted.

## Migration Notes

- Legacy scenarios are migrated via patch on `bench migrate`.
- New scenarios can be bootstrapped with starter expenses from UI.
- Company segmentation engines and copied legacy modifier rows are synchronized on `bench migrate`.
