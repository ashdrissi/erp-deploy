// Add a selectable "Custom" Desk theme to the theme switcher.
// Frappe maps the selected theme to the `User.desk_theme` field.

frappe.ui.ThemeSwitcher = class CustomDeskThemeSwitcher extends frappe.ui.ThemeSwitcher {
  constructor() {
    super();
  }

  fetch_themes() {
    return new Promise((resolve) => {
      this.themes = [
        {
          name: "light",
          label: __("Frappe Light"),
          info: __("Light Theme"),
        },
        {
          name: "dark",
          label: __("Frappe Dark"),
          info: __("Dark Theme"),
        },
        {
          name: "custom",
          label: __("Custom"),
          info: __("Custom Desk Theme"),
        },
        {
          name: "automatic",
          label: __("Automatic"),
          info: __("Uses system theme preference"),
        },
      ];

      resolve(this.themes);
    });
  }
};
