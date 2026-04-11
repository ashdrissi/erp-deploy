frappe.pages["project-map"].on_page_load = function (wrapper) {
    wrapper.sig_page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Project Map"),
        single_column: true,
    });
    _setSigBreadcrumbs(wrapper.sig_page, __("Project Map"));
    _isolateProjectMapPage(wrapper);
    _renderProjectMapOnce(wrapper);
};

frappe.pages["project-map"].on_page_show = function (wrapper) {
    // Frappe preserves page DOM between navigations — nothing to re-render here.
    // Breadcrumbs and title are set once in on_page_load.
    // Re-calling set_title / set_breadcrumbs on every show causes visible flicker.
};

function _renderProjectMapOnce(wrapper) {
    renderSigPage(wrapper, {
        rootId: "sig-map-page-root",
        scriptId: "orderlift-sig-map-script-v10",
        scriptSrc: "/assets/orderlift/js/sig_map_workspace_20260410d.js",
        mountKey: "orderliftSigMap",
        mountOptions: {
            preloadProject: _getPreloadProject(),
        },
    });
}

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

function _isolateProjectMapPage(wrapper) {
    if (wrapper.dataset.projectMapIsolated === "1") return;
    wrapper.dataset.projectMapIsolated = "1";

    // Bubble-phase stopPropagation keeps mouse/pointer/touch events inside the map
    // wrapper so they don't leak to Frappe's document-level handlers.
    ["mousedown", "mouseup", "pointerdown", "pointerup", "touchstart", "touchend"].forEach((eventName) => {
        wrapper.addEventListener(eventName, (event) => {
            event.stopPropagation();
        });
    });

    // For clicks: the workspace's own root-level handler (bubble phase) already
    // calls frappe.set_route() for data-route/data-page-route/data-form-doctype
    // elements and also calls stopPropagation(). We add a wrapper-level backup
    // that prevents any anchor navigation that slipped past the root handler from
    // reaching Frappe's document-level link interceptor.
    wrapper.addEventListener("click", (event) => {
        const anchor = event.target.closest("a");
        const allowDefault = anchor && (
            anchor.getAttribute("target") === "_blank"
            || anchor.closest(".leaflet-control-attribution")
        );

        if (anchor && !allowDefault) {
            event.preventDefault();
        }

        event.stopPropagation();
    });

    wrapper.addEventListener("submit", (event) => {
        event.preventDefault();
        event.stopPropagation();
    });
}
