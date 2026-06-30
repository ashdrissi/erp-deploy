from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import time
import uuid

import frappe
from frappe import _
from frappe.utils import cint

from orderlift.scripts import import_article_excel_catalog as catalog_import
from orderlift.scripts import update_article_buying_prices as article_update


DEFAULT_WORKBOOK = Path("/tmp/db article 2- juin .xlsx")
DEFAULT_SHEET = "Database"
CONFIRM_TOKEN = "APPLY_CATEGORY_ARTICLE_ITEM_RENAMES"


@frappe.whitelist()
def run(
    workbook_path: str | None = None,
    sheet_name: str = DEFAULT_SHEET,
    dry_run: int | str = 1,
    confirm: str | None = None,
    start_row: int | str = 2,
    limit: int | str | None = None,
    throw_on_failure: int | str = 1,
    use_temp_phase: int | str = 0,
    rename_retries: int | str = 3,
) -> dict:
    frappe.only_for("System Manager")
    dry_run = article_update._truthy(dry_run)
    throw_on_failure = article_update._truthy(throw_on_failure)
    use_temp_phase = article_update._truthy(use_temp_phase)
    start_row = cint(start_row or 2)
    limit = cint(limit or 0)
    rename_retries = max(cint(rename_retries or 1), 1)
    if not dry_run and confirm != CONFIRM_TOKEN:
        frappe.throw(_("Pass confirm={0} to apply Item renames.").format(CONFIRM_TOKEN))

    path = Path(workbook_path or DEFAULT_WORKBOOK)
    if not path.exists():
        frappe.throw(_("Workbook not found: {0}").format(path))

    rows = article_update._valid_item_rows(article_update._read_xlsx_rows(path, sheet_name))
    caches = article_update._load_caches()
    summary = {
        "workbook_path": str(path),
        "sheet_name": sheet_name,
        "dry_run": dry_run,
        "start_row": start_row,
        "limit": limit or None,
        "throw_on_failure": throw_on_failure,
        "use_temp_phase": use_temp_phase,
        "rename_retries": rename_retries,
        "confirm_required_for_apply": CONFIRM_TOKEN,
        "rows_total": len(rows),
        "rows_read": 0,
        "last_selected_excel_row": None,
        "duplicate_rows_skipped": 0,
        "items_seen": 0,
        "items_already_correct": 0,
        "items_to_rename": 0,
        "items_temp_renamed": 0,
        "items_renamed": 0,
        "resolved_ambiguous_matches": 0,
        "items_missing": [],
        "ambiguous_matches": [],
        "target_conflicts": [],
        "rename_failures": [],
        "duplicate_rows": [],
        "renames": [],
        "temp_renames": [],
        "category_sequences": {},
    }

    sequence_by_category: dict[str, int] = defaultdict(int)
    planned_targets: dict[str, str] = {}
    planned_sources: set[str] = set()
    max_sequence_by_category: dict[str, int] = defaultdict(int)
    consumed_items: set[str] = set()
    seen_signatures: set[tuple] = set()
    selected_rows = 0
    rename_plan: list[dict] = []

    for row in rows:
        signature = _rename_identity(row)
        if signature in seen_signatures:
            if _row_is_selected(row, start_row):
                summary["duplicate_rows_skipped"] += 1
                _append_limited(
                    summary["duplicate_rows"],
                    {
                        "excel_row": row.get("excel_row"),
                        "source_item_code": article_update._clean(row.get("ITEM CODE")),
                        "item_name": article_update._row_value(row, "ITEM NAME"),
                        "category_article": article_update._clean(row.get("ITEM GROUP")),
                    },
                )
            continue
        seen_signatures.add(signature)

        category = article_update._resolve_item_category(article_update._clean(row.get("ITEM GROUP")), caches)
        category_name = category["name"]
        sequence_by_category[category_name] += 1
        sequence = sequence_by_category[category_name]
        max_sequence_by_category[category_name] = max(max_sequence_by_category[category_name], sequence)
        desired_item_code = article_update._format_item_code(category, sequence)

        if not _row_is_selected(row, start_row):
            continue
        if limit and selected_rows >= limit:
            break
        selected_rows += 1
        summary["rows_read"] = selected_rows
        summary["last_selected_excel_row"] = row.get("excel_row")

        item_code = _find_live_item_for_row(row, summary, caches, consumed_items)
        if not item_code:
            continue

        summary["items_seen"] += 1
        if item_code == desired_item_code:
            summary["items_already_correct"] += 1
            continue

        existing_target = frappe.db.exists("Item", desired_item_code)
        planned_source = planned_targets.get(desired_item_code)
        target_will_be_freed = bool(existing_target and existing_target in planned_sources)
        if (
            (not use_temp_phase and existing_target and existing_target != item_code and not target_will_be_freed)
            or (planned_source and planned_source != item_code)
        ):
            _append_limited(
                summary["target_conflicts"],
                {
                    "excel_row": row.get("excel_row"),
                    "source_item_code": article_update._clean(row.get("ITEM CODE")),
                    "item_code": item_code,
                    "desired_item_code": desired_item_code,
                    "existing_target": existing_target or planned_source,
                },
            )
            continue

        planned_targets[desired_item_code] = item_code
        planned_sources.add(item_code)
        plan_row = {
            "excel_row": row.get("excel_row"),
            "source_item_code": article_update._clean(row.get("ITEM CODE")),
            "old_item_code": item_code,
            "new_item_code": desired_item_code,
            "category_article": category_name,
            "existing_target": existing_target,
        }
        rename_plan.append(plan_row)
        summary["items_to_rename"] += 1
        _append_limited(
            summary["renames"],
            {key: plan_row[key] for key in ["excel_row", "source_item_code", "old_item_code", "new_item_code", "category_article"]},
            limit=300,
        )

        if not dry_run and not use_temp_phase:
            error = _rename_item(item_code, desired_item_code, rename_retries)
            if not error:
                summary["items_renamed"] += 1
            else:
                _append_limited(
                    summary["rename_failures"],
                    {
                        "excel_row": row.get("excel_row"),
                        "source_item_code": article_update._clean(row.get("ITEM CODE")),
                        "old_item_code": item_code,
                        "new_item_code": desired_item_code,
                        "error": error,
                    },
                    limit=300,
                )

    if use_temp_phase:
        source_set = {row["old_item_code"] for row in rename_plan}
        for plan_row in rename_plan:
            existing_target = plan_row.get("existing_target")
            if existing_target and existing_target != plan_row["old_item_code"] and existing_target not in source_set:
                _append_limited(
                    summary["target_conflicts"],
                    {
                        "excel_row": plan_row["excel_row"],
                        "source_item_code": plan_row["source_item_code"],
                        "item_code": plan_row["old_item_code"],
                        "desired_item_code": plan_row["new_item_code"],
                        "existing_target": existing_target,
                    },
                )
        if not dry_run and not summary["target_conflicts"]:
            _apply_temp_phase_renames(rename_plan, summary, rename_retries)

    summary["category_sequences"] = dict(sorted(max_sequence_by_category.items()))
    if not dry_run and not summary["target_conflicts"] and not summary["rename_failures"]:
        _sync_category_sequences(max_sequence_by_category)
        frappe.db.commit()
    elif not dry_run:
        frappe.db.rollback()
        if throw_on_failure:
            frappe.throw(
                _("Item rename encountered {0} conflicts and {1} failures; transaction was rolled back.").format(
                    len(summary["target_conflicts"]),
                    len(summary["rename_failures"]),
                )
            )

    return summary


