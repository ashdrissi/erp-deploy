(function () {
    const PARTY_DOCTYPES = ["Lead", "Prospect", "Customer"];

    PARTY_DOCTYPES.forEach((doctype) => {
        frappe.ui.form.on(doctype, {
            refresh(frm) {
                removeIrrelevantActions(frm);
                syncCreateActions(frm);
                addPartyTools(frm);
                renderPartyWorkspace(frm);
                scheduleDuplicateCheck(frm);
            },
        });
    });

    function syncCreateActions(frm) {
        if (frm.is_new()) return;
        const sync = () => {
            removeNativeCreateActions(frm);
            addOpportunityAction(frm);
            if (["Lead", "Prospect"].includes(frm.doctype)) addCustomerAction(frm);
        };
        [0, 250, 800].forEach((delay) => setTimeout(sync, delay));
    }

    function addOpportunityAction(frm) {
        const button = frm.add_custom_button(__("Opportunity"), async () => {
            const response = await frappe.call({
                method: "orderlift.orderlift_crm.party_management.prepare_opportunity_from_party",
                args: { party_type: frm.doctype, source_name: frm.doc.name },
                freeze: true,
                freeze_message: __("Preparing opportunity..."),
            });
            const doc = response.message;
            if (!doc) return;
            frappe.model.sync(doc);
            frappe.route_options = { orderlift_skip_opportunity_preform: 1 };
            frappe.set_route("Form", "Opportunity", doc.name);
        }, __("Create"));
        $(button).attr("data-orderlift-party-action", "opportunity");
    }

    function addCustomerAction(frm) {
        const button = frm.add_custom_button(__("Customer"), async () => {
            const response = await frappe.call({
                method: "orderlift.orderlift_crm.party_management.convert_party_to_customer",
                args: { party_type: frm.doctype, party_name: frm.doc.name },
                freeze: true,
                freeze_message: __("Converting party..."),
            });
            const customer = response.message && response.message.name;
            if (customer) {
                frappe.route_options = {
                    orderlift_skip_duplicate_check: 1,
                    converted_from_type: response.message.converted_from_type || frm.doctype,
                    converted_from_name: response.message.converted_from_name || frm.doc.name,
                };
                frappe.set_route("Form", "Customer", customer);
            }
        }, __("Create"));
        $(button).attr("data-orderlift-party-action", "customer");
    }

    function addPartyTools(frm) {
        if (frm.is_new()) return;
        frm.add_custom_button(__("Add Address"), () => openAddressDialog(frm), __("Party"));
        frm.add_custom_button(__("Add Contact"), () => openContactDialog(frm), __("Party"));
        frm.add_custom_button(__("Check Duplicates"), () => checkDuplicates(frm, true), __("Party"));
    }

    async function renderPartyWorkspace(frm) {
        const field = frm.fields_dict.custom_party_workspace_html;
        if (!field) return;
        if (frm.is_new()) {
            field.$wrapper.html(`<div class="ol-party-empty">${__("Save the party to add contacts and addresses.")}</div>`);
            return;
        }
        field.$wrapper.html(`<div class="text-muted">${__("Loading contacts and addresses...")}</div>`);
        try {
            const response = await frappe.call({
                method: "orderlift.orderlift_crm.party_management.get_party_workspace",
                args: { party_type: frm.doctype, party_name: frm.doc.name },
            });
            field.$wrapper.html(workspaceMarkup(response.message || {}));
            field.$wrapper.find("[data-add-address]").on("click", () => openAddressDialog(frm));
            field.$wrapper.find("[data-add-contact]").on("click", () => openContactDialog(frm));
            field.$wrapper.find("[data-edit-address]").on("click", function () {
                const row = (response.message.addresses || []).find((item) => item.name === $(this).data("edit-address"));
                openAddressDialog(frm, row);
            });
            field.$wrapper.find("[data-edit-contact]").on("click", function () {
                const row = (response.message.contacts || []).find((item) => item.name === $(this).data("edit-contact"));
                openContactDialog(frm, row);
            });
            injectStyles();
        } catch (error) {
            field.$wrapper.html(`<div class="ol-party-empty">${__("Unable to load contacts and addresses.")}</div>`);
        }
    }

    function workspaceMarkup(data) {
        const addresses = data.addresses || [];
        const contacts = data.contacts || [];
        const deals = data.deals || {};
        return `
            <div class="ol-party-workspace">
                <section><header><div><strong>${__("Addresses")}</strong><span>${addresses.length}</span></div><button class="btn btn-xs btn-primary" data-add-address>${__("Add Address")}</button></header>
                    <div class="ol-party-cards">${addresses.length ? addresses.map(addressCard).join("") : emptyCard(__("No address yet"))}</div>
                </section>
                <section><header><div><strong>${__("Contacts")}</strong><span>${contacts.length}</span></div><button class="btn btn-xs btn-primary" data-add-contact>${__("Add Contact")}</button></header>
                    <div class="ol-party-cards">${contacts.length ? contacts.map(contactCard).join("") : emptyCard(__("No contact yet"))}</div>
                </section>
                <section><header><div><strong>${__("Linked Deals")}</strong></div></header>
                    ${dealSection(__("Opportunities"), "Opportunity", deals.opportunities || [])}
                    ${dealSection(__("Quotations"), "Quotation", deals.quotations || [])}
                    ${dealSection(__("Sales Orders"), "Sales Order", deals.sales_orders || [])}
                    ${dealSection(__("Projects"), "Project", deals.projects || [])}
                </section>
            </div>`;
    }

    function addressCard(row) {
        const badges = [row.is_primary_address ? __("Billing") : "", row.is_shipping_address ? __("Shipping") : "", row.custom_is_site_address ? __("Site") : ""].filter(Boolean);
        return `<button class="ol-party-card" data-edit-address="${escape(row.name)}"><strong>${escape(row.address_title || row.name)}</strong><span>${escape([row.address_line1, row.address_line2, row.city, row.country].filter(Boolean).join(", "))}</span><em>${badges.map((badge) => `<b>${escape(badge)}</b>`).join("")}</em></button>`;
    }

    function contactCard(row) {
        return `<button class="ol-party-card" data-edit-contact="${escape(row.name)}"><strong>${escape([row.first_name, row.last_name].filter(Boolean).join(" ") || row.name)}</strong><span>${escape([row.designation, row.mobile_no || row.phone, row.email_id].filter(Boolean).join(" · "))}</span><em>${row.is_primary_contact ? `<b>${__("Primary")}</b>` : ""}</em></button>`;
    }

    function emptyCard(label) {
        return `<div class="ol-party-empty">${escape(label)}</div>`;
    }

    function dealSection(label, doctype, rows) {
        return `<div class="ol-party-deals"><strong>${escape(label)} <span>${rows.length}</span></strong>${rows.length ? rows.map((row) => dealRow(doctype, row)).join("") : `<p>${__("No linked records yet")}</p>`}</div>`;
    }

    function dealRow(doctype, row) {
        const title = row.title || row.project_name || row.customer_name || row.name;
        const status = row.sales_stage || row.custom_project_status || row.status || "";
        const amount = row.grand_total || row.opportunity_amount;
        const meta = [status, amount ? formatAmount(amount) : "", row.transaction_date || ""].filter(Boolean).join(" · ");
        return `<button class="ol-party-deal-row" data-doctype="${escape(doctype)}" data-name="${escape(row.name)}" onclick="frappe.set_route('Form', this.dataset.doctype, this.dataset.name)"><span>${escape(row.name)}</span><strong>${escape(title)}</strong><em>${escape(meta)}</em></button>`;
    }

    function formatAmount(value) {
        if (typeof format_currency === "function") return format_currency(value);
        return frappe.format(value, { fieldtype: "Currency" });
    }

    function openAddressDialog(frm, row = {}) {
        const dialog = new frappe.ui.Dialog({
            title: row.name ? __("Edit Address") : __("Add Address"),
            fields: [
                { fieldname: "address_title", label: __("Address Title"), fieldtype: "Data", reqd: 1, default: row.address_title || partyDisplayName(frm) },
                { fieldname: "address_type", label: __("Address Type"), fieldtype: "Select", options: "Billing\nShipping\nOther", default: row.address_type || "Billing" },
                { fieldname: "address_line1", label: __("Address Line 1"), fieldtype: "Data", reqd: 1, default: row.address_line1 || "" },
                { fieldname: "address_line2", label: __("Address Line 2"), fieldtype: "Data", default: row.address_line2 || "" },
                { fieldname: "city", label: __("City"), fieldtype: "Data", reqd: 1, default: row.city || "" },
                { fieldname: "state", label: __("State / Province"), fieldtype: "Data", default: row.state || "" },
                { fieldname: "country", label: __("Country"), fieldtype: "Link", options: "Country", reqd: 1, default: row.country || "Morocco" },
                { fieldname: "pincode", label: __("Postal Code"), fieldtype: "Data", default: row.pincode || "" },
                { fieldname: "phone", label: __("Phone"), fieldtype: "Data", options: "Phone", default: row.phone || "" },
                { fieldname: "email_id", label: __("Email"), fieldtype: "Data", options: "Email", default: row.email_id || "" },
                { fieldname: "is_primary_address", label: __("Primary Billing Address"), fieldtype: "Check", default: Number(row.is_primary_address || 0) },
                { fieldname: "is_shipping_address", label: __("Primary Shipping Address"), fieldtype: "Check", default: Number(row.is_shipping_address || 0) },
                { fieldname: "custom_is_site_address", label: __("Site / Installation Address"), fieldtype: "Check", default: Number(row.custom_is_site_address || 0) },
            ],
            primary_action_label: __("Save Address"),
            primary_action: async (values) => {
                await frappe.call({ method: "orderlift.orderlift_crm.party_management.save_party_address", args: { party_type: frm.doctype, party_name: frm.doc.name, values: { ...values, name: row.name || "" } }, freeze: true });
                dialog.hide();
                await frm.reload_doc();
            },
        });
        dialog.show();
    }

    function openContactDialog(frm, row = {}) {
        const dialog = new frappe.ui.Dialog({
            title: row.name ? __("Edit Contact") : __("Add Contact"),
            fields: [
                { fieldname: "first_name", label: __("Contact Name"), fieldtype: "Data", reqd: 1, default: row.first_name || "" },
                { fieldname: "last_name", label: __("Last Name"), fieldtype: "Data", default: row.last_name || "" },
                { fieldname: "designation", label: __("Job Title"), fieldtype: "Data", default: row.designation || "" },
                { fieldname: "mobile_no", label: __("Mobile"), fieldtype: "Data", options: "Phone", default: row.mobile_no || "" },
                { fieldname: "phone", label: __("Phone"), fieldtype: "Data", options: "Phone", default: row.phone || "" },
                { fieldname: "email_id", label: __("Email"), fieldtype: "Data", options: "Email", default: row.email_id || "" },
                { fieldname: "is_primary_contact", label: __("Primary Contact"), fieldtype: "Check", default: Number(row.is_primary_contact || 0) },
            ],
            primary_action_label: __("Save Contact"),
            primary_action: async (values) => {
                await frappe.call({ method: "orderlift.orderlift_crm.party_management.save_party_contact", args: { party_type: frm.doctype, party_name: frm.doc.name, values: { ...values, name: row.name || "" } }, freeze: true });
                dialog.hide();
                await frm.reload_doc();
            },
        });
        dialog.show();
    }

    function scheduleDuplicateCheck(frm) {
        if (frappe.route_options && frappe.route_options.orderlift_skip_duplicate_check) {
            frm.__orderliftDuplicateCheckScheduled = true;
            frappe.route_options = null;
            return;
        }
        if (!frm.is_new() || frm.__orderliftDuplicateCheckScheduled) return;
        frm.__orderliftDuplicateCheckScheduled = true;
        setTimeout(() => checkDuplicates(frm, false), 600);
    }

    async function checkDuplicates(frm, manual) {
        const values = partyIdentity(frm);
        if (!Object.values(values).some(Boolean)) {
            if (manual) frappe.show_alert({ message: __("Enter a party name, ICE, phone, or email first."), indicator: "orange" });
            return;
        }
        const response = await frappe.call({ method: "orderlift.orderlift_crm.party_management.check_party_duplicates", args: { party_type: frm.doctype, party_name: frm.is_new() ? "" : frm.doc.name, values } });
        const matches = response.message || [];
        if (!matches.length) {
            if (manual) frappe.show_alert({ message: __("No possible duplicate found."), indicator: "green" });
            return;
        }
        const dialog = new frappe.ui.Dialog({ title: __("Possible Existing Party"), fields: [{ fieldname: "matches", fieldtype: "HTML" }] });
        dialog.fields_dict.matches.$wrapper.html(`<div class="ol-duplicate-list">${matches.map((match, index) => `<button data-match-index="${index}" data-type="${escape(match.party_type)}" data-name="${escape(match.party_name)}"><strong>${escape(match.display_name)}</strong><span>${escape([match.party_type, match.company, match.reasons.join(", ")].filter(Boolean).join(" · "))}</span><em>${match.requires_access_request ? __("Request access") : __("Open existing")}</em></button>`).join("")}</div>`);
        dialog.fields_dict.matches.$wrapper.find("button").on("click", async function () {
            const match = matches[Number($(this).data("match-index"))];
            if (!match.requires_access_request) {
                frappe.set_route("Form", $(this).data("type"), $(this).data("name"));
                dialog.hide();
                return;
            }
            const company = frm.doc.custom_company || frappe.boot?.orderlift_company_access?.current_company || "";
            const request = await frappe.call({
                method: "orderlift.orderlift_crm.party_management.request_duplicate_reuse",
                args: { values, requested_company: company, reason: __("Reuse possible duplicate from {0}", [frm.doctype]) },
                freeze: true,
            });
            dialog.hide();
            frappe.msgprint(__("Company access request {0} is waiting for approval.", [(request.message || {}).name || ""]));
        });
        dialog.show();
        injectStyles();
    }

    function removeIrrelevantActions(frm) {
        const remove = () => {
            const forbidden = [__("Pricing Rule"), __("Create Pricing Rule"), __("Change company"), __("Add to Prospect")].map((value) => value.toLowerCase());
            $(frm.page.wrapper).find("button, a.dropdown-item").each(function () {
                const label = ($(this).text() || "").trim().toLowerCase();
                if (forbidden.some((value) => label === value || label.includes(value))) $(this).remove();
                if (!$(this).is("[data-orderlift-party-action]") && [__("Opportunity"), __("Create Opportunity")].map((value) => value.toLowerCase()).includes(label)) {
                    $(this).remove();
                    return;
                }
                if (["Lead", "Prospect"].includes(frm.doctype) && !$(this).is("[data-orderlift-party-action]") && [__("Customer"), __("Convert to Customer")].map((value) => value.toLowerCase()).includes(label)) {
                    $(this).remove();
                }
            });
        };
        [0, 250, 800].forEach((delay) => setTimeout(remove, delay));
    }

    function removeNativeCreateActions(frm) {
        const createLabels = [__("Opportunity"), __("Create Opportunity")].map((value) => value.toLowerCase());
        if (["Lead", "Prospect"].includes(frm.doctype)) {
            createLabels.push(__("Customer").toLowerCase(), __("Convert to Customer").toLowerCase());
        }
        $(frm.page.wrapper).find("button, a.dropdown-item").each(function () {
            const label = ($(this).text() || "").trim().toLowerCase();
            if (createLabels.includes(label)) $(this).remove();
        });
    }

    function partyIdentity(frm) {
        return {
            party_name: frm.doc.customer_name || frm.doc.company_name || frm.doc.lead_name || "",
            contact_name: [frm.doc.first_name, frm.doc.last_name].filter(Boolean).join(" "),
            tax_id: frm.doc.tax_id || frm.doc.custom_tax_id || "",
            email_id: frm.doc.email_id || "",
            mobile_no: frm.doc.mobile_no || frm.doc.phone || frm.doc.whatsapp_no || "",
        };
    }

    function partyDisplayName(frm) { return frm.doc.customer_name || frm.doc.company_name || frm.doc.lead_name || frm.doc.name || ""; }
    function escape(value) { return frappe.utils.escape_html(String(value || "")); }
    function injectStyles() {
        if (document.getElementById("ol-party-workspace-styles")) return;
        $("<style id='ol-party-workspace-styles'>").text(`.ol-party-workspace{display:grid;grid-template-columns:minmax(0,1fr);gap:14px;margin:8px 0 16px;width:100%}.ol-party-workspace section{width:100%;border:1px solid var(--border-color);border-radius:12px;background:var(--fg-color);padding:14px}.ol-party-workspace header{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}.ol-party-workspace header strong{font-size:13px}.ol-party-workspace header span{margin-left:6px;color:var(--text-muted)}.ol-party-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:8px}.ol-party-card{display:grid;gap:3px;text-align:left;border:1px solid var(--border-color);border-radius:9px;background:var(--control-bg);padding:10px;color:var(--text-color)}.ol-party-card span{font-size:11px;color:var(--text-muted)}.ol-party-card em{display:flex;gap:4px;font-style:normal}.ol-party-card b{font-size:9px;border-radius:999px;background:var(--blue-50);color:var(--blue-600);padding:2px 6px}.ol-party-deals{display:grid;gap:6px;margin-top:10px}.ol-party-deals>strong{font-size:12px}.ol-party-deals>strong span{color:var(--text-muted);font-weight:400}.ol-party-deals p{margin:0;color:var(--text-muted);font-size:11px}.ol-party-deal-row{display:grid;grid-template-columns:150px minmax(0,1fr) 220px;gap:8px;align-items:center;text-align:left;border:1px solid var(--border-color);border-radius:8px;background:var(--control-bg);padding:8px;color:var(--text-color)}.ol-party-deal-row span,.ol-party-deal-row em{font-size:11px;color:var(--text-muted);font-style:normal}.ol-party-empty{padding:18px;border:1px dashed var(--border-color);border-radius:9px;color:var(--text-muted);text-align:center}.ol-duplicate-list{display:grid;gap:8px}.ol-duplicate-list button{display:grid;text-align:left;padding:10px;border:1px solid var(--border-color);border-radius:9px;background:var(--fg-color)}.ol-duplicate-list span{font-size:11px;color:var(--text-muted)}.ol-duplicate-list em{margin-top:5px;color:var(--primary);font-size:11px;font-style:normal;font-weight:700}@media(max-width:767px){.ol-party-workspace section{padding:10px}.ol-party-cards{grid-template-columns:1fr}.ol-party-deal-row{grid-template-columns:1fr}}`).appendTo(document.head);
    }
})();
