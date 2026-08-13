(function orderliftDeleteBlockerHelper() {
    if (window.__orderliftDeleteBlockerHelper20260804bRegistered) return;
    window.__orderliftDeleteBlockerHelper20260804bRegistered = true;

    var PREVIEW_METHOD = "orderlift.delete_blocker_helper.get_delete_blockers";
    var DELETE_METHOD = "orderlift.delete_blocker_helper.delete_blockers_and_parent";
    var PATCH_FLAG = "__orderliftDeleteBlockerHelper20260804bPatched";
    var BULK_PATCH_FLAG = "__orderliftDeleteBlockerBulk20260804bPatched";

    function escapeHtml(value) {
        if (frappe.utils && frappe.utils.escape_html) {
            return frappe.utils.escape_html(String(value || ""));
        }
        return $("<div>").text(String(value || "")).html();
    }

    function documentTitle(doctype, name) {
        var title = String(name || "");
        var meta = frappe.get_meta(doctype);
        var titleField = meta && meta.title_field;
        var value = titleField && frappe.model.get_value(doctype, name, titleField);
        return value ? String(value) + " (" + title + ")" : title;
    }

    function formLink(doctype, name) {
        var route = frappe.utils.get_form_link(doctype, name);
        return '<a href="' + route + '" target="_blank" rel="noopener noreferrer">' + escapeHtml(name) + "</a>";
    }

    function reasonText(reason) {
        var text = reason.field_label || reason.fieldname || reason.link_doctype || "";
        if (reason.row) text += " - " + __("Row {0}", [reason.row]);
        return escapeHtml(text);
    }

    function lockReasonText(reason) {
        var labels = {
            delete_permission: __("No delete permission"),
            submitted: __("Submitted"),
            standard_doctype: __("Protected system document"),
            reference_doctype: __("Reference/master record"),
            ledger_doctype: __("Ledger record"),
        };
        return labels[reason] || __("Locked");
    }

    function overrideText(reasons) {
        var labels = {
            delete_permission: __("permission override"),
            submitted: __("submitted override"),
        };
        return (reasons || []).map(function (reason) { return labels[reason] || reason; }).join(", ");
    }

    function blockerRows(blockers) {
        var groups = {};
        blockers.forEach(function (blocker, index) {
            if (!groups[blocker.doctype]) groups[blocker.doctype] = [];
            groups[blocker.doctype].push({ blocker: blocker, index: index });
        });

        return Object.keys(groups).sort().map(function (doctype) {
            var rows = groups[doctype].map(function (entry) {
                var blocker = entry.blocker;
                var reasons = (blocker.reasons || []).map(reasonText).join(", ");
                var overrides = blocker.override_reasons || [];
                var depth = Number(blocker.depth || 1);
                var blockingDocuments = (blocker.blocking_documents || []).map(function (row) {
                    return row.doctype + " " + row.name;
                }).join(", ");
                var control = blocker.can_delete
                    ? '<input class="ol-delete-blocker-check" type="checkbox" data-index="' + entry.index + '" aria-label="' + escapeHtml(__("Select {0}", [blocker.name])) + '">'
                    : '<span class="ol-delete-blocker-lock" title="' + escapeHtml(__("You cannot delete this document")) + '">' + escapeHtml(lockReasonText(blocker.lock_reason)) + "</span>";
                var state = blocker.can_delete ? "" : " ol-delete-blocker-row-locked";
                var override = overrides.length
                    ? '<span class="ol-delete-blocker-override">' + escapeHtml(overrideText(overrides)) + "</span>"
                    : "";
                var hierarchy = '<span class="ol-delete-blocker-depth">' + escapeHtml(
                    __("Dependency level {0}", [depth])
                ) + (blockingDocuments ? " · " + escapeHtml(__("Blocks {0}", [blockingDocuments])) : "") + "</span>";
                return [
                    '<div class="ol-delete-blocker-row' + state + '">',
                    '<span class="ol-delete-blocker-control">' + control + "</span>",
                    '<span class="ol-delete-blocker-document">' + formLink(blocker.doctype, blocker.name) + override + hierarchy + "</span>",
                    '<span class="ol-delete-blocker-reason">' + escapeHtml(__("Linked through")) + ": " + reasons + "</span>",
                    "</div>",
                ].join("");
            }).join("");

            return [
                '<section class="ol-delete-blocker-group">',
                '<h5>' + escapeHtml(__(doctype)) + ' <span class="badge">' + groups[doctype].length + "</span></h5>",
                rows,
                "</section>",
            ].join("");
        }).join("");
    }

    function dialogHtml(data) {
        var blockers = data.blockers || [];
        var restricted = Number(data.restricted_blocker_count || 0);
        var nonDeletable = Number(data.non_deletable_blocker_count || 0);
        var sourceLedgerCount = Number(data.source_ledger_blocker_count || 0);
        var overrideCount = blockers.filter(function (row) { return (row.override_reasons || []).length; }).length;
        var selectableCount = blockers.filter(function (row) { return row.can_delete; }).length;
        var referenceUnlinkCount = blockers.filter(function (row) {
            return !row.can_delete && row.lock_reason === "reference_doctype";
        }).length;
        var hardLockedCount = Math.max(nonDeletable - referenceUnlinkCount, 0);
        var warning = "";

        if (restricted) {
            warning += '<div class="alert alert-danger">' + escapeHtml(
                __("{0} restricted document(s) also block deletion. Their details are hidden.", [restricted])
            ) + "</div>";
        }
        if (referenceUnlinkCount) {
            warning += '<div class="alert alert-info">' + escapeHtml(
                __("{0} master/reference record(s) will be kept. Only their link rows to this document will be removed.", [referenceUnlinkCount])
            ) + "</div>";
        }
        if (hardLockedCount) {
            warning += '<div class="alert alert-warning">' + escapeHtml(
                __("{0} visible blocker(s) cannot be cascade-deleted. Permission-locked records and submitted records may require manual unlink/cancel review.", [hardLockedCount])
            ) + "</div>";
        }
        if (overrideCount || (data.parent || {}).submitted) {
            warning += '<div class="alert alert-danger">' + escapeHtml(
                __("Privileged deletion is enabled. Submitted records will be cancelled through native hooks before deletion.")
            ) + "</div>";
        }
        if (sourceLedgerCount) {
            warning += '<div class="alert alert-warning">' + escapeHtml(
                __("{0} generated ledger row(s) linked to this source voucher will be removed automatically during privileged deletion.", [sourceLedgerCount])
            ) + "</div>";
        }

        var controls = selectableCount
            ? '<div class="ol-delete-blocker-actions"><button type="button" class="btn btn-default btn-xs ol-delete-blocker-select-all">' + escapeHtml(__("Select all deletable")) + "</button></div>"
            : "";

        return [
            '<div class="ol-delete-blocker-dialog">',
            '<p class="text-muted">' + escapeHtml(
                __("Select every deletable business-document blocker below. Dependencies are deleted deepest-first, then the requested document. Master records are shown for review but are not cascade-deleted. Generated GL, stock, and payment ledger rows are removed automatically with their exact source voucher during privileged deletion.")
            ) + "</p>",
            warning,
            controls,
            blockerRows(blockers),
            '<div class="ol-delete-blocker-summary"></div>',
            "</div>",
        ].join("");
    }

    function injectStyle() {
        if (document.getElementById("orderlift-delete-blocker-helper-style")) return;
        var style = document.createElement("style");
        style.id = "orderlift-delete-blocker-helper-style";
        style.textContent = [
            ".ol-delete-blocker-dialog{max-height:62vh;overflow:auto;padding-right:4px}",
            ".ol-delete-blocker-group{border:1px solid var(--border-color,#d8dfe6);border-radius:8px;margin:12px 0;overflow:hidden}",
            ".ol-delete-blocker-group h5{background:var(--subtle-fg,#f7f8fa);margin:0;padding:10px 12px}",
            ".ol-delete-blocker-actions{display:flex;justify-content:flex-end;margin:8px 0}",
            ".ol-delete-blocker-row{display:grid;grid-template-columns:minmax(96px,auto) minmax(140px,1fr) minmax(180px,1.4fr);align-items:center;gap:12px;padding:10px 12px;border-top:1px solid var(--border-color,#e8ebef)}",
            ".ol-delete-blocker-row-locked{background:var(--subtle-fg,#f7f8fa);opacity:.78}",
            ".ol-delete-blocker-control{display:flex;align-items:center;justify-content:center;min-width:96px}",
            ".ol-delete-blocker-check{width:16px;height:16px}",
            ".ol-delete-blocker-lock{display:inline-block;font-size:10px;font-weight:600;line-height:1.2;text-align:center;text-transform:uppercase;white-space:normal}",
            ".ol-delete-blocker-document{font-weight:600;overflow-wrap:anywhere}",
            ".ol-delete-blocker-override{display:block;color:var(--orange-600,#c05621);font-size:10px;font-weight:600;margin-top:3px;text-transform:uppercase}",
            ".ol-delete-blocker-depth{display:block;color:var(--text-muted,#6b7280);font-size:10px;font-weight:500;margin-top:3px}",
            ".ol-delete-blocker-reason{color:var(--text-muted,#6b7280);font-size:12px;overflow-wrap:anywhere}",
            ".ol-delete-blocker-summary{font-weight:600;margin-top:12px}",
            "@media(max-width:767px){.ol-delete-blocker-row{grid-template-columns:96px 1fr}.ol-delete-blocker-reason{grid-column:2}}",
        ].join("\n");
        document.head.appendChild(style);
    }

    function showBlockerDialog(data, callback, cancelCallback) {
        injectStyle();
        var parent = data.parent || {};
        var blockers = data.blockers || [];
        var selectable = blockers.filter(function (row) { return row.can_delete; });
        var sourceLedgerCount = Number(data.source_ledger_blocker_count || 0);
        var referenceUnlinkCount = blockers.filter(function (row) {
            return !row.can_delete && row.lock_reason === "reference_doctype";
        }).length;
        var unavailable = Number(data.restricted_blocker_count || 0)
            + Math.max(Number(data.non_deletable_blocker_count || 0) - referenceUnlinkCount, 0);
        var title = documentTitle(parent.doctype, parent.name);
        var actionStarted = false;
        var dialog = new frappe.ui.Dialog({
            title: __("Delete blockers and {0}", [title]),
            size: "large",
            fields: [{ fieldname: "body", fieldtype: "HTML" }],
            onhide: function () {
                if (!actionStarted && cancelCallback) cancelCallback();
            },
            primary_action_label: __("Delete blockers and document"),
            primary_action: function () {
                var selected = [];
                dialog.fields_dict.body.$wrapper.find(".ol-delete-blocker-check:checked").each(function () {
                    var blocker = blockers[Number(this.getAttribute("data-index"))];
                    if (blocker) selected.push({ doctype: blocker.doctype, name: blocker.name });
                });

                var executeDelete = function () {
                    actionStarted = true;
                    frappe.call({
                        method: DELETE_METHOD,
                        args: {
                            doctype: parent.doctype,
                            name: parent.name,
                            selected_blockers: selected,
                        },
                        freeze: true,
                        freeze_message: __("Deleting blockers and {0}...", [title]),
                    }).then(function (response) {
                        dialog.hide();
                        frappe.utils.play_sound("delete");
                        frappe.model.clear_doc(parent.doctype, parent.name);
                        if (callback) callback(response, null);
                    }).catch(function () {
                        actionStarted = false;
                    });
                };

                var selectedUsesOverride = selected.some(function (selectedRow) {
                    return blockers.some(function (blocker) {
                        return blocker.doctype === selectedRow.doctype
                            && blocker.name === selectedRow.name
                            && (blocker.override_reasons || []).length;
                    });
                });
                if (parent.submitted || selectedUsesOverride || sourceLedgerCount) {
                    frappe.confirm(
                        __("This will cancel submitted records through native hooks, then delete them. Accounting or stock effects may be reversed. Continue?"),
                        executeDelete
                    );
                    return;
                }

                executeDelete();
            },
        });

        dialog.fields_dict.body.$wrapper.html(dialogHtml(data));
        dialog.show();
        var $primary = dialog.get_primary_btn();
        if (!selectable.length && !referenceUnlinkCount && !sourceLedgerCount) $primary.hide();

        function updateAction() {
            var selectedCount = dialog.fields_dict.body.$wrapper.find(".ol-delete-blocker-check:checked").length;
            var ready = !unavailable && (selectable.length > 0 || referenceUnlinkCount > 0 || sourceLedgerCount > 0) && selectedCount === selectable.length;
            $primary.prop("disabled", !ready);
            $primary.text(
                selectable.length
                    ? __("Delete {0} blocker(s) and {1}", [selectable.length, parent.name])
                    : sourceLedgerCount
                        ? __("Delete {0} and generated ledger rows", [parent.name])
                        : __("Unlink {0} reference(s) and delete {1}", [referenceUnlinkCount, parent.name])
            );
            dialog.fields_dict.body.$wrapper.find(".ol-delete-blocker-summary").text(
                sourceLedgerCount && !selectable.length && !referenceUnlinkCount
                    ? __("No business blockers selected; {0} and {1} generated ledger row(s) will be removed", [parent.name, sourceLedgerCount])
                    : referenceUnlinkCount
                    ? __("{0} of {1} deletable blockers selected; {2} master reference(s) will be unlinked", [selectedCount, selectable.length, referenceUnlinkCount])
                    : __("{0} of {1} deletable blockers selected", [selectedCount, selectable.length])
            );
        }

        dialog.fields_dict.body.$wrapper.on("change", ".ol-delete-blocker-check", updateAction);
        dialog.fields_dict.body.$wrapper.on("click", ".ol-delete-blocker-select-all", function () {
            dialog.fields_dict.body.$wrapper.find(".ol-delete-blocker-check").prop("checked", true);
            updateAction();
        });
        updateAction();
        return dialog;
    }

    function patchDeleteDoc() {
        if (!window.frappe || !frappe.model || typeof frappe.model.delete_doc !== "function") return false;
        if (frappe.model.delete_doc[PATCH_FLAG]) return true;

        var originalDeleteDoc = frappe.model.delete_doc;
        var wrappedDeleteDoc = function (doctype, docname, callback) {
            var context = this;
            var args = arguments;
            if (!doctype || !docname || String(docname).startsWith("new-")) {
                return originalDeleteDoc.apply(context, args);
            }

            return frappe.call({
                method: PREVIEW_METHOD,
                args: { doctype: doctype, name: docname },
                freeze: true,
                freeze_message: __("Checking documents that block deletion..."),
            }).then(function (response) {
                var data = response.message || {};
                var count = (data.blockers || []).length + Number(data.restricted_blocker_count || 0) + Number(data.source_ledger_blocker_count || 0);
                if (!count) return originalDeleteDoc.apply(context, args);
                showBlockerDialog(data, callback);
                return response;
            }).catch(function () {
                // Native deletion remains the safe fallback because it performs all permission and link checks.
                return originalDeleteDoc.apply(context, args);
            });
        };

        wrappedDeleteDoc[PATCH_FLAG] = true;
        frappe.model.delete_doc = wrappedDeleteDoc;
        return true;
    }

    function patchBulkDelete() {
        if (!window.frappe || !frappe.ui || !frappe.ui.BulkOperations) return false;
        if (typeof frappe.ui.BulkOperations.prototype.delete !== "function") return false;
        if (frappe.ui.BulkOperations.prototype.delete[BULK_PATCH_FLAG]) return true;

        var originalBulkDelete = frappe.ui.BulkOperations.prototype.delete;
        var wrappedBulkDelete = function (docnames, done) {
            var context = this;
            var args = arguments;
            if (!Array.isArray(docnames) || docnames.length !== 1 || !context.doctype) {
                return originalBulkDelete.apply(context, args);
            }

            var name = String(docnames[0] || "");
            if (!name || name.startsWith("new-")) {
                return originalBulkDelete.apply(context, args);
            }

            return frappe.call({
                method: PREVIEW_METHOD,
                args: { doctype: context.doctype, name: name },
                freeze: true,
                freeze_message: __("Checking documents that block deletion..."),
            }).then(function (response) {
                var data = response.message || {};
                var count = (data.blockers || []).length + Number(data.restricted_blocker_count || 0) + Number(data.source_ledger_blocker_count || 0);
                if (!count) return originalBulkDelete.apply(context, args);

                var finish = function () {
                    if (done) done();
                };
                showBlockerDialog(data, finish, finish);
                return response;
            }).catch(function () {
                return originalBulkDelete.apply(context, args);
            });
        };

        wrappedBulkDelete[BULK_PATCH_FLAG] = true;
        frappe.ui.BulkOperations.prototype.delete = wrappedBulkDelete;
        return true;
    }

    function bootstrap(attempts) {
        var formReady = patchDeleteDoc();
        var bulkReady = patchBulkDelete();
        if ((!formReady || !bulkReady) && attempts > 0) {
            window.setTimeout(function () { bootstrap(attempts - 1); }, 250);
        }
    }

    bootstrap(40);
})();
