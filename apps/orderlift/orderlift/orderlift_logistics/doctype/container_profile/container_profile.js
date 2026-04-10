(function () {
    const CSS_ID = "orderlift-logistics-workspace-css-20260410";
    const CSS_PATH = "/assets/orderlift/css/logistics_workspace_20260410.css";
    const JS_PATH = "/assets/orderlift/js/container_profile_workspace_20260410.js";

    if (!document.getElementById(CSS_ID)) {
        const link = document.createElement("link");
        link.id = CSS_ID;
        link.rel = "stylesheet";
        link.href = CSS_PATH;
        document.head.appendChild(link);
    }

    if (!window.__orderlift_container_profile_loader_20260410) {
        window.__orderlift_container_profile_loader_20260410 = true;
        frappe.require(JS_PATH);
    }
})();
