// SAV Ticket — client-side form logic (v3 — full auto-fill + native links)

frappe.ui.form.on("SAV Ticket", {
    refresh(frm) {
        _set_technician_filter(frm);
        _render_status_actions(frm);
        _show_priority_indicator(frm);
        _render_context_badges(frm);
        _render_quick_actions(frm);
    },

    setup(frm) {
        // Set fetch_on for customer -> contact
        frm.set_df_property("contact", "fetch_from", "customer.customer_primary_contact");
    },

    onload_post_render(frm) {
        _hide_auto_sections_if_empty(frm);
    },

    status(frm) {
        _render_status_actions(frm);
    },

    assigned_technician(frm) {
        if (frm.doc.assigned_technician && !frm.doc.intervention_date) {
            frm.set_value("intervention_date", frappe.datetime.get_today());
        }
    },

    defect_type(frm) {
        _toggle_defect_sections(frm);
    },

    serial_no(frm) {
        if (frm.doc.serial_no && frm.doc.__islocal) {
            _resolve_from_serial(frm);
        }
    },

    sales_order(frm) {
        if (frm.doc.sales_order && !frm.doc.serial_no) {
            _resolve_from_so(frm);
        }
    },

    delivery_note(frm) {
        if (frm.doc.delivery_note && !frm.doc.serial_no && !frm.doc.sales_order) {
            _resolve_from_dn(frm);
        }
    },

    customer(frm) {
        if (frm.doc.customer && !frm.doc.serial_no && !frm.doc.sales_order && !frm.doc.delivery_note) {
            _resolve_from_customer(frm);
        }
    },

    installation_project(frm) {
        if (frm.doc.installation_project) {
            frm.trigger("installation_project");
        }
    },
});

// ── Auto-fill cascade ────────────────────────────────────────────────────────

function _resolve_from_serial(frm) {
    frappe.call({
        method: "orderlift.orderlift_sav.doctype.sav_ticket.auto_fill.resolve_from_serial_no",
        args: { serial_no: frm.doc.serial_no },
        callback(r) {
            if (r.message) {
                const d = r.message;
                if (d.item_concerned) frm.set_value("item_concerned", d.item_concerned);
                if (d.batch) frm.set_value("batch", d.batch);
                if (d.delivery_note) frm.set_value("delivery_note", d.delivery_note);
                if (d.sales_order) frm.set_value("sales_order", d.sales_order);
                if (d.sales_invoice) frm.set_value("sales_invoice", d.sales_invoice);
                if (d.customer) frm.set_value("customer", d.customer);
                if (d.source_delivery_date) frm.set_value("source_delivery_date", d.source_delivery_date);
                if (d.warranty_status) frm.set_value("warranty_status", d.warranty_status);
                if (d.days_since_delivery) frm.set_value("days_since_delivery", d.days_since_delivery);
                if (d.customer_tier) frm.set_value("customer_tier", d.customer_tier);
                if (d.site_address) frm.set_value("site_address", d.site_address);
                if (d.recurrence_count) frm.set_value("recurrence_count", d.recurrence_count);
                if (d.installation_project) frm.set_value("installation_project", d.installation_project);
                _show_resolve_confirmation(frm, __("Serial No resolved — {0} filled").format(d.item_concerned || "context"));
            }
        },
    });
}

function _resolve_from_so(frm) {
    frappe.call({
        method: "orderlift.orderlift_sav.doctype.sav_ticket.auto_fill.resolve_from_sales_order",
        args: { sales_order: frm.doc.sales_order },
        callback(r) {
            if (r.message) {
                const d = r.message;
                if (d.customer) frm.set_value("customer", d.customer);
                if (d.installation_project) frm.set_value("installation_project", d.installation_project);
                if (d.delivery_note) frm.set_value("delivery_note", d.delivery_note);
                if (d.sales_invoice) frm.set_value("sales_invoice", d.sales_invoice);
                if (d.source_delivery_date) frm.set_value("source_delivery_date", d.source_delivery_date);
                if (d.customer_tier) frm.set_value("customer_tier", d.customer_tier);
                if (d.site_address) frm.set_value("site_address", d.site_address);
                if (d.days_since_delivery) frm.set_value("days_since_delivery", d.days_since_delivery);
                if (d.recurrence_count) frm.set_value("recurrence_count", d.recurrence_count);
                _show_resolve_confirmation(frm, __("Sales Order resolved"));
            }
        },
    });
}

