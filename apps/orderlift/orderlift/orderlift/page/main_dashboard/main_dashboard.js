frappe.pages['main-dashboard'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Control Tower',
		single_column: true
	});

	wrapper.main_dashboard = new MainDashboard(page, wrapper);
}

class MainDashboard {
	constructor(page, wrapper) {
		this.page = page;
		this.wrapper = $(wrapper).find('.layout-main-section');
		this.setup_ui();
		this.refresh();
	}

	setup_ui() {
		this.wrapper.empty();
		this.wrapper.append(`
			<style>
				.master-dash-container {
					padding: 20px 0;
					max-width: 1400px;
					margin: 0 auto;
					font-family: var(--font-stack);
				}
				.kpi-row {
					display: grid;
					grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
					gap: 20px;
					margin-bottom: 30px;
				}
				.kpi-card {
					background: var(--card-bg);
					border-radius: 12px;
					padding: 24px;
					box-shadow: 0 4px 12px rgba(0,0,0,0.03);
					border: 1px solid var(--border-color);
					display: flex;
					align-items: flex-start;
					justify-content: space-between;
					transition: transform 0.2s ease, box-shadow 0.2s ease;
				}
				.kpi-card:hover {
					transform: translateY(-2px);
					box-shadow: 0 6px 16px rgba(0,0,0,0.06);
				}
				.kpi-content {
					display: flex;
					flex-direction: column;
				}
				.kpi-label {
					font-size: 13px;
					font-weight: 600;
					color: var(--text-muted);
					text-transform: uppercase;
					letter-spacing: 0.5px;
					margin-bottom: 8px;
				}
				.kpi-value {
					font-size: 28px;
					font-weight: 800;
					color: var(--text-color);
				}
				.kpi-icon {
					padding: 12px;
					border-radius: 12px;
					display: flex;
					align-items: center;
					justify-content: center;
				}
				.kpi-icon svg {
					width: 24px;
					height: 24px;
					stroke-width: 2;
				}
				
				/* Module Gateways */
				.gateways-title {
					font-size: 18px;
					font-weight: 700;
					margin-bottom: 20px;
					color: var(--text-color);
					display: flex;
					align-items: center;
					gap: 8px;
				}
				.gateways-grid {
					display: grid;
					grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
					gap: 20px;
					margin-bottom: 30px;
				}
				.gateway-card {
					background: var(--card-bg);
					border-radius: 12px;
					padding: 0;
					box-shadow: 0 4px 12px rgba(0,0,0,0.03);
					border: 1px solid var(--border-color);
					cursor: pointer;
					overflow: hidden;
					display: flex;
					flex-direction: column;
					text-decoration: none !important;
					transition: all 0.2s ease;
				}
				.gateway-card:hover {
					transform: translateY(-3px);
					box-shadow: 0 8px 24px rgba(0,0,0,0.08);
					border-color: var(--primary-color);
				}
				.gateway-header {
					padding: 24px;
					display: flex;
					align-items: center;
					gap: 16px;
					border-bottom: 1px solid var(--border-color);
				}
				.gateway-icon {
					width: 48px;
					height: 48px;
					border-radius: 12px;
					display: flex;
					align-items: center;
					justify-content: center;
					color: white;
				}
				.gateway-icon.pricing { background: #3b82f6; }
				.gateway-icon.stock { background: #8b5cf6; }
				.gateway-icon.logistics { background: #f59e0b; }
				.gateway-icon.crm { background: #10b981; }
				
				.gateway-icon svg { width: 24px; height: 24px; stroke-width: 2; stroke: currentColor; fill: none; }
				
				.gateway-title-wrapper {
					flex: 1;
				}
				.gateway-title-wrapper h3 {
					margin: 0 0 4px 0;
					font-size: 16px;
					font-weight: 700;
					color: var(--text-color);
				}
				.gateway-title-wrapper p {
					margin: 0;
					font-size: 13px;
					color: var(--text-muted);
				}
				.gateway-footer {
					padding: 16px 24px;
					background: var(--control-bg);
					display: flex;
					align-items: center;
					justify-content: space-between;
					font-size: 13px;
					font-weight: 600;
					color: var(--primary-color);
				}
				.gateway-footer svg { width: 16px; height: 16px; }
				
				/* Dark mode tweaks */
				[data-theme="dark"] .kpi-card, [data-theme="dark"] .gateway-card {
					background: var(--card-bg);
					border-color: var(--border-color);
				}
				
				.shimmer-bg {
					animation: shimmer 2s infinite linear;
					background: linear-gradient(to right, var(--control-bg) 4%, var(--border-color) 25%, var(--control-bg) 36%);
					background-size: 1000px 100%;
					border-radius: 4px;
				}
				@keyframes shimmer {
					0% { background-position: -1000px 0; }
					100% { background-position: 1000px 0; }
				}
			</style>
			
			<div class="master-dash-container">
				
				<div class="kpi-row" id="kpi-container">
					${this.get_skeleton_kpis(4)}
				</div>
				
				<h2 class="gateways-title">
					<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
					Module Gateways
				</h2>
				
				<div class="gateways-grid">
					<!-- Pricing & Sales -->
					<div class="gateway-card" onclick="frappe.set_route('pricing-dashboard')">
						<div class="gateway-header">
							<div class="gateway-icon pricing">
								<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
							</div>
							<div class="gateway-title-wrapper">
								<h3>Pricing & Sales</h3>
								<p>Simulators, policies, published lists</p>
							</div>
						</div>
						<div class="gateway-footer">
							<span>Open Dashboard</span>
							<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"></path><path d="m12 5 7 7-7 7"></path></svg>
						</div>
					</div>
					
					<!-- Stock & Warehouses -->
					<div class="gateway-card" onclick="frappe.set_route('stock-dashboard')">
						<div class="gateway-header">
							<div class="gateway-icon stock">
								<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>
							</div>
							<div class="gateway-title-wrapper">
								<h3>Stock & Warehouses</h3>
								<p>Capacity, rotation, reorder queue</p>
							</div>
						</div>
						<div class="gateway-footer">
							<span>Open Dashboard</span>
							<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"></path><path d="m12 5 7 7-7 7"></path></svg>
						</div>
					</div>
					
					<!-- Logistics -->
					<div class="gateway-card" onclick="frappe.msgprint('Logistics Dashboard coming soon!')">
						<div class="gateway-header">
							<div class="gateway-icon logistics">
								<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><rect x="1" y="3" width="15" height="13"></rect><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"></polygon><circle cx="5.5" cy="18.5" r="2.5"></circle><circle cx="18.5" cy="18.5" r="2.5"></circle></svg>
							</div>
							<div class="gateway-title-wrapper">
								<h3>Logistics & Export</h3>
								<p>Transfers, tracking, loading</p>
							</div>
						</div>
						<div class="gateway-footer">
							<span>Open Dashboard</span>
							<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"></path><path d="m12 5 7 7-7 7"></path></svg>
						</div>
					</div>
					
					<!-- CRM -->
					<div class="gateway-card" onclick="frappe.msgprint('CRM Dashboard coming soon!')">
						<div class="gateway-header">
							<div class="gateway-icon crm">
								<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
							</div>
							<div class="gateway-title-wrapper">
								<h3>CRM</h3>
								<p>Pipeline, customers, agents</p>
							</div>
						</div>
						<div class="gateway-footer">
							<span>Open Dashboard</span>
							<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"></path><path d="m12 5 7 7-7 7"></path></svg>
						</div>
					</div>
				</div>
				
			</div>
		`);
	}

