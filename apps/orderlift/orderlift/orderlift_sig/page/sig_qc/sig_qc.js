frappe.pages["sig-qc"].on_page_load = function (wrapper) {
    wrapper.sig_page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Mobile QC"),
        single_column: true,
    });
    _setSigBreadcrumbs(wrapper.sig_page, __("Mobile QC"));
};

frappe.pages["sig-qc"].on_page_show = function (wrapper) {
    _setSigBreadcrumbs(wrapper.sig_page, __("Mobile QC"));
    renderSigPage(wrapper, {
        rootId: "sig-qc-page-shell",
        scriptId: "orderlift-sig-qc-script",
        scriptSrc: "/assets/orderlift/js/sig_qc.js?v=20260408c",
        mountKey: "orderliftSigQc",
        mountOptions: {
            preloadProject: _getPreloadProject(),
        },
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


function _getPreloadProject() {
    return (frappe.route_options && frappe.route_options.project)
        || new URL(window.location.href).searchParams.get("project")
        || "";
}