function _resolve_from_dn(frm) {
    frappe.call({
        method: "orderlift.orderlift_sav.doctype.sav_ticket.auto_fill.resolve_from_delivery_note",
        args: { delivery_note: frm.doc.delivery_note },
        callback(r) {
            if (r.message) {
                const d = r.message;
                if (d.customer) frm.set_value("customer", d.customer);
                if (d.installation_project) frm.set_value("installation_project", d.installation_project);
                if (d.sales_order) frm.set_value("sales_order", d.sales_order);
                if (d.sales_invoice) frm.set_value("sales_invoice", d.sales_invoice);
                if (d.source_delivery_date) frm.set_value("source_delivery_date", d.source_delivery_date);
                if (d.customer_tier) frm.set_value("customer_tier", d.customer_tier);
                if (d.site_address) frm.set_value("site_address", d.site_address);
                if (d.days_since_delivery) frm.set_value("days_since_delivery", d.days_since_delivery);
                if (d.recurrence_count) frm.set_value("recurrence_count", d.recurrence_count);
                _show_resolve_confirmation(frm, __("Delivery Note resolved"));
            }
        },
    });
}

function _resolve_from_customer(frm) {
    frappe.call({
        method: "orderlift.orderlift_sav.doctype.sav_ticket.auto_fill.resolve_from_customer",
        args: { customer: frm.doc.customer },
        callback(r) {
            if (r.message) {
                const d = r.message;
                if (d.customer_tier) frm.set_value("customer_tier", d.customer_tier);
                if (d.site_address) frm.set_value("site_address", d.site_address);
                if (d.recurrence_count) frm.set_value("recurrence_count", d.recurrence_count);
            }
        },
    });
}

function _show_resolve_confirmation(frm, message) {
    frappe.show_alert({
        message: message,
        indicator: "green",
    });
}

// ── Defect type section toggles ──────────────────────────────────────────────

function _toggle_defect_sections(frm) {
    const dt = frm.doc.defect_type;

    // Installation Defect section
    frm.toggle_display("section_break_installation", dt === "Installation Defect");

    // Quality section
    frm.toggle_display("section_break_quality", ["Product Defect", "Supplier Defect"].includes(dt));

    // Purchase Receipt field
    frm.toggle_reqd("purchase_receipt", dt === "Supplier Defect");
    frm.toggle_reqd("installation_project", dt === "Installation Defect");
    frm.toggle_reqd("item_concerned", dt === "Product Defect");
}

// ── Context badges ───────────────────────────────────────────────────────────

function _render_context_badges(frm) {
    if (frm.is_new()) return;

    const warranty_indicator = (frm.doc.warranty_status || "").includes("En garantie")
        ? "green"
        : (frm.doc.warranty_status || "").includes("Expirée")
        ? "red"
        : "orange";

    if (frm.doc.recurrence_count > 0) {
        frm.dashboard.add_indicator(
            __("Recurrence: {0}", [frm.doc.recurrence_count]),
            frm.doc.recurrence_count >= 3 ? "red" : "orange"
        );
    }

    if (frm.doc.warranty_status) {
        frm.dashboard.add_indicator(frm.doc.warranty_status, warranty_indicator);
    }

    if (frm.doc.severity) {
        const severity_colours = {
            Low: "green",
            Medium: "blue",
            High: "orange",
            Critical: "red",
        };
        frm.dashboard.add_indicator(frm.doc.severity, severity_colours[frm.doc.severity] || "grey");
    }
}

// ── Quick actions ────────────────────────────────────────────────────────────

function _render_quick_actions(frm) {
    if (frm.is_new()) return;

    // Create Task button
    if (frm.doc.assigned_technician && !frm.doc.execution_links?.length) {
            frm.add_custom_button(__("Create Task"), () => {
            frm.call("create_task_for_technician").then(r => {
                frm.reload_doc();
            });
        }, __("Actions"));
    }

    // Create replacement Stock Entry
    if (frm.doc.item_concerned) {
        frm.add_custom_button(__("Replacement (stock)"), () => {
            _dialog_stock_action(frm, "Replacement");
        }, __("Actions"));

        frm.add_custom_button(__("Return (stock)"), () => {
            _dialog_stock_action(frm, "Return");
        }, __("Actions"));
    }

    // Supplier defect — vendor return
    if (frm.doc.defect_type === "Supplier Defect" && frm.doc.item_concerned) {
        frm.add_custom_button(__("Vendor Return"), () => {
            _dialog_stock_action(frm, "Vendor Return");
        }, __("Actions"));
    }

    // Resolve manually button (refresh auto-fill)
    if (frm.doc.serial_no) {
        frm.add_custom_button(__("Re-run resolution"), () => {
            _resolve_from_serial(frm);
        }, __("Actions"));
    }
}

function _dialog_stock_action(frm, action_type) {
    const d = new frappe.ui.Dialog({
        title: __("Stock Action — {0}", [action_type]),
        fields: [
            {
                fieldname: "target_warehouse",
                fieldtype: "Link",
                label: __("Target Warehouse"),
                options: "Warehouse",
                reqd: 1,
            },
        ],
        primary_action_label: __("Create"),
        primary_action(values) {
            frm.call("create_stock_entry", {
                action_type: action_type,
                target_warehouse: values.target_warehouse,
            }).then(() => {
                d.hide();
                frm.reload_doc();
            });
        },
    });
    d.show();
}

