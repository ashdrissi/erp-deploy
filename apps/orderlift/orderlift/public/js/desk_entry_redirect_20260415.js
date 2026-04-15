(function orderliftDeskEntryRedirect() {
    if (window.__orderlift_desk_entry_redirect_20260415_installed) return;
    window.__orderlift_desk_entry_redirect_20260415_installed = true;

    var pathname = (window.location.pathname || "").replace(/\/+$/, "");
    if (pathname !== "/desk" && pathname !== "/app") return;

    var target = "/desk/home-page?sidebar=Main+Dashboard";
    var current = window.location.pathname + window.location.search + window.location.hash;
    if (current !== target) {
        window.location.replace(target);
    }
})();
