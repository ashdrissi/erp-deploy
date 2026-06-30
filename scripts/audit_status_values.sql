-- Audit: all distinct stored status values per doctype and company
-- vs active status row names

-- 1) All Opportunity.sales_stage values
SELECT 'Opportunity' as doctype, sales_stage as stored_value, company, COUNT(*) as cnt
FROM `tabOpportunity`
WHERE sales_stage IS NOT NULL AND sales_stage != ''
GROUP BY sales_stage, company
ORDER BY company, sales_stage;

-- 2) All Project.custom_project_status values
SELECT 'Project' as doctype, custom_project_status as stored_value, company, COUNT(*) as cnt
FROM `tabProject`
WHERE custom_project_status IS NOT NULL AND custom_project_status != ''
GROUP BY custom_project_status, company
ORDER BY company, custom_project_status;

-- 3) All Sales Order.custom_orderlift_order_status values
SELECT 'Sales Order' as doctype, custom_orderlift_order_status as stored_value, company, COUNT(*) as cnt
FROM `tabSales Order`
WHERE custom_orderlift_order_status IS NOT NULL AND custom_orderlift_order_status != ''
GROUP BY custom_orderlift_order_status, company
ORDER BY company, custom_orderlift_order_status;

-- 4) All active Sales Stage row names (Opportunity statuses)
SELECT 'Sales Stage (active)' as source, name as row_name, custom_company as company
FROM `tabSales Stage`
WHERE custom_is_active = 1
ORDER BY custom_company, name;

-- 5) All active Project Status row names
SELECT 'Project Status (active)' as source, name as row_name, company
FROM `tabProject Status`
WHERE is_active = 1
ORDER BY company, name;

-- 6) All active Orderlift Order Status row names
SELECT 'Orderlift Order Status (active)' as source, name as row_name, company
FROM `tabOrderlift Order Status`
WHERE is_active = 1
ORDER BY company, name;
