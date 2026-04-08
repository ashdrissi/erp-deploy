frappe.pages["sig-dashboard"].on_page_load = function (wrapper) {
    wrapper.sig_page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("SIG Dashboard"),
        single_column: true,
    });
    _setSigBreadcrumbs(wrapper.sig_page, __("SIG Dashboard"));
};

frappe.pages["sig-dashboard"].on_page_show = function (wrapper) {
    _setSigBreadcrumbs(wrapper.sig_page, __("SIG Dashboard"));
    renderSigPage(wrapper, {
        rootId: "sig-dashboard-page-root",
        scriptId: "orderlift-sig-dashboard-script",
        scriptSrc: "/assets/orderlift/js/sig_dashboard.js?v=20260408d",
        mountKey: "orderliftSigDashboard",
    });
};

function renderSigPage(wrapper, config) {
    const page = wrapper.sig_page;
    page.main.html(`<div id="${config.rootId}"></div>`);
    loadSigScript(config.scriptId, config.scriptSrc)
        .then(() => window[config.mountKey].mount(page.main[0].querySelector(`#${config.rootId}`), config.mountOptions || {}))
        .catch((error) => {
            page.main.html(`<div class="text-muted" style="padding:24px">${frappe.utils.escape_html(error.message || __("Failed to load page."))}</div>`);
        });
}

function loadSigScript(id, src) {
    if (document.getElementById(id)) return Promise.resolve();
    return new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.id = id;
        script.src = src;
        script.async = true;
        script.onload = resolve;
        script.onerror = () => reject(new Error(`Failed to load ${src}`));
        document.head.appendChild(script);
    });
}

function _setSigBreadcrumbs(page, title) {
    if (page && page.set_breadcrumbs) {
        page.set_breadcrumbs(__("Main Dashboard"));
    }
    if (page && page.set_title) {
        page.set_title(title);
    }
}