// ── Filters ──────────────────────────────────────────────────────────────────

function _set_technician_filter(frm) {
    frm.set_query("assigned_technician", () => ({
        query: "orderlift.orderlift_sav.doctype.sav_ticket.sav_ticket.get_technicians",
    }));

    // Filter contact to customer's contacts
    frm.set_query("contact", () => ({
        filters: {
            link_doctype: "Customer",
            link_name: frm.doc.customer,
        },
    }));

    // Filter project to customer's projects
    frm.set_query("installation_project", () => ({
        filters: {
            customer: frm.doc.customer,
        },
    }));
}

// ── Custom action buttons (status workflow) ──────────────────────────────────

function _render_status_actions(frm) {
    frm.clear_custom_buttons();
    _render_quick_actions(frm);

    if (frm.is_new()) return;

    const status = frm.doc.status;

    // Open → Assigned
    if (status === "Open") {
        frm.add_custom_button(__("Assign Technician"), () => {
            _dialog_assign_technician(frm);
        }, __("Actions"));
    }

    // Assigned → In Progress (technician self-service)
    if (status === "Assigned") {
        frm.add_custom_button(__("Start Intervention"), () => {
            _update_status(frm, "In Progress");
        }, __("Actions"));
    }

    // In Progress → Resolved (requires report)
    if (status === "In Progress") {
        frm.add_custom_button(__("Submit Report"), () => {
            if (!(frm.doc.resolution_report || "").trim()) {
                frappe.msgprint({
                    title: __("Report Required"),
                    message: __("Please fill in the resolution report before closing."),
                    indicator: "red",
                });
                return;
            }
            _update_status(frm, "Resolved");
        }, __("Actions"));
    }

    // Resolved → Closed or rejected (manager)
    if (status === "Resolved") {
        frm.add_custom_button(__("Validate Closure"), () => {
            _update_status(frm, "Closed");
        }, __("Actions"));

        frm.add_custom_button(__("Reject — Return to In Progress"), () => {
            _dialog_reject_closure(frm);
        }, __("Actions"));
    }
}

// ── Dialogs ───────────────────────────────────────────────────────────────────

function _dialog_assign_technician(frm) {
    const d = new frappe.ui.Dialog({
        title: __("Assign Technician"),
        fields: [
            {
                fieldname: "technician",
                fieldtype: "Link",
                label: __("Technician"),
                options: "User",
                reqd: 1,
                get_query: () => ({
                    query: "orderlift.orderlift_sav.doctype.sav_ticket.sav_ticket.get_technicians",
                }),
            },
            {
                fieldname: "intervention_date",
                fieldtype: "Date",
                label: __("Intervention Date"),
                default: frappe.datetime.get_today(),
            },
        ],
        primary_action_label: __("Assign"),
        primary_action(values) {
            frm.call("assign_technician", {
                technician: values.technician,
                intervention_date: values.intervention_date,
            }).then(() => {
                d.hide();
                frm.reload_doc();
            });
        },
    });
    d.show();
}

function _dialog_reject_closure(frm) {
    const d = new frappe.ui.Dialog({
        title: __("Reject Closure"),
        fields: [
            {
                fieldname: "manager_comment",
                fieldtype: "Small Text",
                label: __("Manager Comment"),
                reqd: 1,
            },
        ],
        primary_action_label: __("Reject"),
        primary_action(values) {
            frm.call("reject_closure", {
                manager_comment: values.manager_comment,
            }).then(() => {
                d.hide();
                frm.reload_doc();
            });
        },
    });
    d.show();
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function _update_status(frm, new_status) {
    frappe.confirm(
        __("Move ticket to status « {0} »?", [new_status]),
        () => {
            frm.set_value("status", new_status);
            frm.save().then(() => frm.reload_doc());
        }
    );
}

function _show_priority_indicator(frm) {
    const colours = {
        Low: "green",
        Medium: "blue",
        High: "orange",
        Critical: "red",
    };
    const colour = colours[frm.doc.priority] || "grey";
    frm.set_indicator_formatter("priority", () => colour);
}

function _hide_auto_sections_if_empty(frm) {
    // Hide the "Contexte (auto)" section if all derived fields are empty
    const has_context =
        frm.doc.warranty_status ||
        frm.doc.source_delivery_date ||
        frm.doc.days_since_delivery ||
        frm.doc.customer_tier ||
        frm.doc.recurrence_count;

    if (!has_context) {
        frm.toggle_display("section_break_context", false);
    }
}