def _row_is_selected(row: dict, start_row: int) -> bool:
    return cint(row.get("excel_row") or 0) >= start_row


def _apply_temp_phase_renames(rename_plan: list[dict], summary: dict, rename_retries: int) -> None:
    for index, plan_row in enumerate(rename_plan, start=1):
        temp_item_code = _make_temporary_item_code(index)
        plan_row["temporary_item_code"] = temp_item_code
        _append_limited(
            summary["temp_renames"],
            {
                "old_item_code": plan_row["old_item_code"],
                "temporary_item_code": temp_item_code,
                "new_item_code": plan_row["new_item_code"],
            },
            limit=300,
        )
        error = _rename_item(plan_row["old_item_code"], temp_item_code, rename_retries)
        if error:
            _append_limited(
                summary["rename_failures"],
                {**plan_row, "phase": "temporary", "error": error},
                limit=300,
            )
            return
        summary["items_temp_renamed"] += 1

    for plan_row in rename_plan:
        error = _rename_item(plan_row["temporary_item_code"], plan_row["new_item_code"], rename_retries)
        if error:
            _append_limited(
                summary["rename_failures"],
                {**plan_row, "phase": "final", "error": error},
                limit=300,
            )
            return
        summary["items_renamed"] += 1


def _make_temporary_item_code(index: int) -> str:
    while True:
        item_code = f"TMPREN-{uuid.uuid4().hex[:10]}-{index:05d}"
        if not frappe.db.exists("Item", item_code):
            return item_code


