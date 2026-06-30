import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt


DEFAULT_INTERNAL_DIMENSIONS_CM = {
    "20ft": (589.8, 235.2, 239.3),
    "40ft": (1203.2, 235.2, 239.3),
    "12m3 Van": (370.0, 175.0, 185.0),
}
DERIVED_DIMENSION_WIDTH_CM = 240.0
DERIVED_DIMENSION_HEIGHT_CM = 220.0


def derive_internal_dimensions_cm(max_volume_m3):
    max_volume_m3 = flt(max_volume_m3)
    if max_volume_m3 <= 0:
        return 0.0, 0.0, 0.0
    length_cm = (max_volume_m3 * 1000000.0) / (DERIVED_DIMENSION_WIDTH_CM * DERIVED_DIMENSION_HEIGHT_CM)
    return length_cm, DERIVED_DIMENSION_WIDTH_CM, DERIVED_DIMENSION_HEIGHT_CM


class ContainerProfile(Document):
    def validate(self):
        self.cost_rank = cint(self.cost_rank or 100)
        self._set_default_dimensions()
        self.length_cm = flt(self.length_cm)
        self.width_cm = flt(self.width_cm)
        self.height_cm = flt(self.height_cm)
        self.max_weight_kg = flt(self.max_weight_kg)
        self.max_volume_m3 = flt(self.max_volume_m3)

        if self.max_weight_kg <= 0:
            frappe.throw("Max Weight (kg) must be greater than zero.")
        if self.max_volume_m3 <= 0:
            frappe.throw("Max Volume (m3) must be greater than zero.")
        if self.length_cm <= 0 or self.width_cm <= 0 or self.height_cm <= 0:
            frappe.throw("Internal Length, Width, and Height are required for 3D container planning.")

    def _set_default_dimensions(self):
        if flt(self.length_cm) > 0 or flt(self.width_cm) > 0 or flt(self.height_cm) > 0:
            return
        dims = DEFAULT_INTERNAL_DIMENSIONS_CM.get(self.container_type)
        if not dims:
            dims = derive_internal_dimensions_cm(self.max_volume_m3)
        self.length_cm, self.width_cm, self.height_cm = dims
