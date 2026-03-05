import frappe


def sync_customer_tier_mode(doc, method=None):
    is_dynamic = int(doc.get("enable_dynamic_segmentation") or 0) == 1

    if is_dynamic:
        doc.manual_tier = ""
        if doc.tier:
            doc.tier_source = doc.tier_source or "Dynamic Segmentation"
        return

    manual_tier = (doc.get("manual_tier") or "").strip()
    if manual_tier:
        doc.tier = manual_tier
        doc.tier_source = "Manual"
        doc.tier_last_calculated_on = None