def _rename_item(old_item_code: str, new_item_code: str, retries: int) -> str:
    for attempt in range(1, retries + 1):
        try:
            frappe.rename_doc(
                "Item",
                old_item_code,
                new_item_code,
                force=True,
                show_alert=False,
                rebuild_search=False,
            )
            return ""
        except Exception as exc:
            if "Lock wait timeout" not in str(exc) or attempt >= retries:
                return str(exc)
            frappe.db.rollback()
            time.sleep(attempt)


def _find_live_item_for_row(row: dict, summary: dict, caches: dict, consumed_items: set[str]) -> str | None:
    source_category = article_update._clean(row.get("ITEM GROUP"))
    category = article_update._resolve_item_category(source_category, caches)["name"]
    filters = {
        "item_name": article_update._row_value(row, "ITEM NAME"),
        "item_group": article_update._clean(row.get("ITEM CATEGORY")),
        "stock_uom": article_update._clean(row.get("DEFAULT UNIT OF MEASURE")),
        "custom_item_category": category,
        "disabled": 0,
    }
    required_values = [value for key, value in filters.items() if key != "disabled"]
    if not all(required_values):
        return None

    candidates = _get_item_candidates(filters)
    if not candidates and category != source_category:
        filters["custom_item_category"] = source_category
        category = source_category
        candidates = _get_item_candidates(filters)
    candidates = [candidate for candidate in candidates if candidate.name not in consumed_items]
    if not candidates:
        _append_limited(
            summary["items_missing"],
            {
                "excel_row": row.get("excel_row"),
                "source_item_code": article_update._clean(row.get("ITEM CODE")),
                "item_name": filters["item_name"],
                "category_article": category,
            },
        )
        return None

    matches = [candidate.name for candidate in candidates if _candidate_matches_row(candidate, row)]
    if len(matches) == 1:
        consumed_items.add(matches[0])
        return matches[0]
    if len(candidates) == 1:
        consumed_items.add(candidates[0].name)
        return candidates[0].name
    if matches:
        item_code = sorted(matches)[0]
        consumed_items.add(item_code)
        summary["resolved_ambiguous_matches"] += 1
        return item_code

    _append_limited(
        summary["ambiguous_matches"],
        {
            "excel_row": row.get("excel_row"),
            "source_item_code": article_update._clean(row.get("ITEM CODE")),
            "item_name": filters["item_name"],
            "category_article": category,
            "candidates": [candidate.name for candidate in candidates[:10]],
        },
    )
    return None


def _rename_identity(row: dict) -> tuple:
    return (
        article_update._key(row.get("ITEM CODE")),
        article_update._key(article_update._row_value(row, "ITEM NAME")),
        article_update._key(row.get("ITEM CATEGORY")),
        article_update._key(row.get("ITEM GROUP")),
        article_update._key(row.get("DEFAULT UNIT OF MEASURE")),
    )


def _get_item_candidates(filters: dict) -> list:
    return frappe.get_all(
        "Item",
        filters=filters,
        fields=["name", "custom_material", "custom_customs_material", "customs_tariff_number"],
        order_by="name asc",
        limit_page_length=0,
    )


def _candidate_matches_row(candidate, row: dict) -> bool:
    material = catalog_import._normalize_material_name(article_update._row_value(row, "MATERIAL"))
    customs_material = catalog_import._normalize_customs_material(article_update._row_value(row, "CUSTOMS MATERIAL"))
    tariff_number = catalog_import._normalize_hs(row.get("HS CODE (10 DIGIT)"))
    return all(
        [
            not material or article_update._key(candidate.get("custom_material")) == article_update._key(material),
            not customs_material
            or article_update._key(candidate.get("custom_customs_material")) == article_update._key(customs_material),
            not tariff_number or article_update._key(candidate.get("customs_tariff_number")) == article_update._key(tariff_number),
        ]
    )


def _sync_category_sequences(max_sequence_by_category: dict[str, int]) -> None:
    for category, sequence in max_sequence_by_category.items():
        if not frappe.db.exists("Item Category", category):
            continue
        current = cint(frappe.db.get_value("Item Category", category, "current_sequence") or 0)
        if sequence > current:
            frappe.db.set_value("Item Category", category, "current_sequence", sequence, update_modified=False)


def _append_limited(rows: list, value: dict, limit: int = 100) -> None:
    if len(rows) < limit:
        rows.append(value)
