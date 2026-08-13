(() => {
  const applyDefaultValidity = (frm) => {
    if (!frm.is_new() || frm.__orderlift_validity_initialized) {
      return;
    }

    frm.__orderlift_validity_initialized = true;
    const validTill = frappe.datetime.add_days(frappe.datetime.get_today(), 15);
    if (frm.doc.valid_till !== validTill) {
      frm.set_value("valid_till", validTill);
    }
  };

  frappe.ui.form.on("Quotation", {
    onload(frm) {
      applyDefaultValidity(frm);
    },
  });
})();
