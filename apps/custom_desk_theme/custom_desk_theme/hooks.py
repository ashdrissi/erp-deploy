app_name = "custom_desk_theme"
app_title = "Custom Desk Theme"
app_publisher = "Your Company"
app_description = "Custom Desk theme for ERPNext/Frappe"
app_email = "admin@example.com"
app_license = "MIT"

# Includes in <head> of Desk
# Keep assets always loaded; CSS is scoped to selected theme via [data-theme-mode].
app_include_css = ["/assets/custom_desk_theme/css/custom_desk_theme.css"]
app_include_js = ["/assets/custom_desk_theme/js/theme_switcher.js"]

# Allow selecting this theme from the theme switcher.
override_whitelisted_methods = {
    "frappe.core.doctype.user.user.switch_theme": "custom_desk_theme.overrides.switch_theme.switch_theme"
}
