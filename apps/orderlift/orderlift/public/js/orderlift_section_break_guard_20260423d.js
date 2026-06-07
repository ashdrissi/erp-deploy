/**
 * Orderlift - Guard Frappe section-break toggle calls.
 * Prevents crashes when collapse/open runs before the drop icon exists.
 */

(function guardSectionBreakToggle() {
    if (window.__orderlift_section_break_guard_20260423d_installed) return;
    window.__orderlift_section_break_guard_20260423d_installed = true;

    function patch() {
        if (!frappe.ui || !frappe.ui.sidebar_item || !frappe.ui.sidebar_item.TypeSectionBreak) {
            return false;
        }

        var TypeSectionBreak = frappe.ui.sidebar_item.TypeSectionBreak;
        if (TypeSectionBreak.__orderliftToggleGuardPatched) {
            return true;
        }

        var proto = TypeSectionBreak.prototype;
        var originalToggle = proto.toggle;

        proto.toggle = function () {
            if (!this || !this.$drop_icon || !this.$drop_icon.length) {
                return;
            }

            return originalToggle.apply(this, arguments);
        };

        TypeSectionBreak.__orderliftToggleGuardPatched = true;
        return true;
    }

    var attempts = 120;
    (function ensurePatch() {
        if (patch() || attempts <= 0) return;
        attempts -= 1;
        setTimeout(ensurePatch, 100);
    })();
})();
