import frappe
from frappe.utils import add_days, now_datetime, today

from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note

from orderlift.logistics.utils.domestic_dispatch import create_delivery_trip_from_load_plan


DEMO_ITEMS = [
    {
        "item_code": "DEMO-LOG-MOTOR-01",
        "item_name": "Demo Lift Motor",
        "item_group": "Autres",
        "weight": 480,
        "volume": 1.2,
        "rate": 15000,
    },
    {
        "item_code": "DEMO-LOG-DOOR-01",
        "item_name": "Demo Landing Door",
        "item_group": "Porte",
        "weight": 140,
        "volume": 0.95,
        "rate": 5200,
    },
    {
        "item_code": "DEMO-LOG-PANEL-01",
        "item_name": "Demo Control Panel",
        "item_group": "Autres",
        "weight": 35,
        "volume": 0.18,
        "rate": 2400,
    },
    {
        "item_code": "DEMO-LOG-RAIL-01",
        "item_name": "Demo Rail Kit",
        "item_group": "Autres",
        "weight": 220,
        "volume": 0.7,
        "rate": 4300,
    },
]

DEMO_SUPPLIERS = [
    {"name": "DEMO-TURKEY-SUPPLIER", "country": "Turkey"},
    {"name": "DEMO-MOROCCO-SUPPLIER", "country": "Morocco"},
]

DEMO_CUSTOMERS = [
    "DEMO-DOMESTIC-CASA",
    "DEMO-DOMESTIC-RABAT",
    "DEMO-OUT-CUSTOMER-FR",
    "DEMO-OUT-CUSTOMER-ES",
    "DEMO-OUT-ORDERLIFT-SN",
    "DEMO-OUT-ORDERLIFT-CI",
]

CUSTOMER_CITY_MAP = {
    "DEMO-DOMESTIC-CASA": ("Casablanca", "Morocco"),
    "DEMO-DOMESTIC-RABAT": ("Rabat", "Morocco"),
    "DEMO-OUT-CUSTOMER-FR": ("Marseille", "France"),
    "DEMO-OUT-CUSTOMER-ES": ("Valencia", "Spain"),
    "DEMO-OUT-ORDERLIFT-SN": ("Dakar", "Senegal"),
    "DEMO-OUT-ORDERLIFT-CI": ("Abidjan", "Cote d'Ivoire"),
}


