(function orderliftProcurementSourceChain() {
    if (window.__orderliftProcurementSourceChain20260726aRegistered) return;
    window.__orderliftProcurementSourceChain20260726aRegistered = true;

    var METHOD = "orderlift.orderlift_logistics.source_chain.get_upstream_source_chain";
    var FIELDNAME = "custom_upstream_source_chain_html";
    var DOCTYPES = ["Material Request", "Purchase Order", "Purchase Receipt", "Purchase Invoice"];
    var CHILD_FIELDS = {
        "Material Request Item": ["item_code", "sales_order", "sales_order_item"],
        "Purchase Order Item": ["item_code", "material_request", "material_request_item", "sales_order", "sales_order_item"],
        "Purchase Receipt Item": [
            "item_code",
            "purchase_order",
            "purchase_order_item",
            "material_request",
            "material_request_item",
            "sales_order",
            "sales_order_item",
        ],
        "Purchase Invoice Item": [
            "item_code",
            "purchase_order",
            "po_detail",
            "purchase_receipt",
            "pr_detail",
            "material_request",
            "material_request_item",
        ],
    };

    DOCTYPES.forEach(function (doctype) {
        frappe.ui.form.on(doctype, {
            refresh: function (frm) {
                scheduleRender(frm, true);
            },
            items_add: function (frm) {
                scheduleRender(frm);
            },
            items_remove: function (frm) {
                scheduleRender(frm);
            },
        });
    });

    Object.keys(CHILD_FIELDS).forEach(function (childDoctype) {
        var handlers = {};
        CHILD_FIELDS[childDoctype].forEach(function (fieldname) {
            handlers[fieldname] = function (frm) {
                scheduleRender(frm);
            };
        });
        frappe.ui.form.on(childDoctype, handlers);
    });

    function scheduleRender(frm, immediate) {
        if (!frm || !frm.fields_dict || !frm.fields_dict[FIELDNAME]) return;
        window.clearTimeout(frm.__orderliftSourceChainTimer);
        frm.__orderliftSourceChainTimer = window.setTimeout(function () {
            renderSourceChain(frm);
        }, immediate ? 0 : 250);
    }

    function renderSourceChain(frm) {
        var field = frm.fields_dict[FIELDNAME];
        if (!field) return;
        injectStyles();

        var items = (frm.doc.items || []).filter(function (row) {
            return row && (row.item_code || row.item_name || row.qty);
        });
        if (!items.length) {
            field.$wrapper.html(emptyState());
            return;
        }

        var requestId = (frm.__orderliftSourceChainRequestId || 0) + 1;
        frm.__orderliftSourceChainRequestId = requestId;
        field.$wrapper.html(loadingState());

        frappe.call({
            method: METHOD,
            args: { doc: JSON.stringify(frm.doc) },
        }).then(function (response) {
            if (frm.__orderliftSourceChainRequestId !== requestId) return;
            field.$wrapper.html(renderPayload(response.message || {}));
        }).catch(function () {
            if (frm.__orderliftSourceChainRequestId !== requestId) return;
            field.$wrapper.html(errorState());
        });
    }

    function renderPayload(payload) {
        var groups = payload.groups || [];
        var manualRows = payload.manual_rows || [];
        var warnings = payload.warnings || [];
        var parts = [];

        if (!groups.length && !manualRows.length) return emptyState();

        if (groups.length > 1) {
            parts.push('<div class="ol-source-chain-summary">' + escapeHtml(__("{0} commercial source chains", [groups.length])) + "</div>");
        }
        groups.forEach(function (group, index) {
            parts.push(renderGroup(group, groups.length > 1 ? index + 1 : null));
        });
        if (manualRows.length) parts.push(renderManualRows(manualRows));
        if (warnings.length) {
            parts.push('<div class="ol-source-chain-warnings">' + warnings.map(function (warning) {
                return '<div class="alert alert-warning">' + escapeHtml(warning) + "</div>";
            }).join("") + "</div>");
        }
        return '<div class="ol-source-chain">' + parts.join("") + "</div>";
    }

    function renderGroup(group, index) {
        var title = index ? escapeHtml(__("Chain {0}", [index])) : escapeHtml(__("Commercial source"));
        var stages = (group.stages || []).map(renderStage).join('<span class="ol-source-chain-arrow" aria-hidden="true">&rarr;</span>');
        return [
            '<section class="ol-source-chain-group">',
            '<div class="ol-source-chain-group-title">' + title + "</div>",
            '<div class="ol-source-chain-stages">' + stages + "</div>",
            "</section>",
        ].join("");
    }

    function renderStage(stage) {
        var documents = stage.documents || [];
        if (stage.restricted) {
            return documents.map(function (document) {
                return '<span class="ol-source-chain-stage ol-source-chain-stage-restricted" title="' + escapeHtml(__("You do not have access to this document")) + '">' + escapeHtml(document.name) + "</span>";
            }).join(", ");
        }
        if (!documents.length) return "";
        return documents.map(function (document) {
            var route = frappe.utils.get_form_link(stage.doctype, document.name);
            return '<a class="ol-source-chain-stage" href="' + route + '" title="' + escapeHtml(stage.doctype) + '">' + escapeHtml(document.name) + "</a>";
        }).join(", ");
    }

    function renderManualRows(rows) {
        return [
            '<section class="ol-source-chain-group ol-source-chain-manual">',
            '<div class="ol-source-chain-group-title">' + escapeHtml(__("Manual or unlinked items")) + "</div>",
            '<div class="ol-source-chain-items">' + escapeHtml(__("{0} item row(s) have no upstream commercial source.", [rows.length])) + "</div>",
            "</section>",
        ].join("");
    }

    function emptyState() {
        return '<div class="ol-source-chain ol-source-chain-empty">' + escapeHtml(__("Add an item to view its commercial source chain.")) + "</div>";
    }

    function loadingState() {
        return '<div class="ol-source-chain ol-source-chain-empty">' + escapeHtml(__("Loading commercial source chain...")) + "</div>";
    }

    function errorState() {
        return '<div class="ol-source-chain ol-source-chain-empty text-muted">' + escapeHtml(__("Commercial source chain is unavailable.")) + "</div>";
    }

    function escapeHtml(value) {
        return frappe.utils.escape_html(String(value || ""));
    }

    function injectStyles() {
        if (document.getElementById("orderlift-procurement-source-chain-style")) return;
        var style = document.createElement("style");
        style.id = "orderlift-procurement-source-chain-style";
        style.textContent = [
            ".ol-source-chain{padding:4px 0 10px}",
            ".ol-source-chain-summary{margin:0 0 8px;font-size:12px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:.04em}",
            ".ol-source-chain-group{margin:8px 0;padding:10px 12px;border:1px solid var(--border-color,#d8dfe6);border-radius:8px;background:#fff}",
            ".ol-source-chain-group-title{margin-bottom:8px;font-size:12px;font-weight:700;color:#334155}",
            ".ol-source-chain-stages{display:flex;flex-wrap:wrap;align-items:center;gap:6px;line-height:1.75}",
            ".ol-source-chain-stage{display:inline-flex;align-items:center;padding:2px 7px;border:1px solid #bfdbfe;border-radius:999px;background:#eff6ff;color:#1d4ed8;font-size:12px;font-weight:600}",
            ".ol-source-chain-stage:hover{color:#1e40af;background:#dbeafe;text-decoration:none}",
            ".ol-source-chain-stage-restricted{border-color:#fed7aa;background:#fff7ed;color:#9a3412}",
            ".ol-source-chain-arrow{color:#94a3b8;font-size:15px}",
            ".ol-source-chain-items{margin-top:8px;color:#64748b;font-size:12px;overflow-wrap:anywhere}",
            ".ol-source-chain-manual{border-style:dashed;background:#fffbeb}",
            ".ol-source-chain-warnings{margin-top:8px}.ol-source-chain-warnings .alert{margin:4px 0;padding:7px 10px;font-size:12px}",
            ".ol-source-chain-empty{color:#64748b;font-size:12px}",
        ].join("\n");
        document.head.appendChild(style);
    }
})();
