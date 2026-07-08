(function () {
    const HIDDEN_LABELS = new Set(["Full Page"]);
    const HIDDEN_CLASS = "orderlift-print-control-hidden";

    function isPrintSurface() {
        const route = typeof frappe !== "undefined" && frappe.get_route ? frappe.get_route() : [];
        return window.location.pathname.indexOf("/printview") !== -1
            || route[0] === "print"
            || window.location.hash.indexOf("#print") !== -1;
    }

    function ensureStyle() {
        if (document.getElementById("orderlift-print-controls-style")) return;
        const style = document.createElement("style");
        style.id = "orderlift-print-controls-style";
        style.textContent = `.${HIDDEN_CLASS} { display: none !important; }`;
        document.head.appendChild(style);
    }

    function normalizedText(element) {
        return String((element && element.textContent) || "").replace(/\s+/g, " ").trim();
    }

    function hidePrintControls() {
        if (!isPrintSurface()) return;
        ensureStyle();
        document.querySelectorAll("button, a, .btn").forEach((element) => {
            if (HIDDEN_LABELS.has(normalizedText(element))) {
                element.classList.add(HIDDEN_CLASS);
            }
        });
    }

    function startObserver() {
        if (window.__orderlift_print_controls_observer) return;
        const observer = new MutationObserver(hidePrintControls);
        observer.observe(document.documentElement, { childList: true, subtree: true });
        window.__orderlift_print_controls_observer = observer;
        window.setTimeout(() => {
            observer.disconnect();
            window.__orderlift_print_controls_observer = null;
        }, 10000);
    }

    function init() {
        hidePrintControls();
        startObserver();
    }

    if (typeof frappe !== "undefined" && frappe.router && frappe.router.on) {
        frappe.router.on("change", init);
    }
    window.addEventListener("hashchange", init);

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
