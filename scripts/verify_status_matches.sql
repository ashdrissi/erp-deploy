-- Cross-check: find any stored values that don't match an active status row name
-- Opportunity vs Sales Stage
SELECT 'Opportunity MISMATCH' as check_type, o.name, o.company, o.sales_stage as stored_value
FROM `tabOpportunity` o
LEFT JOIN `tabSales Stage` ss ON ss.name = o.sales_stage AND ss.custom_company = o.company AND ss.custom_is_active = 1
WHERE o.sales_stage IS NOT NULL AND o.sales_stage != '' AND o.company IS NOT NULL AND o.company != ''
  AND ss.name IS NULL;

-- Project vs Project Status
SELECT 'Project MISMATCH' as check_type, p.name, p.company, p.custom_project_status as stored_value
FROM `tabProject` p
LEFT JOIN `tabProject Status` ps ON ps.name = p.custom_project_status AND ps.company = p.company AND ps.is_active = 1
WHERE p.custom_project_status IS NOT NULL AND p.custom_project_status != '' AND p.company IS NOT NULL AND p.company != ''
  AND ps.name IS NULL;

-- Sales Order vs Orderlift Order Status
SELECT 'Sales Order MISMATCH' as check_type, so.name, so.company, so.custom_orderlift_order_status as stored_value
FROM `tabSales Order` so
LEFT JOIN `tabOrderlift Order Status` oos ON oos.name = so.custom_orderlift_order_status AND oos.company = so.company AND oos.is_active = 1
WHERE so.custom_orderlift_order_status IS NOT NULL AND so.custom_orderlift_order_status != '' AND so.company IS NOT NULL AND so.company != ''
  AND oos.name IS NULL;

-- Summary: total mismatches per doctype
SELECT 'Opportunity' as doctype, COUNT(*) as mismatches
FROM `tabOpportunity` o
LEFT JOIN `tabSales Stage` ss ON ss.name = o.sales_stage AND ss.custom_company = o.company AND ss.custom_is_active = 1
WHERE o.sales_stage IS NOT NULL AND o.sales_stage != '' AND o.company IS NOT NULL AND o.company != ''
  AND ss.name IS NULL
UNION ALL
SELECT 'Project' as doctype, COUNT(*) as mismatches
FROM `tabProject` p
LEFT JOIN `tabProject Status` ps ON ps.name = p.custom_project_status AND ps.company = p.company AND ps.is_active = 1
WHERE p.custom_project_status IS NOT NULL AND p.custom_project_status != '' AND p.company IS NOT NULL AND p.company != ''
  AND ps.name IS NULL
UNION ALL
SELECT 'Sales Order' as doctype, COUNT(*) as mismatches
FROM `tabSales Order` so
LEFT JOIN `tabOrderlift Order Status` oos ON oos.name = so.custom_orderlift_order_status AND oos.company = so.company AND oos.is_active = 1
WHERE so.custom_orderlift_order_status IS NOT NULL AND so.custom_orderlift_order_status != '' AND so.company IS NOT NULL AND so.company != ''
  AND oos.name IS NULL;