	get_skeleton_kpis(count) {
		let html = '';
		for (let i = 0; i < count; i++) {
			html += `
				<div class="kpi-card">
					<div class="kpi-content" style="width: 100%;">
						<div class="shimmer-bg" style="width: 120px; height: 16px; margin-bottom: 12px;"></div>
						<div class="shimmer-bg" style="width: 80px; height: 32px;"></div>
					</div>
				</div>
			`;
		}
		return html;
	}

	refresh() {
		frappe.call({
			method: "orderlift.orderlift.page.main_dashboard.main_dashboard.get_dashboard_data",
			callback: (r) => {
				if (r.message) {
					this.render_kpis(r.message.stats);
				}
			}
		});
	}

	render_kpis(stats) {
		const format_curr = (val) => format_currency(val, frappe.boot.sysdefaults.currency);
		const kpis = [
			{ label: "Sales (MTD)", value: format_curr(stats.sales_mtd), color: "var(--blue-500)", bg: "var(--blue-50)", icon: `<path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>` },
			{ label: "Pending Quotes", value: stats.quotes_pending, color: "var(--orange-500)", bg: "var(--orange-50)", icon: `<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline>` },
			{ label: "Pending Transfers", value: stats.transfers_pending, color: "var(--purple-500)", bg: "var(--purple-50)", icon: `<rect x="1" y="3" width="15" height="13"></rect><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"></polygon><circle cx="5.5" cy="18.5" r="2.5"></circle><circle cx="18.5" cy="18.5" r="2.5"></circle>` },
			{ label: "Open Tickets", value: stats.open_tickets, color: "var(--red-500)", bg: "var(--red-50)", icon: `<circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line>` }
		];

		let html = '';
		kpis.forEach(k => {
			html += `
				<div class="kpi-card">
					<div class="kpi-content">
						<div class="kpi-label">${k.label}</div>
						<div class="kpi-value">${k.value}</div>
					</div>
					<div class="kpi-icon" style="background: ${k.bg}; color: ${k.color};">
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round">
							${k.icon}
						</svg>
					</div>
				</div>
			`;
		});

		this.wrapper.find('#kpi-container').html(html);
	}
}
