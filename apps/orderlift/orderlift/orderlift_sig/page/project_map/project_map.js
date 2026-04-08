frappe.pages["project-map"].on_page_load = function (wrapper) {
    wrapper.sig_page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Project Map"),
        single_column: true,
    });
    _setSigBreadcrumbs(wrapper.sig_page, __("Project Map"));
};

frappe.pages["project-map"].on_page_show = function (wrapper) {
    _setSigBreadcrumbs(wrapper.sig_page, __("Project Map"));
    renderSigPage(wrapper, {
        rootId: "sig-map-page-root",
        scriptId: "orderlift-sig-map-script-v4",
        scriptSrc: "/assets/orderlift/js/sig_map.js?v=20260408f",
        mountKey: "orderliftSigMap",
        mountOptions: {
            preloadProject: _getPreloadProject(),
        },
    });
};

function renderSigPage(wrapper, config) {
    const page = wrapper.sig_page;
    page.main.html(`<div id="${config.rootId}"></div>`);
    _stretchProjectMapLayout(wrapper, config.rootId);
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

function _stretchProjectMapLayout(wrapper, rootId) {
    const pageRoot = wrapper.closest(".content.page-container");
    const mapRoot = wrapper.querySelector(`#${rootId}`);

    [
        wrapper.querySelector(".page-body"),
        wrapper.querySelector(".page-wrapper"),
        wrapper.querySelector(".page-content"),
        wrapper.querySelector(".layout-main"),
        wrapper.querySelector(".layout-main-section-wrapper"),
        wrapper.querySelector(".layout-main-section"),
    ].filter(Boolean).forEach((node) => {
        node.style.height = "100%";
        node.style.minHeight = "100%";
    });

    const pageBody = wrapper.querySelector(".container.page-body");
    if (pageBody) {
        pageBody.style.maxWidth = "100%";
    }

    const mainSection = wrapper.querySelector(".layout-main-section");
    if (mainSection) {
        mainSection.style.padding = "0";
    }

    if (pageRoot) {
        pageRoot.style.height = "calc(100vh - 88px)";
    }

    if (mapRoot) {
        mapRoot.style.height = "calc(100vh - 88px)";
        mapRoot.style.minHeight = "calc(100vh - 88px)";
    }
}
