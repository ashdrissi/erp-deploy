from __future__ import annotations

from frappe.model.document import Document

from orderlift.orderlift_sig import technical_list


class SalesOrderTechnicalList(Document):
    def validate(self):
        technical_list.validate_technical_list(self)
