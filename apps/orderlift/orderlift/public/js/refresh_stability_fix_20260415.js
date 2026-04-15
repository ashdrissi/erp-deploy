(function orderliftRefreshStabilityFix() {
    if (window.__orderlift_refresh_stability_fix_20260415_installed) return;
    window.__orderlift_refresh_stability_fix_20260415_installed = true;

    function isRestrictedShellUser() {
        try {
            if (window.frappe && frappe.boot && frappe.boot.is_restricted_shell_user) return true;
            var roles = (window.frappe && frappe.boot && frappe.boot.user && frappe.boot.user.roles) || [];
            return roles.indexOf("Orderlift Admin") !== -1 && roles.indexOf("System Manager") === -1;
        } catch (e) {
            return false;
        }
    }

    function removeBlanker() {
        var el = document.getElementById("orderlift-shell-blanker");
        if (el) el.remove();
    }

    function patchSounds() {
        if (!window.frappe || !frappe.utils || !frappe.utils.play_sound) return false;
        if (frappe.utils.__orderlift_refresh_sound_patch_applied) return true;

        var originalPlaySound = frappe.utils.play_sound;
        frappe.utils.play_sound = function (name) {
            if (isRestrictedShellUser() && name === "numpad-touch") return;
            return originalPlaySound.apply(this, arguments);
        };

        frappe.utils.__orderlift_refresh_sound_patch_applied = true;
        return true;
    }

    function queueRemoveBlanker() {
        setTimeout(removeBlanker, 0);
        requestAnimationFrame(removeBlanker);
    }

    if (document.body) {
        new MutationObserver(queueRemoveBlanker).observe(document.body, {
            childList: true,
            subtree: true,
        });
    }

    queueRemoveBlanker();
    window.addEventListener("load", removeBlanker);
    window.addEventListener("pageshow", removeBlanker);
    window.addEventListener("popstate", queueRemoveBlanker);

    if (window.frappe && frappe.router && frappe.router.on) {
        frappe.router.on("change", queueRemoveBlanker);
    }

    var attempts = 50;
    (function ensureSoundPatch() {
        if (patchSounds() || attempts <= 0) return;
        attempts -= 1;
        setTimeout(ensureSoundPatch, 100);
    })();
})();
