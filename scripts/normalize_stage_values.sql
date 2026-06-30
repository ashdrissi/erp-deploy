-- Normalize stale Opportunity.sales_stage values
-- Fix: "1. Demande Client" (no prefix) -> "Distribution - 1. Demande Client" (canonical active name)
-- Only affects Orderlift Maroc Distribution company records

-- Dry-run: show what would be updated
SELECT name, company, sales_stage as current_stage, 'Distribution - 1. Demande Client' as new_stage
FROM `tabOpportunity`
WHERE sales_stage = '1. Demande Client'
  AND company = 'Orderlift Maroc Distribution';

-- Confirm count
SELECT COUNT(*) as records_to_update
FROM `tabOpportunity`
WHERE sales_stage = '1. Demande Client'
  AND company = 'Orderlift Maroc Distribution';

-- Execute the fix
UPDATE `tabOpportunity`
SET sales_stage = 'Distribution - 1. Demande Client'
WHERE sales_stage = '1. Demande Client'
  AND company = 'Orderlift Maroc Distribution';
