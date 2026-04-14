frappe.pages["logistics-hub-cockpit"].on_page_load = function (wrapper) {
    wrapper.clpv2_page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Logistics Hub Cockpit"),
        single_column: true,
    });

    _setCockpitBreadcrumbs(wrapper.clpv2_page);
    _isolateCockpitPage(wrapper);
    _renderCockpitV2Once(wrapper);
};

frappe.pages["logistics-hub-cockpit"].on_page_show = function (wrapper) {
    // Frappe preserves page DOM between navigations — no re-render needed.
    // Re-subscribe realtime in case we navigated away and back.
    if (wrapper._clpv2Instance) {
        wrapper._clpv2Instance._subscribeRealtime();
    }
};

frappe.pages["logistics-hub-cockpit"].on_page_hide = function (wrapper) {
    if (wrapper._clpv2Instance) {
        wrapper._clpv2Instance._unsubscribeRealtime();
    }
};

function _renderCockpitV2Once(wrapper) {
    if (wrapper.dataset.clpv2Mounted === "1") return;
    wrapper.dataset.clpv2Mounted = "1";

    const page = wrapper.clpv2_page;
    const rootId = "clpv2-page-root";
    page.main.html(`<div id="${rootId}"></div>`);
    _stretchCockpitLayout(wrapper, rootId);

    _loadScript("orderlift-cockpit-v3-script", "/assets/orderlift/js/logistics_hub_cockpit_v3.js")
        .then(() => window.orderliftCockpitV2.mount(
            page.main[0].querySelector("#" + rootId),
            { preloadPlan: _getPreloadPlan() }
        ))
        .then(instance => { wrapper._clpv2Instance = instance; })
        .catch(err => {
            page.main.html(
                `<div class="text-muted" style="padding:24px">${frappe.utils.escape_html(err.message || __("Failed to load cockpit."))}</div>`
            );
        });
}

function _loadScript(id, src) {
    if (document.getElementById(id)) return Promise.resolve();
    return new Promise((resolve, reject) => {
        const s = document.createElement("script");
        s.id = id;
        s.src = src;
        s.async = true;
        s.onload = resolve;
        s.onerror = () => reject(new Error("Failed to load " + src));
        document.head.appendChild(s);
    });
}

function _setCockpitBreadcrumbs(page) {
    if (page && page.set_breadcrumbs) page.set_breadcrumbs(__("Main Dashboard"));
    if (page && page.set_title) page.set_title(__("Logistics Hub Cockpit"));
}

function _getPreloadPlan() {
    return (frappe.route_options && (frappe.route_options.container_load_plan || frappe.route_options.name))
        || new URL(window.location.href).searchParams.get("container_load_plan")
        || "";
}

function _stretchCockpitLayout(wrapper, rootId) {
    [
        wrapper.querySelector(".page-body"),
        wrapper.querySelector(".page-wrapper"),
        wrapper.querySelector(".page-content"),
        wrapper.querySelector(".layout-main"),
        wrapper.querySelector(".layout-main-section-wrapper"),
        wrapper.querySelector(".layout-main-section"),
    ].filter(Boolean).forEach(node => {
        node.style.height = "100%";
        node.style.minHeight = "100%";
    });

    const pageBody = wrapper.querySelector(".container.page-body");
    if (pageBody) pageBody.style.maxWidth = "100%";

    const mainSection = wrapper.querySelector(".layout-main-section");
    if (mainSection) mainSection.style.padding = "0";

    const pageRoot = wrapper.closest(".content.page-container");
    if (pageRoot) pageRoot.style.height = "calc(100vh - 88px)";

    const mapRoot = wrapper.querySelector("#" + rootId);
    if (mapRoot) {
        mapRoot.style.height = "calc(100vh - 88px)";
        mapRoot.style.minHeight = "calc(100vh - 88px)";
    }
}

function _isolateCockpitPage(wrapper) {
    if (wrapper.dataset.clpv2Isolated === "1") return;
    wrapper.dataset.clpv2Isolated = "1";

    ["mousedown", "mouseup", "pointerdown", "pointerup", "touchstart", "touchend"].forEach(evt => {
        wrapper.addEventListener(evt, e => e.stopPropagation());
    });

    wrapper.addEventListener("click", e => {
        const anchor = e.target.closest("a");
        const allowDefault = anchor && (
            anchor.getAttribute("target") === "_blank"
        );
        if (anchor && !allowDefault) e.preventDefault();
        e.stopPropagation();
    });

    wrapper.addEventListener("submit", e => {
        e.preventDefault();
        e.stopPropagation();
    });
}
