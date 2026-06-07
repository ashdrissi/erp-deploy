/**
 * Orderlift - rename native Session Defaults to Change Company.
 * The native page is still used because it writes Frappe's session default
 * keys, but the label is clearer for business users.
 */

(function orderliftChangeCompanyLabel() {
    if (window.__orderlift_change_company_label_20260519a_installed) return;
    window.__orderlift_change_company_label_20260519a_installed = true;

    var SOURCE_LABELS = { "Session Defaults": true, "Session Default": true };
    var TARGET_LABEL = "Change Company";

    function normalize(value) {
        return String(value || "").replace(/\s+/g, " ").trim();
    }

    function translate(value) {
        return window.__ ? __(value) : value;
    }

    function setVisible(node) {
        var item = node.closest("li, a, button, .dropdown-item, .menu-item") || node;
        item.style.display = "";
        item.classList.remove("orderlift-hidden-sidebar-node", "orderlift-hidden-standard-item");
    }

    function replaceLabel(node) {
        var label = normalize(node.textContent || node.innerText);
        if (!SOURCE_LABELS[label]) return;

        var target = translate(TARGET_LABEL);
        var labelNode = node.querySelector(".menu-item-label, .dropdown-item-label, .sidebar-item-label, span");
        if (labelNode && normalize(labelNode.textContent || labelNode.innerText) === label) {
            labelNode.textContent = target;
        } else {
            node.textContent = target;
        }
        setVisible(node);
    }

    function apply() {
        var selectors = [".dropdown-item", ".menu-item", ".menu-item-label", "a", "button"];
        for (var s = 0; s < selectors.length; s++) {
            var nodes = document.querySelectorAll(selectors[s]);
            for (var i = 0; i < nodes.length; i++) {
                replaceLabel(nodes[i]);
            }
        }
    }

    var queued = false;
    function queueApply() {
        if (queued) return;
        queued = true;
        requestAnimationFrame(function () {
            queued = false;
            apply();
        });
    }

    var attempts = 160;
    (function keepApplying() {
        queueApply();
        if (attempts <= 0) return;
        attempts -= 1;
        setTimeout(keepApplying, 250);
    })();

    if (document.body) {
        new MutationObserver(queueApply).observe(document.body, { childList: true, subtree: true });
    } else {
        document.addEventListener("DOMContentLoaded", queueApply);
    }

    if (window.frappe && frappe.router && frappe.router.on) {
        frappe.router.on("change", function () { setTimeout(queueApply, 0); });
    }
})();
