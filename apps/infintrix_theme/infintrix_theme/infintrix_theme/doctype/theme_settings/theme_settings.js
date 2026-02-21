// Copyright (c) 2025, Muqeet Mughal and contributors
// For license information, please see license.txt

frappe.ui.form.on("Theme Settings", {
	theme_preset(frm) {
		const preset = frm.doc.theme_preset;
		if (!preset) return;

		const presets = {
			"Modern Pro": {
				color: "#2563EB",
				surface_bg_color: "#F7F9FC",
				surface_card_color: "#FFFFFF",
				border_color: "#D7DEEB",
				text_primary_color: "#0F172A",
				text_muted_color: "#64748B",
				btn_radius: 10,
				card_radius: 16,
				sidebar_width: 248,
				table_striped: 1,
				table_header_bg: 1,
				table_density_mode: "Standard",
				table_header_height: 44,
				table_header_radius: 10,
				table_border_mode: "Subtle",
				table_zebra_mode: "Soft",
				table_hover_style: "Lift",
				table_row_radius: 10,
				table_row_gap: 6,
				table_sort_icon_style: "Bold",
				table_toolbar_style: "Glass",
				ui_density_mode: "Standard",
				content_max_width: 1680,
				navbar_blur_strength: 20,
				button_text_transform: "None",
				card_border_style: "Subtle",
				badge_style: "Soft",
			},
			Minimal: {
				color: "#334155",
				surface_bg_color: "#F8FAFC",
				surface_card_color: "#FFFFFF",
				border_color: "#E2E8F0",
				text_primary_color: "#0F172A",
				text_muted_color: "#64748B",
				btn_radius: 6,
				card_radius: 10,
				sidebar_width: 236,
				table_striped: 0,
				table_header_bg: 0,
				table_density_mode: "Compact",
				table_header_height: 40,
				table_header_radius: 8,
				table_border_mode: "Subtle",
				table_zebra_mode: "Off",
				table_hover_style: "Soft",
				table_row_radius: 8,
				table_row_gap: 4,
				table_sort_icon_style: "Minimal",
				table_toolbar_style: "Flat",
				ui_density_mode: "Compact",
				content_max_width: 1520,
				navbar_blur_strength: 0,
				button_text_transform: "None",
				card_border_style: "Subtle",
				badge_style: "Outline",
			},
			Glass: {
				color: "#0EA5E9",
				surface_bg_color: "#EDF4FF",
				surface_card_color: "rgba(255,255,255,0.78)",
				border_color: "#BFDBFE",
				text_primary_color: "#0B1324",
				text_muted_color: "#64748B",
				btn_radius: 12,
				card_radius: 18,
				sidebar_width: 250,
				glass_blur: 14,
				table_striped: 1,
				table_header_bg: 1,
				table_density_mode: "Spacious",
				table_header_height: 48,
				table_header_radius: 12,
				table_border_mode: "Strong",
				table_zebra_mode: "Soft",
				table_hover_style: "Glow",
				table_row_radius: 12,
				table_row_gap: 8,
				table_sort_icon_style: "Bold",
				table_toolbar_style: "Glass",
				ui_density_mode: "Spacious",
				content_max_width: 1760,
				navbar_blur_strength: 26,
				button_text_transform: "None",
				card_border_style: "Strong",
				badge_style: "Soft",
			},
		};

		const nextValues = presets[preset];
		if (!nextValues) return;

		Object.entries(nextValues).forEach(([field, value]) => {
			frm.set_value(field, value);
		});
	},

   refresh(frm) {
        // render preview initially
        frm.trigger("render_font_preview");
    },

    font_family(frm) {
        // re-render preview on font change
        frm.trigger("render_font_preview");
    },

    render_font_preview(frm) {
        if (!frm.doc.font_family) return;



        const font = frm.doc.font_family;

        // Build preview HTML
        frm.fields_dict.font_preview.$wrapper.html(`
            <iframe srcdoc='
              <!doctype html>
              <html>
              <head>
              	<link type="text/css" rel="stylesheet" href="https://fonts.googleapis.com/css?family=${frm.doc.font_family}:300,400,500,600,700,800,900">

                <style>
                  body { margin:0; padding:16px; font-family:${font}; font-size:15px; line-height:1.5; }
                  h3 { margin-top:0; font-size:18px; }
                  .sample { border:1px solid #ddd; padding:12px; border-radius:6px; margin-bottom:12px; }
                  .mono { font-family: monospace; }
                </style>
              </head>
              <body>
                <h3>${font} Preview</h3>
                <div class="sample">
                  Aa Bb Cc Dd Ee Ff Gg Hh Ii Jj Kk Ll Mm Nn<br>
                  0123456789 ! @ # $ % ^ & * ( )<br>
                  Customer Invoice #INV-2025-0914<br>
                  PO-3489 / Sales Order SO-1204<br>
                  Payment Received: $12,450.50 (via Stripe)<br>
                  <span class="mono">Item Code: PRD-XL-2025 @ Warehouse A1</span>
                </div>
                <div class="sample">
                  <strong>Dashboard</strong><br>
                  Customers · Suppliers · Items · Inventory · Accounting · HR<br>
                </div>
              </body>
              </html>
            ' style="width:100%;height:300px;border:0"></iframe>
        `);
    },
    after_save(frm) {
        frappe.call({
            method: "frappe.sessions.clear",
            type: "POST",
            callback: function(r) {
                location.reload();
            }
        });

        
    }
});
