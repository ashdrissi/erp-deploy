from __future__ import annotations

import inspect

__version__ = "1.0.0"


def _patch_round_floats_in_compatibility() -> None:
    """Bridge ERPNext/Frappe version mismatch for round_floats_in.

    This production bench has an ERPNext build that calls
    ``Document.round_floats_in(..., do_not_round_fields=...)`` while the live
    Frappe build only supports ``round_floats_in(self, doc, fieldnames=None)``.
    Patch the method once so Purchase Order / taxes-and-totals flows keep
    working until the underlying app versions are aligned.
    """

    try:
        from frappe.model.document import Document
    except Exception:
        return

    if getattr(Document, "_orderlift_round_floats_compat", False):
        return

    params = inspect.signature(Document.round_floats_in).parameters
    if "do_not_round_fields" in params:
        Document._orderlift_round_floats_compat = True
        return

    original = Document.round_floats_in

    def round_floats_in_compat(self, doc, fieldnames=None, do_not_round_fields=None):
        excluded = {field for field in (do_not_round_fields or []) if field}

        if fieldnames is not None and excluded:
            fieldnames = [field for field in fieldnames if field not in excluded]

        if fieldnames is None and excluded:
            fieldnames = (
                df.fieldname
                for df in doc.meta.get("fields", {"fieldtype": ["in", ["Currency", "Float", "Percent"]]})
                if df.fieldname not in excluded
            )

        return original(self, doc, fieldnames=fieldnames)

    Document.round_floats_in = round_floats_in_compat
    Document._orderlift_round_floats_compat = True


_patch_round_floats_in_compatibility()