def run(company="Orderlift", batch_key=None, scenarios=None):
    batch_key = batch_key or f"DEMO-LOG-{today().replace('-', '')}"
    selected = _parse_scenarios(scenarios)
    warehouse = _pick_warehouse(company)
    cost_center = _pick_cost_center(company)
    vehicle = _ensure_vehicle()
    driver = _ensure_driver()
    items = _ensure_items()
    suppliers = _ensure_suppliers()
    customers = _ensure_customers()

    _ensure_demo_stock(company, warehouse, cost_center, items, batch_key)

    inbound = None
    domestic = None
    outbound_customer = None
    outbound_orderlift = None

    if "inbound" in selected:
        inbound = _seed_inbound_flow(company, suppliers, items, batch_key)

    if "domestic" in selected:
        domestic = _seed_sales_flow(
            company=company,
            warehouse=warehouse,
            cost_center=cost_center,
            flow_scope="Domestic",
            shipping_responsibility="Orderlift",
            destination_zone="Casablanca-Rabat",
            container_profile=_pick_container_profile("domestic"),
            vehicle=vehicle,
            driver=driver,
            batch_key=batch_key,
            orders=[
                {
                    "customer": customers["DEMO-DOMESTIC-CASA"],
                    "label": "domestic-casa",
                    "lines": [(items["DEMO-LOG-DOOR-01"], 2, 5200), (items["DEMO-LOG-PANEL-01"], 3, 2400)],
                },
                {
                    "customer": customers["DEMO-DOMESTIC-RABAT"],
                    "label": "domestic-rabat",
                    "lines": [(items["DEMO-LOG-RAIL-01"], 2, 4300), (items["DEMO-LOG-PANEL-01"], 4, 2400)],
                },
            ],
            create_load_plan=True,
            create_trip=True,
        )

    if "outbound_customer" in selected:
        outbound_customer = _seed_sales_flow(
            company=company,
            warehouse=warehouse,
            cost_center=cost_center,
            flow_scope="Outbound",
            shipping_responsibility="Customer",
            destination_zone="Customer Pickup / Export",
            container_profile=None,
            vehicle=None,
            driver=None,
            batch_key=batch_key,
            orders=[
                {
                    "customer": customers["DEMO-OUT-CUSTOMER-FR"],
                    "label": "outbound-customer-fr",
                    "lines": [(items["DEMO-LOG-MOTOR-01"], 1, 15000), (items["DEMO-LOG-PANEL-01"], 2, 2400)],
                },
                {
                    "customer": customers["DEMO-OUT-CUSTOMER-ES"],
                    "label": "outbound-customer-es",
                    "lines": [(items["DEMO-LOG-DOOR-01"], 2, 5200), (items["DEMO-LOG-RAIL-01"], 1, 4300)],
                },
            ],
            create_load_plan=False,
            create_trip=False,
        )

    if "outbound_orderlift" in selected:
        outbound_orderlift = _seed_sales_flow(
            company=company,
            warehouse=warehouse,
            cost_center=cost_center,
            flow_scope="Outbound",
            shipping_responsibility="Orderlift",
            destination_zone="West Africa Export",
            container_profile=_pick_container_profile("outbound"),
            vehicle=vehicle,
            driver=driver,
            batch_key=batch_key,
            orders=[
                {
                    "customer": customers["DEMO-OUT-ORDERLIFT-SN"],
                    "label": "outbound-orderlift-sn",
                    "lines": [(items["DEMO-LOG-MOTOR-01"], 1, 15000), (items["DEMO-LOG-DOOR-01"], 1, 5200)],
                },
                {
                    "customer": customers["DEMO-OUT-ORDERLIFT-CI"],
                    "label": "outbound-orderlift-ci",
                    "lines": [(items["DEMO-LOG-RAIL-01"], 2, 4300), (items["DEMO-LOG-PANEL-01"], 2, 2400)],
                },
            ],
            create_load_plan=True,
            create_trip=True,
        )

    summary = {
        "batch_key": batch_key,
        "company": company,
        "warehouse": warehouse,
        "vehicle": vehicle,
        "driver": driver,
        "inbound": inbound,
        "domestic": domestic,
        "outbound_customer": outbound_customer,
        "outbound_orderlift": outbound_orderlift,
    }
    frappe.db.commit()
    print(frappe.as_json(summary, indent=2))
    return summary


def _ensure_items():
    result = {}
    for spec in DEMO_ITEMS:
        if frappe.db.exists("Item", spec["item_code"]):
            doc = frappe.get_doc("Item", spec["item_code"])
        else:
            doc = frappe.new_doc("Item")
            doc.item_code = spec["item_code"]
        doc.item_name = spec["item_name"]
        doc.description = spec["item_name"]
        doc.item_group = spec["item_group"]
        doc.stock_uom = "Pc"
        doc.is_stock_item = 1
        doc.is_purchase_item = 1
        doc.is_sales_item = 1
        doc.standard_rate = spec["rate"]
        doc.custom_weight_kg = spec["weight"]
        doc.custom_volume_m3 = spec["volume"]
        doc.custom_length_cm = 0
        doc.custom_width_cm = 0
        doc.custom_height_cm = 0
        doc.flags.ignore_permissions = True
        if doc.is_new():
            doc.insert()
        else:
            doc.save()
        result[spec["item_code"]] = doc.name
    frappe.db.commit()
    return result


def _ensure_suppliers():
    supplier_group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name") or frappe.db.get_value(
        "Supplier Group", {}, "name"
    )
    result = {}
    for spec in DEMO_SUPPLIERS:
        if frappe.db.exists("Supplier", spec["name"]):
            doc = frappe.get_doc("Supplier", spec["name"])
        else:
            doc = frappe.new_doc("Supplier")
            doc.supplier_name = spec["name"]
        doc.supplier_group = supplier_group
        doc.supplier_type = "Company"
        doc.country = spec["country"]
        doc.flags.ignore_permissions = True
        if doc.is_new():
            doc.insert()
        else:
            doc.save()
        result[spec["name"]] = doc.name
    frappe.db.commit()
    return result


