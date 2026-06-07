/**
 * Orderlift - global Desk company switcher.
 * Shows the current/default company in the Desk sidebar and lets users switch
 * without opening Session Defaults.
 */

(function orderliftCompanySwitcher() {
    if (window.__orderlift_company_switcher_20260519a_installed) return;
    window.__orderlift_company_switcher_20260519a_installed = true;

    var STYLE_ID = "orderlift-company-switcher-20260519a-style";
    var HOST_ID = "orderlift-company-switcher";

    function context() {
        return (window.frappe && frappe.boot && frappe.boot.orderlift_company_access) || {};
    }

    function companies() {
        return Array.isArray(context().companies) ? context().companies : [];
    }

    function currentCompany() {
        return context().current_company || context().user_default_company || companies()[0] || "Orderlift";
    }

    function escapeHtml(value) {
        return String(value || "").replace(/[&<>'"]/g, function (char) {
            return { "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char];
        });
    }

    function translate(value) {
        return window.__ ? __(value) : value;
    }

    function ensureStyle() {
        if (document.getElementById(STYLE_ID)) return;
        var style = document.createElement("style");
        style.id = STYLE_ID;
        style.textContent = [
            ".orderlift-company-switcher { position: relative; margin: 8px 10px 10px; z-index: 5; }",
            ".orderlift-company-switcher-button { width: 100%; min-height: 38px; display: flex; align-items: center; gap: 8px; border: 1px solid var(--border-color, #d8dce5); border-radius: 12px; background: var(--card-bg, #fff); color: var(--text-color, #1f2937); padding: 7px 10px; text-align: left; cursor: pointer; box-shadow: 0 1px 2px rgba(15, 23, 42, .04); }",
            ".orderlift-company-switcher-button:hover, .orderlift-company-switcher-button:focus { border-color: #c7d2fe; background: #f8fafc; outline: none; }",
            ".orderlift-company-switcher-icon { width: 22px; height: 22px; border-radius: 999px; display: inline-flex; align-items: center; justify-content: center; background: #eef2ff; color: #3730a3; font-size: 12px; flex: 0 0 auto; }",
            ".orderlift-company-switcher-copy { min-width: 0; display: grid; gap: 1px; flex: 1 1 auto; }",
            ".orderlift-company-switcher-copy small { color: var(--text-muted, #64748b); font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; line-height: 1; }",
            ".orderlift-company-switcher-copy strong { min-width: 0; color: var(--text-color, #111827); font-size: 12px; font-weight: 750; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; line-height: 1.2; }",
            ".orderlift-company-switcher-caret { color: #64748b; font-size: 11px; flex: 0 0 auto; }",
            ".orderlift-company-switcher-menu { position: absolute; top: calc(100% + 6px); left: 0; right: 0; display: none; padding: 6px; border: 1px solid var(--border-color, #d8dce5); border-radius: 12px; background: var(--card-bg, #fff); box-shadow: 0 16px 38px rgba(15, 23, 42, .16); max-height: 280px; overflow-y: auto; }",
            ".orderlift-company-switcher.open .orderlift-company-switcher-menu { display: grid; gap: 4px; }",
            ".orderlift-company-option { width: 100%; min-height: 32px; border: 0; border-radius: 8px; background: transparent; color: var(--text-color, #1f2937); padding: 0 9px; text-align: left; cursor: pointer; font-size: 12px; font-weight: 650; }",
            ".orderlift-company-option:hover { background: #f1f5f9; }",
            ".orderlift-company-option.active { background: #eef2ff; color: #3730a3; }",
            ".orderlift-company-option[disabled] { cursor: default; opacity: .65; }",
        ].join("\n");
        document.head.appendChild(style);
    }

    function findSidebarHost() {
        return document.querySelector(".body-sidebar") || document.querySelector(".desk-sidebar");
    }

    function render() {
        ensureStyle();
        var sidebar = findSidebarHost();
        if (!sidebar || !window.frappe || !frappe.boot) return;

        var list = companies();
        if (!list.length) return;

        var selected = currentCompany();
        var host = document.getElementById(HOST_ID);
        if (!host) {
            host = document.createElement("div");
            host.id = HOST_ID;
            host.className = "orderlift-company-switcher";
            sidebar.insertBefore(host, sidebar.firstChild);
        }

        host.innerHTML = [
            '<button type="button" class="orderlift-company-switcher-button" aria-haspopup="menu" aria-expanded="false">',
                '<span class="orderlift-company-switcher-icon">⌂</span>',
                '<span class="orderlift-company-switcher-copy"><small>', escapeHtml(translate("Current Company")), '</small><strong>', escapeHtml(selected), '</strong></span>',
                list.length > 1 ? '<span class="orderlift-company-switcher-caret">▾</span>' : '',
            '</button>',
            '<div class="orderlift-company-switcher-menu" role="menu">',
                list.map(function (company) {
                    var active = company === selected;
                    return '<button type="button" role="menuitem" class="orderlift-company-option ' + (active ? 'active' : '') + '" data-orderlift-company="' + escapeHtml(company) + '" ' + (active ? 'disabled' : '') + '>' + escapeHtml(company) + '</button>';
                }).join(""),
            '</div>',
        ].join("");

        bind(host);
    }

    function bind(host) {
        var button = host.querySelector(".orderlift-company-switcher-button");
        if (button) {
            button.addEventListener("click", function (event) {
                event.stopPropagation();
                if (companies().length <= 1) return;
                var open = !host.classList.contains("open");
                host.classList.toggle("open", open);
                button.setAttribute("aria-expanded", open ? "true" : "false");
            });
        }

        var options = host.querySelectorAll("[data-orderlift-company]");
        for (var i = 0; i < options.length; i++) {
            options[i].addEventListener("click", function (event) {
                event.stopPropagation();
                var company = this.getAttribute("data-orderlift-company");
                if (company) switchCompany(company);
            });
        }
    }

    function switchCompany(company) {
        if (!company || company === currentCompany()) return;
        frappe.call({
            method: "orderlift.menu_access.set_current_company",
            args: { company: company },
            freeze: true,
            callback: function (response) {
                frappe.boot.orderlift_company_access = response.message || frappe.boot.orderlift_company_access || {};
                if (frappe.show_alert) {
                    frappe.show_alert({ message: translate("Company changed to {0}").replace("{0}", company), indicator: "green" });
                }
                window.dispatchEvent(new CustomEvent("orderlift-company-changed", { detail: { company: company } }));
                window.location.reload();
            },
        });
    }

    document.addEventListener("click", function () {
        var host = document.getElementById(HOST_ID);
        if (host) host.classList.remove("open");
    });

    var queued = false;
    function queueRender() {
        if (queued) return;
        queued = true;
        requestAnimationFrame(function () {
            queued = false;
            render();
        });
    }

    var attempts = 160;
    (function keepRendering() {
        queueRender();
        if (attempts <= 0) return;
        attempts -= 1;
        setTimeout(keepRendering, 250);
    })();

    if (document.body) {
        new MutationObserver(queueRender).observe(document.body, { childList: true, subtree: true });
    } else {
        document.addEventListener("DOMContentLoaded", queueRender);
    }

    if (frappe.router && frappe.router.on) {
        frappe.router.on("change", function () { setTimeout(queueRender, 0); });
    }
})();
