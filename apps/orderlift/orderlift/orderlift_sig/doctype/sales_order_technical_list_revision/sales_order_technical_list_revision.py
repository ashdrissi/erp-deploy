from __future__ import annotations

from frappe.model.document import Document

from orderlift.orderlift_sig import technical_list


class SalesOrderTechnicalListRevision(Document):
    def after_insert(self):
        technical_list.initialize_revision_manifest(self)

    def before_validate(self):
        technical_list.prepare_revision_items(self)

    def validate(self):
        technical_list.validate_revision(self)

    def before_submit(self):
        technical_list.validate_revision(self, for_submit=True)
        from orderlift.annex_chain import on_technical_revision_submit

        on_technical_revision_submit(self)

    def on_submit(self):
        technical_list.submit_revision(self)

    def before_cancel(self):
        technical_list.validate_revision_cancellation(self)

    def on_cancel(self):
        technical_list.cancel_revision(self)

    def after_delete(self):
        technical_list.cleanup_revision_pointers(self)