def _ensure_customers():
    customer_group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name") or frappe.db.get_value(
        "Customer Group", {}, "name"
    )
    territory = frappe.db.get_value("Territory", {"is_group": 0}, "name") or "All Territories"
    result = {}
    for name in DEMO_CUSTOMERS:
        if frappe.db.exists("Customer", name):
            doc = frappe.get_doc("Customer", name)
        else:
            doc = frappe.new_doc("Customer")
            doc.customer_name = name
        doc.customer_group = customer_group
        doc.customer_type = "Company"
        doc.territory = territory
        doc.flags.ignore_permissions = True
        if doc.is_new():
            doc.insert()
        else:
            doc.save()
        _ensure_customer_address(doc.name)
        result[name] = doc.name
    frappe.db.commit()
    return result


def _ensure_vehicle():
    name = frappe.db.get_value("Vehicle", {"license_plate": "DEMO-LOG-TRUCK-01"}, "name")
    if name:
        return name

    vehicle = frappe.new_doc("Vehicle")
    vehicle.license_plate = "DEMO-LOG-TRUCK-01"
    vehicle.make = "Renault"
    vehicle.model = "Master"
    vehicle.last_odometer = 0
    vehicle.fuel_type = "Diesel"
    vehicle.uom = frappe.db.exists("UOM", "Km") or frappe.db.get_value("UOM", {}, "name")
    vehicle.flags.ignore_permissions = True
    vehicle.insert()
    frappe.db.commit()
    return vehicle.name


def _ensure_driver():
    name = frappe.db.get_value("Driver", {"full_name": "Demo Logistics Driver"}, "name")
    if name:
        return name

    driver = frappe.new_doc("Driver")
    driver.full_name = "Demo Logistics Driver"
    driver.status = "Active"
    driver.flags.ignore_permissions = True
    driver.insert()
    frappe.db.commit()
    return driver.name


def _ensure_demo_stock(company, warehouse, cost_center, items, batch_key):
    existing = frappe.db.get_value(
        "Stock Entry",
        {"stock_entry_type": "Material Receipt", "remarks": ["like", f"%{batch_key}%demo stock seed%"]},
        "name",
    )
    if existing:
        return existing

    entry = frappe.new_doc("Stock Entry")
    entry.company = company
    entry.stock_entry_type = "Material Receipt"
    entry.posting_date = today()
    entry.posting_time = now_datetime().strftime("%H:%M:%S")
    entry.remarks = f"{batch_key} demo stock seed"

    for spec in DEMO_ITEMS:
        entry.append(
            "items",
            {
                "item_code": items[spec["item_code"]],
                "qty": 12,
                "t_warehouse": warehouse,
                "basic_rate": spec["rate"],
                "valuation_rate": spec["rate"],
                "cost_center": cost_center,
            },
        )

    entry.flags.ignore_permissions = True
    entry.insert()
    entry.submit()
    frappe.db.commit()
    return entry.name


def _seed_inbound_flow(company, suppliers, items, batch_key):
    supplier = suppliers["DEMO-TURKEY-SUPPLIER"]
    purchase_orders = []
    definitions = [
        {
            "label": "inbound-01",
            "lines": [(items["DEMO-LOG-MOTOR-01"], 2, 15000), (items["DEMO-LOG-PANEL-01"], 4, 2400)],
        },
        {
            "label": "inbound-02",
            "lines": [(items["DEMO-LOG-DOOR-01"], 2, 5200), (items["DEMO-LOG-RAIL-01"], 3, 4300)],
        },
    ]

    for idx, definition in enumerate(definitions, start=1):
        purchase_orders.append(
            _create_purchase_order(
                company=company,
                supplier=supplier,
                batch_key=batch_key,
                label=definition["label"],
                departure_offset=12 + idx,
                lines=definition["lines"],
            )
        )

    load_plan = _create_load_plan(
        company=company,
        batch_key=batch_key,
        label="Inbound Import Planning",
        flow_scope="Inbound",
        shipping_responsibility="Orderlift",
        source_type="Purchase Order",
        destination_zone="Tangier Port",
        container_profile=_pick_container_profile("inbound"),
        source_names=purchase_orders,
    )
    return {"purchase_orders": purchase_orders, "container_load_plan": load_plan}


