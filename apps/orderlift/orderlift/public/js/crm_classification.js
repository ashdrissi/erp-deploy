(function () {
    const PARTY_DOCTYPES = ["Lead", "Prospect", "Customer"];
    const OPPORTUNITY_ITEM_PRICING_FIELDS = ["rate", "amount", "base_rate", "base_amount"];
    let OPPORTUNITY_STATUS_COLORS = null;
    let OPPORTUNITY_STATUS_COLORS_PROMISE = null;

    PARTY_DOCTYPES.forEach((doctype) => {
        frappe.ui.form.on(doctype, {
            refresh(frm) {
                loadCompanyBusinessTypes(frm, true);
                setupPartySegmentQueries(frm);
                renderPartyClassificationBar(frm);
                renderCampaignHistory(frm);
            },
            company(frm) {
                loadCompanyBusinessTypes(frm, true);
            },
            represents_company(frm) {
                loadCompanyBusinessTypes(frm, true);
            },
            custom_crm_segments_add(frm) {
                setupPartySegmentQueries(frm);
                renderPartyClassificationBar(frm);
            },
            custom_crm_segments_remove(frm) {
                renderPartyClassificationBar(frm);
            },
        });
    });

    frappe.ui.form.on("Opportunity", {
        refresh(frm) {
            clearInvalidNewOpportunityStage(frm);
            if (showOpportunityPreFormIfNeeded(frm)) return;
            setupOpportunityResponsiveComments(frm);
            addOpportunityVoiceCommentButton(frm);
            injectOpportunityVoiceCommentControl(frm);
            setupOpportunitySegmentQueries(frm);
            setupOpportunityQuickActions(frm);
            hideOpportunityItemPricingFields(frm);
            defaultOpportunityOwner(frm);
            loadCompanyBusinessTypes(frm, true);
            renderOpportunityStatusBar(frm);
            syncOpportunityPartyDefaults(frm, false);
            loadOpportunityStatusColors().then(() => renderOpportunityStatusBar(frm));
        },
        timeline_refresh(frm) {
            setupOpportunityResponsiveComments(frm);
            injectOpportunityVoiceCommentControl(frm);
        },
        opportunity_from(frm) {
            frm._orderlift_party_segments = [];
            frm._orderlift_auto_values = {};
            if (frm.doc.party_name) {
                frm.set_value("party_name", "");
            }
            if (frm.doc.custom_crm_business_type) {
                frm.set_value("custom_crm_business_type", "");
            }
            if (frm.doc.custom_crm_segment) {
                frm.set_value("custom_crm_segment", "");
            }
            setupOpportunitySegmentQueries(frm);
            renderOpportunityStatusBar(frm);
        },
        party_name(frm) {
            syncOpportunityPartyDefaults(frm, true);
        },
        company(frm) {
            loadCompanyBusinessTypes(frm, true);
        },
        sales_stage(frm) {
            renderOpportunityStatusBar(frm);
        },
        status(frm) {
            renderOpportunityStatusBar(frm);
        },
        custom_crm_business_type(frm) {
            if (frm.doc.custom_crm_segment) {
                frm.set_value("custom_crm_segment", "");
            }
            renderOpportunityStatusBar(frm);
        },
        custom_crm_segment(frm) {
            renderOpportunityStatusBar(frm);
        },
    });

    function clearInvalidNewOpportunityStage(frm) {
        if (frm.is_new() && frm.doc.sales_stage === "Prospecting") {
            frm.set_value("sales_stage", "");
        }
    }

    frappe.ui.form.on("Opportunity Item", {
        form_render(frm) {
            hideOpportunityItemPricingFields(frm);
        },
        items_add(frm) {
            hideOpportunityItemPricingFields(frm);
        },
    });

    function hideOpportunityItemPricingFields(frm) {
        if (!frm || frm.doctype !== "Opportunity" || !frm.fields_dict || !frm.fields_dict.items) return;
        const grid = frm.fields_dict.items.grid;
        if (!grid) return;

        OPPORTUNITY_ITEM_PRICING_FIELDS.forEach((fieldname) => {
            if (typeof grid.update_docfield_property === "function") {
                grid.update_docfield_property(fieldname, "hidden", 1);
                grid.update_docfield_property(fieldname, "in_list_view", 0);
                grid.update_docfield_property(fieldname, "reqd", 0);
            }
            const field = grid.get_field && grid.get_field(fieldname);
            if (field && field.df) {
                field.df.hidden = 1;
                field.df.in_list_view = 0;
                field.df.reqd = 0;
            }
        });
        if (!grid.__orderlift_pricing_fields_hidden && typeof grid.refresh === "function") {
            grid.__orderlift_pricing_fields_hidden = true;
            grid.refresh();
        }
    }

    function showOpportunityPreFormIfNeeded(frm) {
        if (!frm.is_new() || frm._orderlift_creating_draft) return false;
        frm._orderlift_creating_draft = true;
        resolveActiveCompany().then((company) => showOpportunityPreFormDialog({
            company: (frappe.route_options || {}).company || company,
            business_type: (frappe.route_options || {}).custom_crm_business_type || "",
            segment: (frappe.route_options || {}).custom_crm_segment || "",
        })).finally(() => {
            frm._orderlift_creating_draft = false;
        });
        return true;
    }

    async function showOpportunityPreFormDialog(defaults = {}) {
        const routeOptions = frappe.route_options || {};
        const company = defaults.company || routeOptions.company || activeCompany();
        const businessType = defaults.business_type || routeOptions.custom_crm_business_type || "";
        const segment = defaults.segment || routeOptions.custom_crm_segment || "";
        const dialog = new frappe.ui.Dialog({
            title: __("New Opportunity"),
            fields: [
                { fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: company, reqd: 1 },
                { fieldname: "title", label: __("Title"), fieldtype: "Data", reqd: 1 },
                { fieldname: "party_type", label: __("Party Type"), fieldtype: "Select", options: "Prospect\nCustomer\nLead", default: "Prospect" },
                { fieldname: "party_name", label: __("Existing Client"), fieldtype: "Dynamic Link", options: "party_type" },
                { fieldname: "client_name", label: __("Client Name"), fieldtype: "Data" },
                { fieldname: "phone", label: __("N Tel"), fieldtype: "Data" },
                { fieldname: "tier", label: __("Tier"), fieldtype: "Link", options: "Pricing Tier" },
                { fieldname: "business_type", label: __("Business Type"), fieldtype: "Link", options: "CRM Business Type", default: businessType },
                { fieldname: "segment", label: __("Segment"), fieldtype: "Link", options: "CRM Segment", default: segment },
                { fieldname: "territory", label: __("Territory"), fieldtype: "Link", options: "Territory" },
                { fieldname: "address", label: __("Address"), fieldtype: "Small Text" },
                { fieldname: "comment", label: __("Commentaire"), fieldtype: "Small Text" },
                { fieldname: "attachment", label: __("Attachment"), fieldtype: "Attach" },
            ],
            primary_action_label: __("Create Opportunity"),
            primary_action: async (values) => {
                try {
                    frappe.dom.freeze(__("Creating Opportunity..."));
                    const res = await frappe.call({
                        method: "orderlift.orderlift_crm.api.pipeline.create_opportunity_from_preform",
                        args: { values },
                    });
                    const name = res.message && res.message.name;
                    frappe.dom.unfreeze();
                    dialog.hide();
                    frappe.route_options = null;
                    if (name) frappe.set_route("Form", "Opportunity", name);
                } catch (error) {
                    frappe.dom.unfreeze();
                    console.error("Opportunity pre-form creation failed", error);
                }
            },
        });
        dialog.show();
        lockPreFormCompanyIfRestricted(dialog, company);
        setupPreFormBusinessTypeFilters(dialog);
        setupPreFormPartyDefaults(dialog);
    }

    window.orderliftShowOpportunityPreForm = showOpportunityPreFormDialog;

    function setupPreFormBusinessTypeFilters(dialog) {
        const apply = async () => {
            const company = dialog.get_value("company") || "";
            const res = await frappe.call({
                method: "orderlift.orderlift_crm.company_business_type.get_company_business_type_payload",
                args: { company },
            });
            const data = res.message || {};
            const names = (data.business_types || []).map((row) => row.name).filter(Boolean);
            dialog.set_query("business_type", () => ({ filters: names.length ? { name: ["in", names] } : { is_active: 1 } }));
            if (data.single_business_type && !dialog.get_value("business_type")) {
                dialog.set_value("business_type", data.single_business_type);
            }
        };
        dialog.fields_dict.company.df.onchange = apply;
        dialog.fields_dict.business_type.df.onchange = () => {
            const businessType = dialog.get_value("business_type") || "";
            if (dialog.get_value("segment")) dialog.set_value("segment", "");
            dialog.set_query("segment", () => ({ filters: businessType ? { business_type: businessType, is_active: 1 } : { is_active: 1 } }));
        };
        dialog.set_query("segment", () => ({ filters: { is_active: 1 } }));
        if (dialog.fields_dict.tier) {
            dialog.set_query("tier", () => ({ filters: { is_active: 1 } }));
        }
        apply();
    }

    function setupPreFormPartyDefaults(dialog) {
        const apply = async () => {
            const partyType = dialog.get_value("party_type") || "";
            const partyName = dialog.get_value("party_name") || "";
            if (!partyType || !partyName) return;
            try {
                const res = await frappe.call({
                    method: "orderlift.orderlift_crm.api.pipeline.get_party_defaults",
                    args: { party_type: partyType, party_name: partyName },
                });
                if (dialog.get_value("party_type") !== partyType || dialog.get_value("party_name") !== partyName) return;
                const defaults = res.message || {};
                setDialogValueIfPresent(dialog, "client_name", defaults.display_name);
                setDialogValueIfPresent(dialog, "phone", defaults.mobile || defaults.phone);
                setDialogValueIfPresent(dialog, "tier", defaults.tier);
                setDialogValueIfPresent(dialog, "business_type", defaults.business_type);
                setDialogValueIfPresent(dialog, "segment", defaults.crm_segment);
                setDialogValueIfPresent(dialog, "territory", defaults.territory);
                setDialogValueIfPresent(dialog, "address", defaults.address);
                const businessType = defaults.business_type || "";
                dialog.set_query("segment", () => ({ filters: businessType ? { business_type: businessType, is_active: 1 } : { is_active: 1 } }));
            } catch (error) {
                console.warn("Opportunity party defaults failed", error);
            }
        };
        dialog.fields_dict.party_type.df.onchange = () => {
            if (dialog.get_value("party_name")) dialog.set_value("party_name", "");
        };
        dialog.fields_dict.party_name.df.onchange = apply;
    }

    function setDialogValueIfPresent(dialog, fieldname, value) {
        if (!dialog.fields_dict[fieldname] || value == null || value === "") return;
        dialog.set_value(fieldname, value);
    }

    function activeCompany() {
        const ctx = (window.frappe && frappe.boot && frappe.boot.orderlift_company_access) || {};
        return ctx.current_company || ctx.user_default_company || (ctx.companies || [])[0] || "";
    }

    async function resolveActiveCompany() {
        const fallback = activeCompany();
        try {
            const res = await frappe.call({ method: "orderlift.menu_access.get_current_company_access_payload" });
            const payload = res.message || {};
            if (window.frappe && frappe.boot && payload.current_company) {
                frappe.boot.orderlift_company_access = payload;
            }
            return payload.current_company || fallback;
        } catch (error) {
            console.warn("Unable to refresh active company", error);
            return fallback;
        }
    }

    function canChangePreFormCompany() {
        const adminRoles = ["Administrator", "System Manager", "Developer", "Orderlift Admin"];
        return adminRoles.some((role) => frappe.user && frappe.user.has_role && frappe.user.has_role(role));
    }

    function lockPreFormCompanyIfRestricted(dialog, company) {
        const field = dialog.fields_dict.company;
        if (!field) return;
        if (company && !dialog.get_value("company")) {
            dialog.set_value("company", company);
        }
        if (canChangePreFormCompany()) return;
        field.df.read_only = 1;
        field.refresh();
        if (field.$input) {
            field.$input.prop("readonly", true).addClass("disabled");
        }
        if (field.$wrapper) {
            field.$wrapper.find(".link-btn, .btn-open, .btn-clear, .input-group-btn").hide();
        }
    }

    async function loadCompanyBusinessTypes(frm, applyValues) {
        const company = getDocumentCompany(frm);
        if (!company) {
            frm._orderlift_company_business_types = [];
            if (frm.doctype === "Opportunity") setupOpportunitySegmentQueries(frm);
            else setupPartySegmentQueries(frm);
            return;
        }
        try {
            const res = await frappe.call({
                method: "orderlift.orderlift_crm.company_business_type.get_company_business_type_payload",
                args: { company },
            });
            const data = res.message || {};
            frm._orderlift_company_business_types = data.business_types || [];
            if (frm.doctype === "Opportunity") setupOpportunitySegmentQueries(frm);
            else setupPartySegmentQueries(frm);
            if (frm.doctype === "Opportunity" && applyValues && data.single_business_type && !frm.doc.custom_crm_business_type) {
                await frm.set_value("custom_crm_business_type", data.single_business_type);
            }
            if (frm.doctype === "Opportunity" && frm.doc.custom_crm_business_type && !isAllowedCompanyBusinessType(frm, frm.doc.custom_crm_business_type)) {
                await frm.set_value("custom_crm_business_type", "");
                if (frm.doc.custom_crm_segment) await frm.set_value("custom_crm_segment", "");
            }
            renderOpportunityStatusBar(frm);
        } catch (error) {
            console.error("Unable to load company business types", error);
            frm._orderlift_company_business_types = [];
            if (frm.doctype === "Opportunity") setupOpportunitySegmentQueries(frm);
            else setupPartySegmentQueries(frm);
        }
    }

    function getDocumentCompany(frm) {
        return frm.doc.company || frm.doc.custom_company || frm.doc.represents_company || "";
    }

    function isAllowedCompanyBusinessType(frm, businessType) {
        const names = (frm._orderlift_company_business_types || []).map((row) => row.name).filter(Boolean);
        return !names.length || names.includes(businessType);
    }

    function defaultOpportunityOwner(frm) {
        if (!frm.doc.opportunity_owner && frappe.session && frappe.session.user) {
            frm.set_value("opportunity_owner", frappe.session.user);
        }
    }

    function setupOpportunityQuickActions(frm) {
        if (!frm.fields_dict.custom_quick_actions_html) return;
        frm.fields_dict.custom_quick_actions_html.$wrapper.html(`
            <div class="ol-opportunity-quick-actions">
                <button type="button" class="btn btn-default btn-sm" data-opp-attach>${__("Attachments")}</button>
                <button type="button" class="btn btn-default btn-sm" data-opp-assign>${__("Assign")}</button>
            </div>
        `);
        frm.fields_dict.custom_quick_actions_html.$wrapper.find("[data-opp-attach]").on("click", () => {
            if (frm.attachments && frm.attachments.new_attachment) frm.attachments.new_attachment();
        });
        frm.fields_dict.custom_quick_actions_html.$wrapper.find("[data-opp-assign]").on("click", () => {
            if (frm.assign_to && frm.assign_to.add) frm.assign_to.add();
        });
    }

    function setupOpportunityResponsiveComments(frm) {
        if (frm.wrapper) {
            $(frm.wrapper).addClass("ol-opportunity-form");
        }
    }

    function addOpportunityVoiceCommentButton(frm) {
        if (frm.is_new()) return;
        frm.add_custom_button(__("Voice Comment"), () => showOpportunityVoiceCommentDialog(frm), __("Add"));
    }

    function injectOpportunityVoiceCommentControl(frm) {
        if (frm.is_new()) return;
        [0, 300, 900].forEach((delay) => window.setTimeout(() => {
            injectTimelineVoiceAction(frm);
            injectNotesTabVoiceAction(frm);
            observeNotesTabForVoiceAction(frm);
            const wrapper = frm.footer && frm.footer.wrapper;
            if (!wrapper || !wrapper.length) return;
            const commentBox = wrapper.find(".comment-box");
            if (!commentBox.length || wrapper.find(".ol-voice-comment-inline").length) return;
            $(voiceCommentInlineMarkup()).insertAfter(commentBox);
            wrapper.find("[data-voice-comment-inline]").on("click", () => showOpportunityVoiceCommentDialog(frm));
        }, delay));
    }

    function injectTimelineVoiceAction(frm) {
        const timeline = frm.timeline;
        const actions = timeline && timeline.timeline_actions_wrapper && timeline.timeline_actions_wrapper.find(".action-buttons");
        if (!actions || !actions.length || actions.find("[data-voice-comment-action]").length) return;
        const button = $(`
            <button class="btn btn-xs btn-default action-btn ol-voice-comment-action" data-voice-comment-action>
                ${__("Record Voice Note")}
            </button>
        `);
        button.on("click", () => showOpportunityVoiceCommentDialog(frm));
        actions.prepend(button);
        timeline.timeline_actions_wrapper.show();
    }

    function injectNotesTabVoiceAction(frm) {
        const notesWrapper = frm.fields_dict.notes_html && $(frm.fields_dict.notes_html.wrapper);
        if (!notesWrapper || !notesWrapper.length) return;
        const newNoteButton = notesWrapper.find(".notes-section .new-note-btn").first();
        if (!newNoteButton.length || notesWrapper.find("[data-voice-note-tab-action]").length) return;
        const button = $(`
            <button type="button" class="btn btn-sm small ol-voice-note-tab-action" data-voice-note-tab-action>
                ${__("Record Voice Note")}
            </button>
        `);
        button.on("click", () => showOpportunityVoiceCommentDialog(frm));
        newNoteButton.after(button);
    }

    function observeNotesTabForVoiceAction(frm) {
        if (frm._orderlift_notes_voice_observer) return;
        const notesWrapper = frm.fields_dict.notes_html && frm.fields_dict.notes_html.wrapper;
        if (!notesWrapper) return;
        frm._orderlift_notes_voice_observer = new MutationObserver(() => injectNotesTabVoiceAction(frm));
        frm._orderlift_notes_voice_observer.observe(notesWrapper, { childList: true, subtree: true });
    }

    function voiceCommentInlineMarkup() {
        return `
            <div class="ol-voice-comment-inline">
                <button type="button" class="btn btn-default btn-sm" data-voice-comment-inline>
                    ${__("Record Voice Note")}
                </button>
                <span>${__("Adds a playable audio comment to this Opportunity timeline")}</span>
            </div>
        `;
    }

    function showOpportunityVoiceCommentDialog(frm) {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.MediaRecorder) {
            frappe.msgprint({
                title: __("Voice comments unavailable"),
                message: __("This browser does not support audio recording. Please use a recent Chrome, Edge, Firefox, or Safari browser."),
                indicator: "orange",
            });
            return;
        }

        let recorder = null;
        let stream = null;
        let chunks = [];
        let audioBlob = null;
        let previewUrl = "";
        let startedAt = 0;
        let elapsedSeconds = 0;
        let timer = null;

        const dialog = new frappe.ui.Dialog({
            title: __("Add Voice Comment"),
            fields: [
                { fieldname: "recorder", fieldtype: "HTML" },
                { fieldname: "note", fieldtype: "Small Text", label: __("Optional note") },
            ],
            primary_action_label: __("Save Voice Comment"),
            primary_action: async (values) => {
                if (!audioBlob) {
                    frappe.msgprint(__("Record a voice note before saving."));
                    return;
                }
                try {
                    setDialogPrimaryDisabled(dialog, true);
                    frappe.dom.freeze(__("Saving voice comment..."));
                    const file = await uploadOpportunityVoiceBlob(frm, audioBlob);
                    await frappe.call({
                        method: "orderlift.orderlift_crm.api.voice_comment.add_opportunity_voice_comment",
                        args: {
                            opportunity: frm.doc.name,
                            file: file.name || file.file_url || file.file_name,
                            note: values.note || "",
                            duration: elapsedSeconds,
                        },
                    });
                    frappe.dom.unfreeze();
                    dialog.hide();
                    frappe.show_alert({ message: __("Voice comment added"), indicator: "green" });
                    frm.reload_doc();
                } catch (error) {
                    frappe.dom.unfreeze();
                    setDialogPrimaryDisabled(dialog, false);
                    console.error("Unable to save voice comment", error);
                    frappe.msgprint({
                        title: __("Unable to save voice comment"),
                        message: error.message || __("Check microphone permissions and try again."),
                        indicator: "red",
                    });
                }
            },
        });

        dialog.show();
        dialog.get_field("recorder").$wrapper.html(voiceRecorderMarkup());
        setVoiceRecorderState(dialog, __("Ready to record"), "gray");

        const cleanup = () => {
            if (timer) window.clearInterval(timer);
            timer = null;
            if (recorder && recorder.state === "recording") recorder.stop();
            if (stream) stream.getTracks().forEach((track) => track.stop());
            stream = null;
            if (previewUrl) URL.revokeObjectURL(previewUrl);
            previewUrl = "";
        };

        dialog.$wrapper.on("hidden.bs.modal", cleanup);
        dialog.$wrapper.find("[data-voice-start]").on("click", async () => {
            try {
                audioBlob = null;
                chunks = [];
                if (previewUrl) URL.revokeObjectURL(previewUrl);
                previewUrl = "";
                stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                const mimeType = preferredAudioMimeType();
                recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
                recorder.ondataavailable = (event) => {
                    if (event.data && event.data.size) chunks.push(event.data);
                };
                recorder.onstop = () => {
                    audioBlob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
                    previewUrl = URL.createObjectURL(audioBlob);
                    dialog.$wrapper.find("[data-voice-preview]").html(`<audio controls preload="metadata" src="${previewUrl}" style="width:100%;"></audio>`);
                    dialog.$wrapper.find("[data-voice-start]").prop("disabled", false);
                    dialog.$wrapper.find("[data-voice-stop]").prop("disabled", true);
                    setVoiceRecorderState(dialog, __("Recording ready to save"), "green");
                    if (stream) stream.getTracks().forEach((track) => track.stop());
                    stream = null;
                };
                recorder.start();
                startedAt = Date.now();
                elapsedSeconds = 0;
                dialog.$wrapper.find("[data-voice-start]").prop("disabled", true);
                dialog.$wrapper.find("[data-voice-stop]").prop("disabled", false);
                setVoiceRecorderState(dialog, __("Recording... 0:00"), "red");
                if (timer) window.clearInterval(timer);
                timer = window.setInterval(() => {
                    elapsedSeconds = Math.max(1, Math.round((Date.now() - startedAt) / 1000));
                    setVoiceRecorderState(dialog, `${__("Recording...")} ${formatVoiceDuration(elapsedSeconds)}`, "red");
                }, 500);
            } catch (error) {
                console.error("Unable to start voice recording", error);
                setVoiceRecorderState(dialog, __("Microphone access failed"), "orange");
                frappe.msgprint({
                    title: __("Microphone access failed"),
                    message: __("Allow microphone access for this site, then try again."),
                    indicator: "orange",
                });
            }
        });
        dialog.$wrapper.find("[data-voice-stop]").on("click", () => {
            if (timer) window.clearInterval(timer);
            timer = null;
            elapsedSeconds = Math.max(1, Math.round((Date.now() - startedAt) / 1000));
            if (recorder && recorder.state === "recording") recorder.stop();
        });
    }

    function voiceRecorderMarkup() {
        return `
            <div class="ol-voice-recorder">
                <div class="ol-voice-status" data-voice-status></div>
                <div class="ol-voice-actions">
                    <button type="button" class="btn btn-primary btn-sm" data-voice-start>${__("Start Recording")}</button>
                    <button type="button" class="btn btn-default btn-sm" data-voice-stop disabled>${__("Stop")}</button>
                </div>
                <div class="ol-voice-preview" data-voice-preview></div>
            </div>
        `;
    }

    function setVoiceRecorderState(dialog, message, color) {
        dialog.$wrapper.find("[data-voice-status]").html(`<span class="indicator ${color}">${frappe.utils.escape_html(message)}</span>`);
    }

    function preferredAudioMimeType() {
        const options = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus", "audio/ogg"];
        if (!MediaRecorder.isTypeSupported) return "";
        return options.find((type) => MediaRecorder.isTypeSupported(type)) || "";
    }

    function setDialogPrimaryDisabled(dialog, disabled) {
        const button = dialog.get_primary_btn ? dialog.get_primary_btn() : dialog.$wrapper.find(".modal-footer .btn-primary");
        button.prop("disabled", Boolean(disabled));
    }

    function voiceFilename(frm, blob) {
        const extension = audioExtension(blob.type);
        const timestamp = frappe.datetime.now_datetime().replace(/[^0-9]/g, "");
        return `voice-comment-${frm.doc.name}-${timestamp}${extension}`;
    }

    function audioExtension(mimeType) {
        if (mimeType.includes("mp4")) return ".m4a";
        if (mimeType.includes("ogg")) return ".ogg";
        if (mimeType.includes("wav")) return ".wav";
        return ".webm";
    }

    function formatVoiceDuration(seconds) {
        const minutes = Math.floor(seconds / 60);
        const remainder = String(seconds % 60).padStart(2, "0");
        return `${minutes}:${remainder}`;
    }

    async function uploadOpportunityVoiceBlob(frm, blob) {
        const formData = new FormData();
        formData.append("file", blob, voiceFilename(frm, blob));
        formData.append("doctype", "Opportunity");
        formData.append("docname", frm.doc.name);
        formData.append("is_private", "1");

        const response = await fetch("/api/method/upload_file", {
            method: "POST",
            headers: { "X-Frappe-CSRF-Token": frappe.csrf_token },
            body: formData,
        });
        const data = await response.json();
        if (!response.ok || data.exc) {
            throw new Error((data._server_messages && JSON.parse(data._server_messages)[0]) || data.exception || __("Audio upload failed."));
        }
        return data.message || {};
    }

    frappe.ui.form.on("Quotation", {
        refresh(frm) {
            setupTransactionClassificationQueries(frm);
            syncTransactionPartyClassification(frm, "quotation", false);
            syncTransactionPartyDefaults(frm, "quotation", false);
            renderTransactionClassificationBar(frm, "Quotation");
        },
        quotation_to(frm) {
            syncTransactionPartyClassification(frm, "quotation", true);
            syncTransactionPartyDefaults(frm, "quotation", true);
        },
        party_name(frm) {
            syncTransactionPartyClassification(frm, "quotation", true);
            syncTransactionPartyDefaults(frm, "quotation", true);
        },
        custom_crm_business_type(frm) {
            if (frm.doc.custom_crm_segment) {
                frm.set_value("custom_crm_segment", "");
            }
            setupTransactionClassificationQueries(frm);
            renderTransactionClassificationBar(frm, "Quotation");
        },
        custom_crm_segment(frm) {
            renderTransactionClassificationBar(frm, "Quotation");
        },
    });

    ["Sales Order", "Project"].forEach((doctype) => {
        frappe.ui.form.on(doctype, {
            refresh(frm) {
                setupTransactionClassificationQueries(frm);
            },
            customer(frm) {
                syncTransactionPartyClassification(frm, "customer", false);
            },
            custom_crm_business_type(frm) {
                if (frm.doc.custom_crm_segment) {
                    frm.set_value("custom_crm_segment", "");
                }
                setupTransactionClassificationQueries(frm);
            },
        });
    });

    frappe.ui.form.on("CRM Segment Assignment", {
        business_type(frm, cdt, cdn) {
            const row = locals[cdt][cdn];
            if (row.segment) {
                frappe.model.set_value(cdt, cdn, "segment", "");
            }
        },
        segment(frm) {
            renderPartyClassificationBar(frm);
        },
        is_primary(frm) {
            renderPartyClassificationBar(frm);
        },
    });

    function setupPartySegmentQueries(frm) {
        if (!frm.fields_dict.custom_crm_segments) return;
        frm.set_query("business_type", "custom_crm_segments", () => {
            const filters = { is_active: 1 };
            const companyTypes = unique((frm._orderlift_company_business_types || []).map((row) => row.name).filter(Boolean));
            if (companyTypes.length) filters.name = ["in", companyTypes];
            return { filters };
        });
        frm.set_query("segment", "custom_crm_segments", (_doc, cdt, cdn) => {
            const row = locals[cdt][cdn] || {};
            const filters = { is_active: 1 };
            if (row.business_type) {
                filters.business_type = row.business_type;
            }
            return { filters };
        });
    }

    function setupOpportunitySegmentQueries(frm) {
        frm.set_query("custom_crm_business_type", () => {
            const filters = { is_active: 1 };
            const companyTypes = unique((frm._orderlift_company_business_types || []).map((row) => row.name).filter(Boolean));
            const partyTypes = unique((frm._orderlift_party_segments || []).map((row) => row.business_type).filter(Boolean));
            const businessTypes = companyTypes.length ? companyTypes : partyTypes;
            if (businessTypes.length) {
                filters.name = ["in", businessTypes];
            }
            return { filters };
        });
        frm.set_query("custom_crm_segment", () => {
            const filters = { is_active: 1 };
            const partySegments = frm._orderlift_party_segments || [];
            let segmentNames = partySegments.map((row) => row.segment).filter(Boolean);
            if (frm.doc.custom_crm_business_type) {
                filters.business_type = frm.doc.custom_crm_business_type;
                segmentNames = partySegments
                    .filter((row) => row.business_type === frm.doc.custom_crm_business_type)
                    .map((row) => row.segment)
                    .filter(Boolean);
            }
            segmentNames = unique(segmentNames);
            if (segmentNames.length) {
                filters.name = ["in", segmentNames];
            }
            return { filters };
        });
    }

    function setupTransactionClassificationQueries(frm) {
        if (frm.fields_dict.custom_crm_business_type) {
            frm.set_query("custom_crm_business_type", () => {
                const filters = { is_active: 1 };
                const businessTypes = unique((frm._orderlift_party_segments || []).map((row) => row.business_type).filter(Boolean));
                if (businessTypes.length) {
                    filters.name = ["in", businessTypes];
                }
                return { filters };
            });
        }
        if (frm.fields_dict.custom_crm_segment) {
            frm.set_query("custom_crm_segment", () => {
                const filters = { is_active: 1 };
                const partySegments = frm._orderlift_party_segments || [];
                let segmentNames = partySegments.map((row) => row.segment).filter(Boolean);
                if (frm.doc.custom_crm_business_type) {
                    filters.business_type = frm.doc.custom_crm_business_type;
                    segmentNames = partySegments
                        .filter((row) => row.business_type === frm.doc.custom_crm_business_type)
                        .map((row) => row.segment)
                        .filter(Boolean);
                }
                segmentNames = unique(segmentNames);
                if (segmentNames.length) {
                    filters.name = ["in", segmentNames];
                }
                return { filters };
            });
        }
    }

    async function syncOpportunityPartyClassification(frm, applyValues) {
        if (!frm.doc.opportunity_from || !frm.doc.party_name || !["Lead", "Prospect", "Customer"].includes(frm.doc.opportunity_from)) {
            frm._orderlift_party_segments = [];
            setupOpportunitySegmentQueries(frm);
            return;
        }
        const token = `${frm.doc.opportunity_from}:${frm.doc.party_name}:${Date.now()}`;
        frm._orderlift_party_token = token;
        try {
            const res = await frappe.call({
                method: "orderlift.orderlift_crm.api.pipeline.get_party_crm_classification",
                args: { party_type: frm.doc.opportunity_from, party_name: frm.doc.party_name },
            });
            if (frm._orderlift_party_token !== token) return;
            const data = res.message || {};
            frm._orderlift_party_segments = data.segments || [];
            setupOpportunitySegmentQueries(frm);
            if (applyValues || (!frm.doc.custom_crm_business_type && !frm.doc.custom_crm_segment)) {
                await frm.set_value("custom_crm_business_type", data.business_type || "");
                await frm.set_value("custom_crm_segment", data.crm_segment || "");
            }
            renderOpportunityStatusBar(frm);
        } catch (error) {
            console.error("Unable to load party CRM classification", error);
            frm._orderlift_party_segments = [];
            setupOpportunitySegmentQueries(frm);
        }
    }

    async function syncOpportunityPartyDefaults(frm, applyValues) {
        if (!frm.doc.opportunity_from || !frm.doc.party_name || !PARTY_DOCTYPES.includes(frm.doc.opportunity_from)) {
            frm._orderlift_party_segments = [];
            setupOpportunitySegmentQueries(frm);
            return;
        }
        const token = `${frm.doc.opportunity_from}:${frm.doc.party_name}:${Date.now()}`;
        frm._orderlift_party_token = token;
        try {
            const res = await frappe.call({
                method: "orderlift.orderlift_crm.api.pipeline.get_party_defaults",
                args: { party_type: frm.doc.opportunity_from, party_name: frm.doc.party_name },
            });
            if (frm._orderlift_party_token !== token) return;
            const data = res.message || {};
            frm._orderlift_party_segments = data.segments || [];
            setupOpportunitySegmentQueries(frm);

            const values = {
                custom_crm_business_type: data.business_type || "",
                custom_crm_segment: data.crm_segment || "",
                customer_name: data.display_name || "",
                company: data.company || "",
                industry: data.industry || "",
                territory: data.territory || "",
                city: data.city || "",
                phone: data.phone || "",
                contact_mobile: data.mobile || "",
                contact_email: data.email || "",
                website: data.website || "",
                customer_group: data.customer_group || "",
                custom_tier: data.tier || "",
            };
            for (const [fieldname, value] of Object.entries(values)) {
                await setAutoValue(frm, fieldname, value, applyValues);
            }
            renderOpportunityStatusBar(frm);
        } catch (error) {
            console.error("Unable to load party defaults", error);
            frm._orderlift_party_segments = [];
            setupOpportunitySegmentQueries(frm);
        }
    }

    async function setAutoValue(frm, fieldname, value, applyValues) {
        if (!frm.fields_dict[fieldname] || value === undefined || value === null || value === "") return;
        frm._orderlift_auto_values = frm._orderlift_auto_values || {};
        const current = frm.doc[fieldname] || "";
        const previousAuto = frm._orderlift_auto_values[fieldname] || "";
        if (!applyValues && current) return;
        if (current && previousAuto && current !== previousAuto) return;
        if (current === value) return;
        await frm.set_value(fieldname, value);
        frm._orderlift_auto_values[fieldname] = value;
    }

    async function syncTransactionPartyClassification(frm, mode, applyValues) {
        const partyType = mode === "quotation" ? frm.doc.quotation_to : "Customer";
        const partyName = mode === "quotation" ? frm.doc.party_name : frm.doc.customer;
        if (!partyType || !partyName || !PARTY_DOCTYPES.includes(partyType)) {
            frm._orderlift_party_segments = [];
            setupTransactionClassificationQueries(frm);
            if (frm.doctype === "Quotation") {
                renderTransactionClassificationBar(frm, "Quotation");
            }
            return;
        }
        const token = `${frm.doctype}:${partyType}:${partyName}:${Date.now()}`;
        frm._orderlift_party_token = token;
        try {
            const res = await frappe.call({
                method: "orderlift.orderlift_crm.api.pipeline.get_party_crm_classification",
                args: { party_type: partyType, party_name: partyName },
            });
            if (frm._orderlift_party_token !== token) return;
            const data = res.message || {};
            frm._orderlift_party_segments = data.segments || [];
            setupTransactionClassificationQueries(frm);
            if (applyValues || (!frm.doc.custom_crm_business_type && !frm.doc.custom_crm_segment)) {
                await frm.set_value("custom_crm_business_type", data.business_type || "");
                await frm.set_value("custom_crm_segment", data.crm_segment || "");
            }
            if (frm.doctype === "Quotation") {
                renderTransactionClassificationBar(frm, "Quotation");
            }
        } catch (error) {
            console.error("Unable to load transaction CRM classification", error);
            frm._orderlift_party_segments = [];
            setupTransactionClassificationQueries(frm);
        }
    }

    async function syncTransactionPartyDefaults(frm, mode, applyValues) {
        const partyType = mode === "quotation" ? frm.doc.quotation_to : "Customer";
        const partyName = mode === "quotation" ? frm.doc.party_name : frm.doc.customer;
        if (!partyType || !partyName || !PARTY_DOCTYPES.includes(partyType)) {
            return;
        }
        const token = `${frm.doctype}:${partyType}:${partyName}:defaults:${Date.now()}`;
        frm._orderlift_party_defaults_token = token;
        try {
            const res = await frappe.call({
                method: "orderlift.orderlift_crm.api.pipeline.get_party_defaults",
                args: { party_type: partyType, party_name: partyName },
            });
            if (frm._orderlift_party_defaults_token !== token) return;
            const data = res.message || {};
            const values = {
                customer_name: data.display_name || "",
                territory: data.territory || "",
                customer_address: data.address_name || "",
                address_display: data.address || "",
                contact_person: data.contact_name || "",
                contact_display: data.contact_display || data.email || data.mobile || "",
                contact_mobile: data.mobile || data.phone || "",
                contact_email: data.email || "",
                shipping_address_name: data.address_name || "",
            };
            for (const [fieldname, value] of Object.entries(values)) {
                await setAutoValue(frm, fieldname, value, applyValues);
            }
        } catch (error) {
            console.error("Unable to load transaction party defaults", error);
        }
    }

    function renderPartyClassificationBar(frm) {
        injectCrmClassificationStyles();
        frm.page.inner_toolbar.find(".ol-crm-classification-bar").remove();
        const segments = frm.doc.custom_crm_segments || [];
        const businessTypes = unique(segments.map((row) => row.business_type).filter(Boolean));
        const segmentNames = unique(segments.map((row) => row.segment).filter(Boolean));
        const chips = [
            crmChip(__("CRM Type"), businessTypes.length ? businessTypes.join(" + ") : __("Not set"), "type"),
            crmChip(__("Segments"), segmentNames.length ? segmentNames.join(" + ") : __("Not set"), "segment"),
        ];
        frm.page.inner_toolbar.prepend(`<div class="ol-crm-classification-bar">${chips.join("")}</div>`);
    }

    function renderOpportunityStatusBar(frm) {
        injectCrmClassificationStyles();
        frm.page.inner_toolbar.find(".ol-opportunity-status-bar").remove();
        const chips = [
            crmChip(__("Opportunity Status"), frm.doc.sales_stage || __("Not set"), "status"),
            crmChip(__("Type"), frm.doc.custom_crm_business_type || __("Not set"), "type"),
            crmChip(__("Segment"), frm.doc.custom_crm_segment || __("Not set"), "segment"),
        ];
        frm.page.inner_toolbar.prepend(`<div class="ol-opportunity-status-bar">${chips.join("")}</div>`);
    }

    function renderTransactionClassificationBar(frm, label) {
        injectCrmClassificationStyles();
        frm.page.inner_toolbar.find(".ol-transaction-classification-bar").remove();
        const chips = [
            crmChip(__("Type"), frm.doc.custom_crm_business_type || __("Not set"), "type"),
            crmChip(__("Segment"), frm.doc.custom_crm_segment || __("Not set"), "segment"),
        ];
        frm.page.inner_toolbar.prepend(`
            <div class="ol-transaction-classification-bar" title="${frappe.utils.escape_html(label)} CRM Classification">
                ${chips.join("")}
            </div>
        `);
    }

    async function renderCampaignHistory(frm) {
        if (frm.is_new()) return;
        injectCrmClassificationStyles();
        const wrapper = frm.dashboard && frm.dashboard.wrapper;
        if (!wrapper) return;
        wrapper.find(".ol-campaign-history-panel").remove();
        wrapper.append(`<div class="ol-campaign-history-panel"><div class="ol-history-loading">${__("Loading campaign history...")}</div></div>`);
        try {
            const res = await frappe.call({
                method: "orderlift.orderlift_crm.api.campaign.get_party_campaign_history",
                args: { party_type: frm.doctype, party_name: frm.doc.name },
            });
            const rows = res.message || [];
            wrapper.find(".ol-campaign-history-panel").html(campaignHistoryMarkup(rows));
            wrapper.find(".ol-campaign-history-panel [data-route-doctype]").on("click", function (event) {
                event.preventDefault();
                frappe.set_route("Form", $(this).data("route-doctype"), $(this).data("route-name"));
            });
        } catch (error) {
            console.error("Campaign history failed", error);
            wrapper.find(".ol-campaign-history-panel").html(`<div class="ol-history-empty">${__("Unable to load campaign history.")}</div>`);
        }
    }

    function campaignHistoryMarkup(rows) {
        if (!rows.length) {
            return `<div class="ol-history-head"><strong>${__("Campaign History")}</strong><span>${__("No campaign targets yet")}</span></div>`;
        }
        return `
            <div class="ol-history-head"><strong>${__("Campaign History")}</strong><span>${rows.length} ${__("target records")}</span></div>
            <div class="ol-history-table-wrap">
                <table class="ol-history-table">
                    <thead><tr><th>${__("Campaign")}</th><th>${__("Type")}</th><th>${__("Segment")}</th><th>${__("Follow-up")}</th><th>${__("Assigned")}</th><th>${__("Last Contact")}</th><th>${__("Docs")}</th></tr></thead>
                    <tbody>${rows.map(historyRow).join("")}</tbody>
                </table>
            </div>
        `;
    }

    function historyRow(row) {
        const docs = (row.docs || []).map((doc) => `
            <a href="#" data-route-doctype="${frappe.utils.escape_html(doc.doctype)}" data-route-name="${frappe.utils.escape_html(doc.name)}">
                ${frappe.utils.escape_html(doc.doctype)} <span>${frappe.utils.escape_html(doc.status || "-")}</span>
            </a>
        `).join("");
        return `
            <tr>
                <td><a href="#" data-route-doctype="Partner Campaign" data-route-name="${frappe.utils.escape_html(row.campaign)}"><strong>${frappe.utils.escape_html(row.campaign_name || row.campaign)}</strong><span>${frappe.utils.escape_html(row.campaign_date || "-")} · ${frappe.utils.escape_html(row.campaign_status || "-")}</span></a></td>
                <td>${frappe.utils.escape_html(row.business_type || "-")}</td>
                <td>${frappe.utils.escape_html(row.crm_segment || "-")}</td>
                <td>${frappe.utils.escape_html(row.target_status || "-")}</td>
                <td>${frappe.utils.escape_html(row.assigned_to || "-")}</td>
                <td>${frappe.utils.escape_html(row.last_contact_date || "-")}</td>
                <td><div class="ol-history-docs">${docs || `<span>${__("No outcome docs")}</span>`}</div></td>
            </tr>
        `;
    }

    function crmChip(label, value, tone) {
        const color = indicatorColor(label, value, tone);
        const displayValue = value === __("Not set") ? `${label} ${__("not set")}` : value;
        return `
            <span class="indicator-pill no-indicator-dot whitespace-nowrap ${color}" data-tone="${frappe.utils.escape_html(tone || "")}" title="${frappe.utils.escape_html(displayValue)}">
                <span>${frappe.utils.escape_html(displayValue)}</span>
            </span>
        `;
    }

    function loadOpportunityStatusColors() {
        if (OPPORTUNITY_STATUS_COLORS) return Promise.resolve(OPPORTUNITY_STATUS_COLORS);
        if (!OPPORTUNITY_STATUS_COLORS_PROMISE) {
            OPPORTUNITY_STATUS_COLORS_PROMISE = frappe.call({
                method: "orderlift.orderlift_crm.api.status_control.get_status_control_data",
                args: { document_type: "Opportunity" },
            }).then((res) => {
                OPPORTUNITY_STATUS_COLORS = {};
                ((res.message && res.message.statuses) || []).forEach((row) => {
                    if (row.name) {
                        OPPORTUNITY_STATUS_COLORS[row.name] = statusColorClass(row.color);
                    }
                });
                return OPPORTUNITY_STATUS_COLORS;
            }).catch((error) => {
                console.error("Unable to load Opportunity status colors", error);
                OPPORTUNITY_STATUS_COLORS = {};
                return OPPORTUNITY_STATUS_COLORS;
            });
        }
        return OPPORTUNITY_STATUS_COLORS_PROMISE;
    }

    function indicatorColor(label, value, tone) {
        const cleanLabel = String(label || "").toLowerCase();
        const cleanValue = String(value || "").toLowerCase();
        if (!cleanValue || cleanValue.includes("not set")) return "gray";
        if (tone === "status" && OPPORTUNITY_STATUS_COLORS && OPPORTUNITY_STATUS_COLORS[value]) {
            return OPPORTUNITY_STATUS_COLORS[value];
        }
        if (tone === "type") {
            if (cleanValue.includes("installation")) return "purple";
            if (cleanValue.includes("distribution")) return "blue";
            if (cleanValue.includes("maintenance")) return "orange";
            return "gray";
        }
        if (tone === "segment") {
            if (cleanValue.includes("grossiste")) return "green";
            if (cleanValue.includes("revendeur")) return "blue";
            if (cleanValue.includes("installateur")) return "orange";
            if (cleanValue.includes("promoteur")) return "purple";
            if (cleanValue.includes("individu")) return "gray";
            return "green";
        }
        if (cleanLabel.includes("erp")) {
            if (["won", "completed", "converted"].some((status) => cleanValue.includes(status))) return "green";
            if (["lost", "cancelled"].some((status) => cleanValue.includes(status))) return "red";
            if (["closed", "on hold"].some((status) => cleanValue.includes(status))) return "gray";
            return "blue";
        }
        if (["lost", "blocked"].some((status) => cleanValue.includes(status))) return "red";
        if (["won", "project", "done", "completed"].some((status) => cleanValue.includes(status))) return "green";
        if (["study"].some((status) => cleanValue.includes(status))) return "purple";
        if (["visit", "negotiation"].some((status) => cleanValue.includes(status))) return "orange";
        return "blue";
    }

    function statusColorClass(color) {
        const clean = String(color || "").trim().toLowerCase();
        return ["gray", "blue", "green", "orange", "red", "purple"].includes(clean) ? clean : "blue";
    }

    function unique(values) {
        return [...new Set(values)];
    }

    function injectCrmClassificationStyles() {
        if (document.getElementById("ol-crm-classification-style")) return;
        const style = document.createElement("style");
        style.id = "ol-crm-classification-style";
        style.textContent = `
            .ol-crm-classification-bar, .ol-opportunity-status-bar, .ol-transaction-classification-bar { display:flex; gap:8px; flex-wrap:wrap; margin:0 0 8px; }
            .ol-opportunity-status-bar { gap:4px; flex-wrap:nowrap; max-width:100%; overflow:hidden; align-items:center; }
            .ol-opportunity-status-bar .indicator-pill { display:inline-flex; min-width:0; max-width:128px; padding:2px 7px; font-size:10px; line-height:1.15; font-weight:800; letter-spacing:0; }
            .ol-opportunity-status-bar .indicator-pill[data-tone="status"] { max-width:150px; }
            .ol-opportunity-status-bar .indicator-pill > span { display:block; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
            @media (max-width: 767px) {
                .ol-opportunity-status-bar { gap:3px; }
                .ol-opportunity-status-bar .indicator-pill { max-width:96px; padding:2px 5px; font-size:9px; }
                .ol-opportunity-status-bar .indicator-pill[data-tone="status"] { max-width:118px; }
            }
            .ol-campaign-history-panel { margin:12px 0; border:1px solid #e2e8f0; border-radius:12px; background:#fff; overflow:hidden; }
            .ol-history-head { display:flex; justify-content:space-between; gap:10px; align-items:center; padding:10px 12px; background:#f8fafc; border-bottom:1px solid #e2e8f0; }
            .ol-history-head strong { color:#111827; font-size:13px; }
            .ol-history-head span, .ol-history-loading, .ol-history-empty { color:#64748b; font-size:11px; font-weight:800; }
            .ol-history-loading, .ol-history-empty { padding:12px; }
            .ol-history-table-wrap { overflow-x:auto; }
            .ol-history-table { width:100%; min-width:880px; border-collapse:collapse; }
            .ol-history-table th { text-align:left; font-size:10px; color:#64748b; text-transform:uppercase; letter-spacing:.06em; padding:8px 10px; border-bottom:1px solid #e2e8f0; }
            .ol-history-table td { padding:9px 10px; border-bottom:1px solid #f1f5f9; vertical-align:top; font-size:12px; }
            .ol-history-table td a { color:#1d4ed8; font-weight:900; text-decoration:none; }
            .ol-history-table td a span, .ol-history-table td strong + span { display:block; color:#64748b; font-size:10px; font-weight:800; margin-top:2px; }
            .ol-history-docs { display:flex; gap:5px; flex-wrap:wrap; }
            .ol-history-docs a, .ol-history-docs > span { border-radius:999px; background:#eef2ff; color:#3730a3; padding:4px 7px; font-size:10px; font-weight:900; }
            .ol-opportunity-quick-actions { display:flex; gap:8px; flex-wrap:wrap; margin:2px 0 8px; }
            .ol-opportunity-form .comment-content.row { display:grid; grid-template-columns:minmax(132px, 180px) minmax(0, 1fr) auto; gap:10px; align-items:start; margin-left:0; margin-right:0; width:100%; }
            .ol-opportunity-form .comment-content.row > .head,
            .ol-opportunity-form .comment-content.row > .content,
            .ol-opportunity-form .comment-content.row > .text-right { width:auto; max-width:none; float:none; padding-left:0; padding-right:0; }
            .ol-opportunity-form .comment-content .head .row { display:grid; grid-template-columns:28px minmax(0, 1fr); gap:8px; margin-left:0; margin-right:0; align-items:start; }
            .ol-opportunity-form .comment-content .head [class*="col-xs-"] { width:auto; max-width:none; float:none; padding-left:0; padding-right:0; }
            .ol-opportunity-form .comment-content .title,
            .ol-opportunity-form .comment-content .time { max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
            .ol-opportunity-form .comment-content .content { min-width:0; overflow:hidden; }
            .ol-opportunity-form .comment-content .ql-editor { max-width:100%; overflow-wrap:anywhere; word-break:break-word; white-space:normal; }
            .ol-opportunity-form .comment-content .text-right { display:flex; justify-content:flex-end; gap:2px; white-space:nowrap; }
            .ol-opportunity-form .comment-content .edit-note-btn,
            .ol-opportunity-form .comment-content .delete-note-btn { padding-left:4px !important; padding-right:4px !important; }
            @media (max-width: 767px) {
                .ol-opportunity-form .comment-content.row { grid-template-columns:minmax(0, 1fr) auto; gap:6px 8px; padding:10px !important; }
                .ol-opportunity-form .comment-content.row > .head { grid-column:1 / 2; }
                .ol-opportunity-form .comment-content.row > .content { grid-column:1 / -1; }
                .ol-opportunity-form .comment-content.row > .text-right { grid-column:2 / 3; grid-row:1 / 2; }
            }
            .ol-voice-comment-action { font-weight:700; }
            .ol-voice-note-tab-action { margin-left:6px; font-weight:700; }
            .ol-voice-comment-inline { display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin:8px 0 14px; }
            .ol-voice-comment-inline span { color:#64748b; font-size:11px; font-weight:700; }
            .ol-voice-recorder { display:grid; gap:12px; padding:2px 0 8px; }
            .ol-voice-actions { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
            .ol-voice-preview { min-height:38px; padding:10px; border:1px dashed #cbd5e1; border-radius:10px; background:#f8fafc; }
        `;
        document.head.appendChild(style);
    }
})();
