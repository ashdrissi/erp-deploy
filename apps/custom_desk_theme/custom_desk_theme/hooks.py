app_name = "custom_desk_theme"
app_title = "Custom Desk Theme"
app_publisher = "Syntax Line"
app_description = "Branded Desk theme for Orderlift — teal/cyan accent, dark/light modes, in-app CSS editor"
app_email = "contact@syntaxline.dev"
app_license = "MIT"
app_version = "1.0.0"

# Bump when you need to force browser cache refresh for theme assets.
ASSET_VERSION = "20260220-4"

# Required apps
required_apps = ["frappe"]

# ---------------------------------------------------------
# Assets — injected into Desk for all logged-in users
# ---------------------------------------------------------
app_include_css = [
    "/assets/custom_desk_theme/css/theme_20260220_2015.css",
]   
app_include_js = ["/assets/custom_desk_theme/js/custom_theme.js"]

# ---------------------------------------------------------
# Boot session — send theme settings to client on login
# ---------------------------------------------------------
boot_session = "custom_desk_theme.custom_desk_theme.doctype.theme_settings.theme_settings.get_theme_settings"

# Uncomment below if you want to override Frappe's website settings for theming
# override_whitelisted_methods = {}