def _seed_sales_flow(
    company,
    warehouse,
    cost_center,
    flow_scope,
    shipping_responsibility,
    destination_zone,
    container_profile,
    vehicle,
    driver,
    batch_key,
    orders,
    create_load_plan,
    create_trip,
):
    sales_orders = []
    delivery_notes = []

    for idx, definition in enumerate(orders, start=1):
        so = _create_sales_order(
            company=company,
            warehouse=warehouse,
            cost_center=cost_center,
            customer=definition["customer"],
            flow_scope=flow_scope,
            shipping_responsibility=shipping_responsibility,
            batch_key=batch_key,
            label=definition["label"],
            delivery_offset=4 + idx,
            lines=definition["lines"],
        )
        dn = _create_delivery_note(
            sales_order=so,
            warehouse=warehouse,
            flow_scope=flow_scope,
            shipping_responsibility=shipping_responsibility,
            destination_zone=destination_zone,
            batch_key=batch_key,
            label=definition["label"],
        )
        sales_orders.append(so)
        delivery_notes.append(dn)

    load_plan = None
    delivery_trip = None
    if create_load_plan:
        load_plan = _create_load_plan(
            company=company,
            batch_key=batch_key,
            label=f"{flow_scope} {shipping_responsibility} Planning",
            flow_scope=flow_scope,
            shipping_responsibility=shipping_responsibility,
            source_type="Delivery Note",
            destination_zone=destination_zone,
            container_profile=container_profile,
            source_names=delivery_notes,
        )

    if create_trip and load_plan:
        result = create_delivery_trip_from_load_plan(
            load_plan,
            vehicle=vehicle,
            departure_time=add_days(now_datetime(), 1),
            driver=driver,
        )
        delivery_trip = result.get("delivery_trip") if result else None
        frappe.db.commit()

    return {
        "sales_orders": sales_orders,
        "delivery_notes": delivery_notes,
        "container_load_plan": load_plan,
        "delivery_trip": delivery_trip,
    }


def _create_purchase_order(company, supplier, batch_key, label, departure_offset, lines):
    po = frappe.new_doc("Purchase Order")
    po.company = company
    po.supplier = supplier
    po.transaction_date = today()
    po.schedule_date = add_days(today(), departure_offset)
    po.custom_flow_scope = "Inbound"
    po.custom_shipping_responsibility = "Orderlift"
    _set_if_present(po, "supplier_quotation_no", f"{batch_key}-{label}")
    _set_if_present(po, "note", f"{batch_key} {label}")

    for item_code, qty, rate in lines:
        po.append(
            "items",
            {
                "item_code": item_code,
                "qty": qty,
                "rate": rate,
                "schedule_date": po.schedule_date,
            },
        )

    po.flags.ignore_permissions = True
    po.insert()
    po.submit()
    frappe.db.commit()
    return po.name


def _create_sales_order(company, warehouse, cost_center, customer, flow_scope, shipping_responsibility, batch_key, label, delivery_offset, lines):
    existing = frappe.db.get_value("Sales Order", {"po_no": f"{batch_key}-{label}"}, "name")
    if existing:
        return existing

    so = frappe.new_doc("Sales Order")
    so.company = company
    so.customer = customer
    so.po_no = f"{batch_key}-{label}"
    so.transaction_date = today()
    so.custom_flow_scope = flow_scope
    so.custom_shipping_responsibility = shipping_responsibility
    so.set_warehouse = warehouse

    for item_code, qty, rate in lines:
        so.append(
            "items",
            {
                "item_code": item_code,
                "qty": qty,
                "rate": rate,
                "delivery_date": add_days(today(), delivery_offset),
                "warehouse": warehouse,
                "cost_center": cost_center,
            },
        )

    so.run_method("set_missing_values")
    so.flags.ignore_permissions = True
    so.insert()
    so.submit()
    frappe.db.commit()
    return so.name


def _create_delivery_note(sales_order, warehouse, flow_scope, shipping_responsibility, destination_zone, batch_key, label):
    dn = make_delivery_note(sales_order)
    dn.posting_date = today()
    dn.posting_time = now_datetime().strftime("%H:%M:%S")
    dn.set_warehouse = warehouse
    dn.shipping_address_name = _ensure_customer_address(dn.customer)
    dn.custom_flow_scope = flow_scope
    dn.custom_shipping_responsibility = shipping_responsibility
    dn.custom_destination_zone = destination_zone
    _set_if_present(dn, "remarks", f"{batch_key} {label}")

    for row in dn.items or []:
        row.warehouse = warehouse

    dn.flags.ignore_permissions = True
    dn.insert()
    dn.submit()
    frappe.db.commit()
    return dn.name


