from pathlib import Path

import frappe


BENCH_APPS = Path("/home/frappe/frappe-bench/apps")
PF_DIR = BENCH_APPS / "orderlift/orderlift/print_formats"

# Mode variants: (name_suffix, price_mode, show_images, force_without_details)
_MODES = (
    ("PU HT", "HT", True, False),
    ("PU TTC", "TTC", True, False),
    ("Prix Unitaire", "PRIX_UNITAIRE", True, False),
    ("PU HT Sans Images", "HT", False, False),
    ("PU TTC Sans Images", "TTC", False, False),
    ("Prix Unitaire Sans Images", "PRIX_UNITAIRE", False, False),
    ("PU HT Without Details", "HT", False, True),
    ("PU TTC Without Details", "TTC", False, True),
    ("Prix Unitaire Without Details", "PRIX_UNITAIRE", False, True),
)

_MOROCCO_ONLY_MODES = (
    ("PU HT Without Prices", "HT", True, False),
    ("PU TTC Without Prices", "TTC", True, False),
    ("Prix Unitaire Without Prices", "PRIX_UNITAIRE", True, False),
)

_MOROCCO_COMPANIES = {
    "Orderlift Maroc Distribution",
    "Orderlift Maroc Installation",
}

_MOROCCO_WITHOUT_PRICE_DOCTYPES = {
    "Quotation",
    "Sales Order",
    "Delivery Note",
    "Sales Invoice",
    "Purchase Order",
    "Purchase Invoice",
}

# Per-doctype config
_DOC_CONFIG = (
    {
        "doc_type": "Quotation",
        "template_key": "quotation",
        "module": "Orderlift Sales",
        "name_prefix": "Orderlift Quotation",
        "show_cover_with_images": True,
        "legacy_name": "Orderlift Quotation",
    },
    {
        "doc_type": "Sales Order",
        "template_key": "sales",
        "module": "Orderlift Sales",
        "name_prefix": "Orderlift Sales Order",
        "show_cover_with_images": True,
        "legacy_name": "Orderlift Sales Order",
    },
    {
        "doc_type": "Delivery Note",
        "template_key": "sales",
        "module": "Orderlift Logistics",
        "name_prefix": "Orderlift Delivery Note",
        "show_cover_with_images": False,
        "legacy_name": "Orderlift Delivery Note",
    },
    {
        "doc_type": "Sales Invoice",
        "template_key": "sales",
        "module": "Orderlift Sales",
        "name_prefix": "Orderlift Sales Invoice",
        "show_cover_with_images": False,
        "legacy_name": "Orderlift Sales Invoice",
    },
    {
        "doc_type": "Purchase Order",
        "template_key": "purchase",
        "module": "Orderlift Sales",
        "name_prefix": "Orderlift Purchase Order",
        "show_cover_with_images": False,
        "legacy_name": None,
    },
    {
        "doc_type": "Purchase Invoice",
        "template_key": "purchase",
        "module": "Orderlift Sales",
        "name_prefix": "Orderlift Purchase Invoice",
        "show_cover_with_images": False,
        "legacy_name": None,
    },
    {
        "doc_type": "Purchase Receipt",
        "template_key": "purchase",
        "module": "Orderlift Logistics",
        "name_prefix": "Orderlift Purchase Receipt",
        "show_cover_with_images": False,
        "legacy_name": None,
    },
    {
        "doc_type": "Supplier Quotation",
        "template_key": "purchase",
        "module": "Orderlift Sales",
        "name_prefix": "Orderlift Supplier Quotation",
        "show_cover_with_images": False,
        "legacy_name": None,
    },
)

# Company config: which template suffix and name suffix per company
_COMPANIES = (
    {
        "name": "Orderlift",
        "template_suffix": "",
        "name_suffix": " - OL",
    },
    {
        "name": "Orderlift Maroc Distribution",
        "template_suffix": "",
        "name_suffix": " - OMD",
    },
    {
        "name": "Orderlift Maroc Installation",
        "template_suffix": "",
        "name_suffix": " - OMI",
    },
    {
        "name": "Orderlift Turkey",
        "template_suffix": "_tr",
        "name_suffix": " - TR",
    },
)

_TEMPLATE_MAP = {
    "quotation": "orderlift_quotation.html",
    "sales": "orderlift_sales_document.html",
    "purchase": "orderlift_purchase_document.html",
}


def _resolve_template_file(template_key, company_cfg):
    base = _TEMPLATE_MAP[template_key]
    sfx = company_cfg.get("template_suffix", "")
    if not sfx:
        return base
    stem = base.rsplit(".", 1)[0]
    return f"{stem}{sfx}.html"


