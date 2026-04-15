import frappe

def ensure_container_profile():
    cp_name = "40ft High Cube"
    if frappe.db.exists("Container Profile", cp_name):
        print(f"Container Profile exists: {cp_name}")
        return cp_name
    
    cp = frappe.new_doc("Container Profile")
    cp.container_name = cp_name
    cp.container_type = "40ft"
    cp.max_volume_m3 = 76.0
    cp.max_weight_kg = 28000
    cp.is_active = 1
    cp.cost_rank = 1
    cp.insert(ignore_permissions=True)
    frappe.db.commit()
    print(f"Created: {cp_name}")
    return cp_name