def _create_load_plan(company, batch_key, label, flow_scope, shipping_responsibility, source_type, destination_zone, container_profile, source_names):
    container_label = f"{batch_key} {label}"
    existing = frappe.db.get_value("Container Load Plan", {"container_label": container_label}, "name")
    if existing:
        return existing

    doc = frappe.new_doc("Container Load Plan")
    doc.company = company
    doc.container_label = container_label
    doc.container_profile = container_profile
    doc.flow_scope = flow_scope
    doc.shipping_responsibility = shipping_responsibility
    doc.source_type = source_type
    doc.destination_zone = destination_zone
    doc.departure_date = add_days(today(), 7)
    doc.status = "Ready"
    doc.notes = f"{batch_key} seeded demo flow"

    for idx, source_name in enumerate(source_names, start=1):
        row = {"selected": 1, "sequence": idx * 10}
        if source_type == "Purchase Order":
            row["purchase_order"] = source_name
        else:
            row["delivery_note"] = source_name
        doc.append("shipments", row)

    doc.flags.ignore_permissions = True
    doc.insert()
    doc.submit()
    frappe.db.commit()
    return doc.name


def _pick_warehouse(company):
    warehouse = frappe.db.get_value("Warehouse", {"company": company, "name": ["like", "%Finished Goods%"]}, "name")
    if warehouse:
        return warehouse
    warehouse = frappe.db.get_value("Warehouse", {"company": company, "is_group": 0}, "name")
    if warehouse:
        return warehouse
    frappe.throw(f"No warehouse found for company {company}")


def _pick_cost_center(company):
    cost_center = frappe.db.get_value("Cost Center", {"company": company, "name": ["like", "%Main%"]}, "name")
    if cost_center:
        return cost_center
    cost_center = frappe.db.get_value("Cost Center", {"company": company}, "name")
    if cost_center:
        return cost_center
    frappe.throw(f"No cost center found for company {company}")


def _pick_container_profile(mode):
    if mode == "domestic":
        name = frappe.db.get_value("Container Profile", {"container_name": "DEMO-TRUCK-10T"}, "name")
        if name:
            return name
        name = frappe.db.get_value("Container Profile", {"container_type": "Standard Truck", "is_active": 1}, "name")
        if name:
            return name

    if mode in ("inbound", "outbound"):
        name = frappe.db.get_value("Container Profile", {"container_name": "DEMO-40FT-HC"}, "name")
        if name:
            return name
        name = frappe.db.get_value("Container Profile", {"container_type": "40ft", "is_active": 1}, "name")
        if name:
            return name

    name = frappe.db.get_value("Container Profile", {"is_active": 1}, "name")
    if name:
        return name
    frappe.throw("No active Container Profile found")


def _set_if_present(doc, fieldname, value):
    if doc.meta.has_field(fieldname):
        doc.set(fieldname, value)


def _parse_scenarios(scenarios):
    if not scenarios:
        return {"inbound", "domestic", "outbound_customer", "outbound_orderlift"}

    if isinstance(scenarios, str):
        values = [part.strip() for part in scenarios.split(",") if part.strip()]
    else:
        values = [str(part).strip() for part in scenarios if str(part).strip()]

    return set(values)


def _ensure_customer_address(customer_name):
    existing = frappe.db.get_value(
        "Dynamic Link",
        {"link_doctype": "Customer", "link_name": customer_name, "parenttype": "Address"},
        "parent",
    )
    if existing:
        return existing

    city, country = CUSTOMER_CITY_MAP.get(customer_name, ("Casablanca", "Morocco"))
    country = _resolve_country(country)
    address = frappe.new_doc("Address")
    address.address_title = customer_name
    address.address_type = "Shipping"
    address.address_line1 = f"{customer_name} Logistics Hub"
    address.city = city
    address.country = country
    address.append(
        "links",
        {
            "link_doctype": "Customer",
            "link_name": customer_name,
        },
    )
    address.flags.ignore_permissions = True
    address.insert()
    frappe.db.commit()
    return address.name


def _resolve_country(country):
    if frappe.db.exists("Country", country):
        return country

    aliases = {
        "Cote d'Ivoire": ["Côte d'Ivoire", "Ivory Coast"],
    }
    for candidate in aliases.get(country, []):
        if frappe.db.exists("Country", candidate):
            return candidate

    return "Morocco"