def run(companies=None, doc_types=None):
    company_filter = _normalize_filter(companies)
    doc_type_filter = _normalize_filter(doc_types)
    company_configs = _filter_configs(_COMPANIES, "name", company_filter, "company")
    doc_configs = _filter_configs(_DOC_CONFIG, "doc_type", doc_type_filter, "doctype")
    full_run = not company_filter and not doc_type_filter

    # Pre-load all needed templates
    templates = {}
    for cfg in doc_configs:
        for comp in company_configs:
            tpl_file = _resolve_template_file(cfg["template_key"], comp)
            if tpl_file not in templates:
                path = PF_DIR / tpl_file
                if not path.exists():
                    print(f"WARNING: template not found {path}")
                    continue
                templates[tpl_file] = path.read_text(encoding="utf-8")

    total = 0
    for cfg in doc_configs:
        doc_type = cfg["doc_type"]
        module = cfg["module"]
        prefix = cfg["name_prefix"]
        has_cover = cfg["show_cover_with_images"]
        legacy = cfg["legacy_name"]

        if full_run:
            _handle_legacy(legacy)
            _disable_shared_company_formats(prefix)

        for comp in company_configs:
            company = comp["name"]
            name_suffix = comp.get("name_suffix", "")
            tpl_file = _resolve_template_file(cfg["template_key"], comp)
            html = templates.get(tpl_file)
            if html is None:
                continue

            modes = _modes_for_company(comp, doc_type)
            for mode_suffix, price_mode, show_images, force_without_details in modes:
                name = f"{prefix} {mode_suffix}{name_suffix}"
                show_cover = "true" if (has_cover and show_images) else "false"
                show_images_str = "true" if show_images else "false"
                hide_price_columns = mode_suffix.endswith("Without Prices")

                rendered = _prepend_variables(
                    html,
                    price_mode,
                    show_images_str,
                    show_cover,
                    force_without_details,
                    hide_price_columns,
                )
                _upsert_print_format(name, rendered, doc_type, module, company)

            total += len(modes)

    frappe.db.commit()
    print(
        f"SUCCESSFULLY UPDATED {total} print format records across "
        f"{len(doc_configs)} doctypes x {len(company_configs)} companies"
    )


def _normalize_filter(values):
    if not values:
        return set()
    if isinstance(values, str):
        values = values.split(",")
    return {str(value).strip() for value in values if str(value).strip()}


def _filter_configs(configs, key, requested, label):
    if not requested:
        return configs
    known = {config[key] for config in configs}
    unknown = sorted(requested - known)
    if unknown:
        raise ValueError(f"Unknown print format {label}(s): {', '.join(unknown)}")
    return tuple(config for config in configs if config[key] in requested)


def _modes_for_company(company_cfg, doc_type):
    if (
        company_cfg.get("name") in _MOROCCO_COMPANIES
        and doc_type in _MOROCCO_WITHOUT_PRICE_DOCTYPES
    ):
        return _MODES + _MOROCCO_ONLY_MODES
    return _MODES


def _prepend_variables(
    html,
    price_mode,
    show_images,
    show_cover,
    force_without_details=False,
    hide_price_columns=False,
):
    return (
        f"{{% set orderlift_price_display_mode = '{price_mode}' %}}\n"
        f"{{% set orderlift_show_images = '{show_images}' %}}\n"
        f"{{% set orderlift_show_cover = '{show_cover}' %}}\n"
        f"{{% set orderlift_force_without_details = {'true' if force_without_details else 'false'} %}}\n"
        f"{{% set orderlift_hide_price_columns = {'true' if hide_price_columns else 'false'} %}}\n"
        + html
    )


def _handle_legacy(legacy_name):
    if not legacy_name:
        return
    if not frappe.db.exists("Print Format", legacy_name):
        return
    first_new_name = f"{legacy_name} PU HT"
    if frappe.db.exists("Print Format", first_new_name):
        doc = frappe.get_doc("Print Format", legacy_name)
        doc.disabled = 1
        doc.save(ignore_permissions=True)
        return
    frappe.rename_doc("Print Format", legacy_name, first_new_name, force=True)


def _disable_shared_company_formats(prefix):
    if not frappe.db.has_column("Print Format", "custom_company"):
        return
    legacy_names = [f"{prefix} {mode_suffix}" for mode_suffix, _price_mode, _show_images, _force in _MODES]
    rows = frappe.get_all(
        "Print Format",
        filters={"name": ["in", legacy_names], "custom_company": ["is", "not set"]},
        pluck="name",
        limit_page_length=0,
    )
    for name in rows:
        frappe.db.set_value("Print Format", name, "disabled", 1, update_modified=False)


def _upsert_print_format(name, rendered_html, doc_type, module, company):
    if frappe.db.exists("Print Format", name):
        doc = frappe.get_doc("Print Format", name)
    else:
        doc = frappe.new_doc("Print Format")
        doc.name = name

    doc.align_labels_right = 0
    doc.custom_format = 1
    doc.disabled = 0
    doc.doc_type = doc_type
    doc.font = "Default"
    doc.line_breaks = 0
    doc.module = module
    doc.print_format_type = "Jinja"
    doc.show_section_headings = 0
    doc.standard = "No"
    doc.html = rendered_html
    if doc.meta.get_field("custom_company"):
        doc.custom_company = company
    doc.save(ignore_permissions=True)
