from __future__ import annotations

from frappe.model.document import Document

from orderlift.annex_chain import validate_annex_integrity
from orderlift.document_templates import validate_annex_document


class OrderliftAnnexDocument(Document):
    def validate(self):
        validate_annex_document(self)
        validate_annex_integrity(self)

    def on_trash(self):
        validate_annex_integrity(self, deleting=True)
        validate_annex_document(self, deleting=True)

    def on_update(self):
        from orderlift.annex_chain import on_annex_update

        on_annex_update(self)

    def after_delete(self):
        from orderlift.annex_chain import on_annex_delete

        on_annex_delete(self)
