import frappe

def execute():
    policies = frappe.get_all('Pricing Benchmark Policy', pluck='name')
    print('Policies:', policies)
    if policies:
        name = policies[0]
        frappe.db.set_value('Pricing Benchmark Policy', name, 'is_default', 1)
        frappe.db.set_value('Pricing Benchmark Policy', name, 'is_active', 1)
        frappe.db.commit()
        print('Marked default')
        
        doc = frappe.get_doc('Pricing Benchmark Policy', name)
        modified = False
        
        if not doc.get('tier_modifiers'):
            tiers = [
                {'tier': 'Gold',   'modifier_amount': 0,    'modifier_type': 'Fixed', 'is_active': 1},
                {'tier': 'Silver', 'modifier_amount': -10,  'modifier_type': 'Fixed', 'is_active': 1},
                {'tier': 'Bronze', 'modifier_amount': -15,  'modifier_type': 'Fixed', 'is_active': 1},
                {'tier': 'Eco',    'modifier_amount': -20,  'modifier_type': 'Fixed', 'is_active': 1},
                {'tier': 'Luxe',   'modifier_amount': 25,   'modifier_type': 'Fixed', 'is_active': 1},
            ]
            for t in tiers:
                doc.append('tier_modifiers', t)
            modified = True
            print('Added tier modifiers')
                
        if not doc.get('zone_modifiers'):
            territories = frappe.get_all('Territory', pluck='name', limit_page_length=5)
            amounts = [50, 25, 0, -10, 15]
            for i, terr in enumerate(territories[:5]):
                doc.append('zone_modifiers', {
                    'territory': terr,
                    'modifier_amount': amounts[i % len(amounts)],
                    'modifier_type': 'Fixed',
                    'is_active': 1,
                })
            modified = True
            print('Added zone modifiers')
                
        if modified:
            doc.save(ignore_permissions=True)
            frappe.db.commit()
            print("Successfully saved doc")
    else:
        print("No policies found")
