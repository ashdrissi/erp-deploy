// SAV Ticket — client-side form logic

frappe.ui.form.on("SAV Ticket", {
    refresh(frm) {
        _set_technician_filter(frm);
        _render_status_actions(frm);
        _show_priority_indicator(frm);
    },

    status(frm) {
        _render_status_actions(frm);
    },

    assigned_technician(frm) {
        // Auto-set intervention date to today when a technician is chosen
        if (frm.doc.assigned_technician && !frm.doc.intervention_date) {
            frm.set_value("intervention_date", frappe.datetime.get_today());
        }
    },
});

// ── Filters ──────────────────────────────────────────────────────────────────

function _set_technician_filter(frm) {
    frm.set_query("assigned_technician", () => ({
        query: "orderlift.orderlift_sav.doctype.sav_ticket.sav_ticket.get_technicians",
    }));
}

// ── Custom action buttons ─────────────────────────────────────────────────────

function _render_status_actions(frm) {
    frm.clear_custom_buttons();

    if (frm.is_new()) return;

    const status = frm.doc.status;

    // Open → Assigned
    if (status === "Open") {
        frm.add_custom_button(__("Assigner un technicien"), () => {
            _dialog_assign_technician(frm);
        }, __("Actions"));
    }

    // Assigned → In Progress (technician self-service)
    if (status === "Assigned") {
        frm.add_custom_button(__("Démarrer l'intervention"), () => {
            _update_status(frm, "In Progress");
        }, __("Actions"));
    }

    // In Progress → Resolved (requires report)
    if (status === "In Progress") {
        frm.add_custom_button(__("Soumettre le rapport"), () => {
            if (!(frm.doc.resolution_report || "").trim()) {
                frappe.msgprint({
                    title: __("Rapport obligatoire"),
                    message: __("Veuillez renseigner le rapport de résolution avant de clôturer."),
                    indicator: "red",
                });
                return;
            }
            _update_status(frm, "Resolved");
        }, __("Actions"));
    }

    // Resolved → Closed or rejected (manager)
    if (status === "Resolved") {
        frm.add_custom_button(__("Valider la clôture"), () => {
            _update_status(frm, "Closed");
        }, __("Actions"));

        frm.add_custom_button(__("Rejeter — Renvoyer en cours"), () => {
            _dialog_reject_closure(frm);
        }, __("Actions"));
    }
}

// ── Dialogs ───────────────────────────────────────────────────────────────────

function _dialog_assign_technician(frm) {
    const d = new frappe.ui.Dialog({
        title: __("Assigner un technicien"),
        fields: [
            {
                fieldname: "technician",
                fieldtype: "Link",
                label: __("Technicien"),
                options: "User",
                reqd: 1,
                get_query: () => ({
                    query: "orderlift.orderlift_sav.doctype.sav_ticket.sav_ticket.get_technicians",
                }),
            },
            {
                fieldname: "intervention_date",
                fieldtype: "Date",
                label: __("Date d'intervention"),
                default: frappe.datetime.get_today(),
            },
        ],
        primary_action_label: __("Assigner"),
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
        title: __("Rejeter la clôture"),
        fields: [
            {
                fieldname: "manager_comment",
                fieldtype: "Small Text",
                label: __("Commentaire du responsable"),
                reqd: 1,
            },
        ],
        primary_action_label: __("Rejeter"),
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
        __("Passer le ticket en statut « {0} » ?", [new_status]),
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
