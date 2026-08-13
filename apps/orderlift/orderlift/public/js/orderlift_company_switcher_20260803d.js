(function orderliftCompanySwitcher() {
    if (window.__orderliftCompanySwitcher20260803dInstalled) return;
    window.__orderliftCompanySwitcher20260803dInstalled = true;

    const HOST_ID = "orderlift-company-switcher";
    const STYLE_ID = "orderlift-company-switcher-20260803d-style";
    const STORAGE_KEY = "orderlift.company-context.changed";
    const sourceId = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    let switching = false;
    let requiredDialogShown = false;

    frappe.boot.desk_settings = frappe.boot.desk_settings || {};
    frappe.boot.desk_settings.view_switcher = 1;

    function context() {
        return frappe.boot?.orderlift_company_access || {};
    }

    function companies() {
        return Array.isArray(context().companies) ? context().companies : [];
    }

    function currentCompany() {
        return context().current_company || "";
    }

    function escapeHtml(value) {
        return frappe.utils?.escape_html ? frappe.utils.escape_html(String(value || "")) : String(value || "");
    }

    function applyPayload(payload) {
        if (!payload || !payload.current_company) return;
        frappe.boot.orderlift_company_access = payload;
        if (frappe.boot.user?.defaults) {
            frappe.boot.user.defaults.company = payload.current_company;
            frappe.boot.user.defaults.Company = payload.current_company;
        }
        if (frappe.user_defaults) {
            frappe.user_defaults.company = payload.current_company;
            frappe.user_defaults.Company = payload.current_company;
        }
        if (frappe.boot.sysdefaults) {
            frappe.boot.sysdefaults.company = payload.current_company;
            frappe.boot.sysdefaults.Company = payload.current_company;
        }
        if (frappe.sys_defaults) {
            frappe.sys_defaults.company = payload.current_company;
            frappe.sys_defaults.Company = payload.current_company;
        }
    }

    async function switchCompany(company) {
        company = String(company || "").trim();
        if (!company || switching) return false;
        if (!companies().includes(company)) {
            frappe.msgprint({
                title: __("Company Access"),
                message: __("You do not have access to company {0}.", [company]),
                indicator: "red",
            });
            return false;
        }
        if (company === currentCompany() && !context().requires_company_selection) return true;

        switching = true;
        try {
            const response = await frappe.call({
                method: "orderlift.menu_access.set_current_company",
                args: { company },
                freeze: true,
                freeze_message: __("Switching company..."),
            });
            const payload = response.message || {};
            applyPayload(payload);
            notifyOtherTabs(payload);
            window.location.reload();
            return true;
        } catch (error) {
            console.error("Orderlift company switch failed", error);
            return false;
        } finally {
            switching = false;
        }
    }

    function showCompanyDialog(required) {
        const options = companies();
        if (!options.length) {
            frappe.msgprint({
                title: __("Company Access Required"),
                message: __("No company is assigned to this user. Contact an administrator."),
                indicator: "red",
            });
            return;
        }

        const dialog = new frappe.ui.Dialog({
            title: required ? __("Select Your Company") : __("Change Company"),
            fields: [{
                fieldname: "company",
                fieldtype: "Select",
                label: __("Company"),
                options: options.join("\n"),
                default: currentCompany() || options[0],
                reqd: 1,
            }],
            primary_action_label: __("Use Company"),
            primary_action(values) {
                void switchCompany(values.company);
            },
        });
        if (required) {
            dialog.$wrapper?.find(".modal-header .btn-modal-close").hide();
            dialog.$wrapper?.on("hide.bs.modal", () => {
                if (!currentCompany()) window.setTimeout(() => dialog.show(), 0);
            });
        }
        dialog.show();
    }

    function ensureStyle() {
        if (document.getElementById(STYLE_ID)) return;
        const style = document.createElement("style");
        style.id = STYLE_ID;
        style.textContent = [
            ".orderlift-company-switcher{box-sizing:border-box;flex:0 0 auto;width:auto;max-width:calc(100% - 20px);min-width:0;margin:8px 10px 10px;overflow:hidden}",
            ".orderlift-company-switcher button{box-sizing:border-box;width:100%;max-width:100%;min-width:0;display:flex;align-items:center;gap:8px;overflow:hidden;border:1px solid var(--border-color);border-radius:10px;background:var(--card-bg);padding:8px 10px;text-align:left}",
            ".orderlift-company-switcher .orderlift-company-icon{display:inline-flex;flex:0 0 auto}",
            ".orderlift-company-switcher .orderlift-company-copy{display:block;flex:1 1 auto;min-width:0;overflow:hidden}",
            ".orderlift-company-switcher small{display:block;color:var(--text-muted);font-size:10px;text-transform:uppercase}",
            ".orderlift-company-switcher strong{display:block;width:100%;max-width:100%;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}",
            ".body-sidebar>.sidebar-header .header-subtitle{display:none!important}",
            ".orderlift-company-stale-banner{position:fixed;left:50%;top:12px;z-index:1100;transform:translateX(-50%);max-width:720px;padding:10px 14px;border-radius:9px;background:#fff3cd;color:#664d03;box-shadow:0 8px 30px rgba(0,0,0,.18)}",
        ].join("");
        document.head.appendChild(style);
    }

    function renderSidebarSwitcher() {
        ensureStyle();
        const sidebar = document.querySelector(".body-sidebar") || document.querySelector(".desk-sidebar");
        if (!sidebar || !companies().length) return;
        let host = document.getElementById(HOST_ID);
        if (!host) {
            host = document.createElement("div");
            host.id = HOST_ID;
            host.className = "orderlift-company-switcher";
        }
        const header = sidebar.querySelector(":scope > .sidebar-header");
        const logo = sidebar.querySelector(":scope > #orderlift-sidebar-brand-logo");
        const anchor = header || logo?.nextSibling || sidebar.firstChild;
        if (host.parentElement !== sidebar || host.nextSibling !== header) {
            sidebar.insertBefore(host, anchor || null);
        }
        const companyLabel = currentCompany() || __("Select company");
        if (host.dataset.companyLabel !== companyLabel) {
            host.dataset.companyLabel = companyLabel;
            host.innerHTML = `<button type="button"><span class="orderlift-company-icon">${frappe.utils?.icon ? frappe.utils.icon("organization", "sm") : ""}</span><span class="orderlift-company-copy"><small>${__("Current Company")}</small><strong title="${escapeHtml(companyLabel)}">${escapeHtml(companyLabel)}</strong></span></button>`;
            host.querySelector("button")?.addEventListener("click", () => showCompanyDialog(false));
        }
    }

    function notifyOtherTabs(payload) {
        const message = { sourceId, company: payload.current_company, revision: payload.context_revision || 0 };
        if (window.BroadcastChannel) {
            const channel = new BroadcastChannel("orderlift-company-context");
            channel.postMessage(message);
            channel.close();
        }
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...message, timestamp: Date.now() }));
        } catch (error) {
            console.warn("Unable to notify other company tabs", error);
        }
    }

    function handleRemoteSwitch(message) {
        if (!message || message.sourceId === sourceId || !message.company) return;
        const route = frappe.get_route?.() || [];
        const customPageMayHaveDraft = !window.cur_frm && !["List", "Form", "Workspaces"].includes(route[0]);
        if (window.cur_frm?.is_dirty?.() || customPageMayHaveDraft) {
            window.__orderliftCompanyContextStale = true;
            if (!document.querySelector(".orderlift-company-stale-banner")) {
                const banner = document.createElement("div");
                banner.className = "orderlift-company-stale-banner";
                banner.innerHTML = `<span>${__("Company changed to {0} in another tab. Save or discard your work, then reload this tab.", [escapeHtml(message.company)])}</span> <button type="button" class="btn btn-xs btn-warning">${__("Reload")}</button>`;
                banner.querySelector("button")?.addEventListener("click", () => window.location.reload());
                document.body.appendChild(banner);
            }
            return;
        }
        window.location.reload();
    }

    function installTabSync() {
        if (window.BroadcastChannel) {
            const channel = new BroadcastChannel("orderlift-company-context");
            channel.addEventListener("message", (event) => handleRemoteSwitch(event.data));
        }
        window.addEventListener("storage", (event) => {
            if (event.key !== STORAGE_KEY || !event.newValue) return;
            try {
                handleRemoteSwitch(JSON.parse(event.newValue));
            } catch (error) {
                console.warn("Unable to read company tab notification", error);
            }
        });
    }

    function bootstrap(attempts) {
        renderSidebarSwitcher();
        if (!requiredDialogShown && context().requires_company_selection) {
            requiredDialogShown = true;
            showCompanyDialog(true);
        }
        if (!document.body && attempts > 0) {
            window.setTimeout(() => bootstrap(attempts - 1), 250);
        }
    }

    window.orderlift = window.orderlift || {};
    window.orderlift.setActiveCompany = switchCompany;
    window.orderlift.getActiveCompany = currentCompany;
    installTabSync();
    bootstrap(80);
    let renderQueued = false;
    const queueRender = () => {
        if (renderQueued) return;
        renderQueued = true;
        window.requestAnimationFrame(() => {
            renderQueued = false;
            renderSidebarSwitcher();
        });
    };
    if (document.body) {
        new MutationObserver(queueRender).observe(document.body, { childList: true, subtree: true });
    }
    frappe.router?.on?.("change", () => {
        [0, 150, 500].forEach((delay) => window.setTimeout(queueRender, delay));
    });
})();
