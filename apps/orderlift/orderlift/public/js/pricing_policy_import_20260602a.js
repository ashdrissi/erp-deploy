(function () {
    if (window.__orderlift_pricing_policy_import_20260602a_installed) return;
    window.__orderlift_pricing_policy_import_20260602a_installed = true;

    const SUPPORTED_DOCTYPES = new Set(["Pricing Benchmark Policy", "Pricing Customs Policy"]);

    for (const doctype of SUPPORTED_DOCTYPES) {
        frappe.ui.form.on(doctype, {
            refresh(frm) {
                addPolicyImportButton(frm);
            },
        });
    }

    async function addPolicyImportButton(frm) {
        if (!SUPPORTED_DOCTYPES.has(frm.doctype)) return;
        if (frm.__orderlift_policy_import_loading) return;
        frm.__orderlift_policy_import_loading = true;
        try {
            const response = await frappe.call({
                method: "orderlift.orderlift_sales.utils.policy_import.get_policy_import_context",
                args: { policy_doctype: frm.doctype },
            });
            const context = response.message || {};
            if (!context.can_import) return;
            const label = frm.is_new() ? __("Import from Existing Policy") : __("Duplicate to Company");
            frm.add_custom_button(label, () => showPolicyImportDialog(frm, context));
        } catch (error) {
            console.error("Orderlift policy import context failed", error);
        } finally {
            frm.__orderlift_policy_import_loading = false;
        }
    }

    function showPolicyImportDialog(frm, context) {
        const currentCompany = context.current_company || "";
        const sourcePolicy = frm.is_new() ? "" : frm.doc.name;
        const targetName = defaultTargetPolicyName(frm);
        const companies = context.companies || [];
        const dialog = new frappe.ui.Dialog({
            title: frm.is_new() ? __("Import from Existing Policy") : __("Duplicate Policy to Company"),
            fields: [
                {
                    fieldname: "source_policy",
                    fieldtype: "Link",
                    label: __("Source Policy"),
                    options: frm.doctype,
                    default: sourcePolicy,
                    read_only: sourcePolicy ? 1 : 0,
                    reqd: 1,
                },
                {
                    fieldname: "target_policy_name",
                    fieldtype: "Data",
                    label: __("New Policy Name"),
                    default: targetName,
                    reqd: 1,
                    description: __("A new policy document will be created for the selected company."),
                },
                {
                    fieldname: "target_company",
                    fieldtype: "Link",
                    label: __("Target Company"),
                    options: "Company",
                    default: currentCompany,
                    reqd: 1,
                    get_query: () => ({
                        filters: companies.length ? { name: ["in", companies] } : {},
                    }),
                },
                {
                    fieldname: "confirm_html",
                    fieldtype: "HTML",
                    options: `<div class="text-muted" style="line-height:1.5">${frappe.utils.escape_html(__("This creates a new policy and copies all policy rows. It will not overwrite existing policies."))}</div>`,
                },
            ],
            primary_action_label: __("Import Policy"),
            primary_action(values) {
                frappe.confirm(
                    __("Create policy {0} for company {1}?", [
                        values.target_policy_name,
                        values.target_company || currentCompany || "-",
                    ]),
                    async () => {
                        const result = await importPolicy(frm.doctype, values);
                        dialog.hide();
                        if (result.policy) {
                            frappe.set_route("Form", frm.doctype, result.policy);
                        }
                    }
                );
            },
        });
        dialog.show();
    }

    function defaultTargetPolicyName(frm) {
        const baseName = (frm.doc.policy_name || frm.doc.name || "").trim();
        if (!baseName) return "";
        return frm.is_new() ? baseName : `${baseName} - Copy`;
    }

    async function importPolicy(policyDoctype, values) {
        const response = await frappe.call({
            method: "orderlift.orderlift_sales.utils.policy_import.import_policy_from_existing",
            args: {
                policy_doctype: policyDoctype,
                source_policy: values.source_policy,
                target_policy_name: values.target_policy_name,
                target_company: values.target_company,
            },
            freeze: true,
            freeze_message: __("Importing Policy..."),
        });
        const result = response.message || {};
        frappe.show_alert({
            message: __("Created policy {0}.", [result.policy_name || values.target_policy_name]),
            indicator: "green",
        }, 8);
        return result;
    }
})();
