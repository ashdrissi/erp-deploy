(function () {
    "use strict";

    const root = document.getElementById("ol-b2b-portal-root");
    if (!root) return;

    const isGuest  = Number(root.dataset.isGuest || 0) === 1;
    const loginUrl = root.dataset.loginUrl || "/login?redirect-to=/b2b-portal";

    const state = {
        bootstrap:    null,
        catalog:      [],
        basket:       loadBasket(),
        entryIndex:   {},
        catalogView:  "grid",   // "grid" | "list"
        searchTimer:  null,
    };

    if (isGuest) { renderGuest(); return; }
    boot();

    /* ── Boot ───────────────────────────────────────────────── */
    async function boot() {
        try {
            state.bootstrap = await api("orderlift.orderlift_client_portal.api.get_bootstrap");
            render();
            bindEvents();
        } catch (err) { renderError(err); }
    }

    /* ── Top-level render ───────────────────────────────────── */
    function render() {
        const route        = parseRoute();
        const user         = (state.bootstrap && state.bootstrap.user) || {};
        const initials     = makeInitials(user.customer_name || user.email || "U");
        const basketCount  = state.basket.reduce((s, r) => s + Number(r.qty || 0), 0);

        root.innerHTML = `
          <div class="olp-shell">
            <div class="olp-layout">
              <!-- Sidebar -->
              <aside class="olp-sidebar">
                <div class="olp-sidebar-logo">
                  <div class="olp-logo-icon">${iconBuildingStore()}</div>
                  <div>
                    <div class="olp-logo-name">Orderlift B2B</div>
                    <div class="olp-logo-sub" title="${escapeHtml(user.customer_group||'')}">
                      ${escapeHtml(user.customer_group || "Portal")}
                    </div>
                  </div>
                </div>
                <nav class="olp-sidebar-nav">
                  <div class="olp-nav-group">Main</div>
                  ${navBtn("dashboard",     "Dashboard",    route.page, iconGrid())}
                  ${navBtn("catalog",       "Catalog",      route.page, iconList())}
                  ${navBtn("request-quote", "Quote Basket", route.page, iconBasket(), basketCount || "")}
                  ${navBtn("requests",      "My Requests",  route.page, iconDoc())}
                  ${navBtn("quotations",    "Quotations",   route.page, iconQuote())}
                  <div class="olp-nav-group">Account</div>
                  ${navBtn("account", "My Account", route.page, iconUser())}
                </nav>
                <div class="olp-sidebar-user" id="olp-user-menu-trigger">
                  <div class="olp-avatar">${escapeHtml(initials)}</div>
                  <div class="olp-sidebar-user-info">
                    <div class="olp-user-name">${escapeHtml(user.customer_name || "Portal User")}</div>
                    <div class="olp-user-email">${escapeHtml(user.email || "")}</div>
                  </div>
                  <div class="olp-user-menu-chevron">${iconChevron()}</div>
                </div>
                <div id="olp-user-menu" class="olp-user-menu" style="display:none;">
                  <button class="olp-user-menu-item" data-nav-page="account">
                    ${iconUser()} My Account
                  </button>
                  <a class="olp-user-menu-item" href="/update-password">
                    ${iconKey()} Change Password
                  </a>
                  <div class="olp-user-menu-divider"></div>
                  <button class="olp-user-menu-item olp-user-menu-item-danger" id="olp-logout-btn">
                    ${iconLogout()} Sign Out
                  </button>
                </div>
              </aside>
              <!-- Main -->
              <main class="olp-main-wrap">
                <div class="olp-topbar">
                  <div class="olp-topbar-title">${pageTitle(route.page)}</div>
                  <div class="olp-topbar-spacer"></div>
                  <div class="olp-search-wrap">
                    ${iconSearch()}
                    <input id="olp-global-search" placeholder="Search catalog…" value="${escapeHtml(route.search || "")}">
                  </div>
                  <button class="olp-btn olp-btn-primary" data-nav-page="request-quote">
                    ${iconBasket()}
                    Basket${basketCount ? ` <span class="olp-nav-badge">${basketCount}</span>` : ""}
                  </button>
                </div>
                <div class="olp-main" id="olp-main"></div>
              </main>
            </div>
            <div id="olp-modal-root"></div>
            <div id="olp-toast-root" class="olp-toast-root"></div>
          </div>`;

        renderRoute(route);
    }

    async function renderRoute(route) {
        if (route.page === "catalog")       return renderCatalog(route);
        if (route.page === "request-quote") return renderBasket();
        if (route.page === "requests")      return renderRequests();
        if (route.page === "quotations")    return renderQuotations();
        if (route.page === "request")       return renderRequestDetail(route.param);
        if (route.page === "item")          return renderCatalogDetail("item",   route.param);
        if (route.page === "bundle")        return renderCatalogDetail("bundle", route.param);
        if (route.page === "account")       return renderAccount();
        return renderDashboard();
    }

    /* ── Dashboard ──────────────────────────────────────────── */
    function renderDashboard() {
        const ctx     = state.bootstrap || {};
        const user    = ctx.user    || {};
        const metrics = ctx.metrics || {};
        const policy  = ctx.policy  || {};
        const featured = (ctx.featured_catalog || []).slice(0, 6);
        const recent   = ctx.recent_requests   || [];
        const recentQ  = ctx.recent_quotations || [];

        const hr      = new Date().getHours();
        const greeting = hr < 12 ? "Good morning" : hr < 17 ? "Good afternoon" : "Good evening";
        const dateStr  = new Date().toLocaleDateString("en-US", { weekday:"long", month:"long", day:"numeric", year:"numeric" });

        setView(`
          <div class="olp-welcome">
            <div>
              <div class="olp-welcome-greeting">${greeting}, ${escapeHtml(user.customer_name || "there")} 👋</div>
              <div class="olp-welcome-sub">${escapeHtml(dateStr)} · ${escapeHtml(user.customer_group || "")}</div>
            </div>
            <div class="olp-welcome-actions">
              <button class="olp-btn olp-btn-white" data-nav-page="catalog">${iconList()} Browse Catalog</button>
              <button class="olp-btn olp-btn-white-solid" data-nav-page="request-quote">${iconBasket()} Quote Basket</button>
            </div>
          </div>

          <div class="olp-kpi-row">
            ${kpiCard("Catalog Products", metrics.visible_products  || 0, "approved for your group", "blue",   iconList())}
            ${kpiCard("Quote Requests",   metrics.requests_total    || 0, "submitted via portal",    "orange", iconDoc())}
            ${kpiCard("Quotations",       metrics.quotations_total  || 0, "available to download",   "green",  iconQuote())}
            ${kpiCard("Basket Lines",     state.basket.length,             "ready to submit",         "purple", iconBasket())}
          </div>

          <div class="olp-quick-actions">
            <button class="olp-quick-action" data-nav-page="catalog">${iconList()} Browse catalog</button>
            <button class="olp-quick-action" data-nav-page="request-quote">${iconBasket()} Open basket</button>
            <button class="olp-quick-action" data-nav-page="requests">${iconDoc()} My requests</button>
            <button class="olp-quick-action" data-nav-page="quotations">${iconQuote()} Download quotations</button>
          </div>

          <div class="olp-grid olp-grid-2" style="margin-bottom:24px;">
            <div class="olp-card">
              <div class="olp-card-head">
                <div><div class="olp-card-title">Recent Requests</div><div class="olp-card-sub">Latest quote activity</div></div>
                <button class="olp-btn olp-btn-sm olp-btn-ghost" data-nav-page="requests">View all</button>
              </div>
              ${renderActivityFeed(recent)}
            </div>
            <div style="display:flex;flex-direction:column;gap:16px;">
              <div class="olp-card">
                <div class="olp-card-head">
                  <div class="olp-card-title">Account</div>
                  <button class="olp-btn olp-btn-sm olp-btn-ghost" data-nav-page="account">Details</button>
                </div>
                <div class="olp-pad-sm">
                  <div class="olp-info-block" style="margin-bottom:0;">
                    ${infoRow("Customer",     user.customer_name   || "—")}
                    ${infoRow("Group",        user.customer_group  || "—")}
                    ${infoRow("Quote Access", policy.quote_request_allowed ? "✓ Enabled" : "Disabled")}
                    ${infoRow("Currency",     policy.currency      || "MAD")}
                  </div>
                </div>
              </div>
              <div class="olp-card">
                <div class="olp-card-head">
                  <div class="olp-card-title">Recent Quotations</div>
                  <button class="olp-btn olp-btn-sm olp-btn-ghost" data-nav-page="quotations">View all</button>
                </div>
                ${renderRecentQuotations(recentQ.slice(0, 3))}
              </div>
            </div>
          </div>

          ${featured.length ? `
          <div class="olp-section">
            <div class="olp-section-head">
              <div>
                <div class="olp-section-title">Featured Products</div>
                <div class="olp-section-sub">Curated selection for your group</div>
              </div>
              <button class="olp-btn olp-btn-sm" data-nav-page="catalog">Browse all ${metrics.visible_products || ""} products</button>
            </div>
            <div class="olp-product-grid">${renderProductCards(featured)}</div>
          </div>` : ""}
        `);
    }

    function renderActivityFeed(rows) {
        if (!rows.length) return `<div class="olp-empty"><div class="olp-empty-title">No requests yet</div><div class="olp-empty-sub">Submit your first quote from the catalog.</div></div>`;
        return `<div class="olp-activity-list">${rows.map(row => `
          <div class="olp-activity-item" data-nav-page="request/${escapeHtml(row.name)}">
            <div class="olp-activity-dot olp-activity-dot-${statusDotColor(row.status)}"></div>
            <div class="olp-activity-content">
              <div class="olp-activity-title">${escapeHtml(row.name)}</div>
              <div class="olp-activity-meta">
                <span class="olp-status ${statusClass(row.status)}">${escapeHtml(row.status||"")}</span>
                <span>${escapeHtml(fmtDate(row.modified||""))}</span>
              </div>
            </div>
            <div class="olp-activity-amount">${formatMoney(row.total_amount, row.currency)}</div>
          </div>`).join("")}
        </div>`;
    }

    function renderRecentQuotations(rows) {
        if (!rows.length) return `<div class="olp-empty" style="padding:20px;"><div class="olp-empty-sub">No quotations yet.</div></div>`;
        return `<div class="olp-activity-list">${rows.map(row => `
          <div class="olp-activity-item" data-nav-page="request/${escapeHtml(row.request_name||"")}">
            <div class="olp-activity-dot olp-activity-dot-green"></div>
            <div class="olp-activity-content">
              <div class="olp-activity-title">${escapeHtml(row.quotation||"")}</div>
              <div class="olp-activity-meta">
                <span class="olp-status ${statusClass(row.status)}">${escapeHtml(row.status||"")}</span>
                ${row.valid_till ? `<span>Valid ${escapeHtml(String(row.valid_till))}</span>` : ""}
              </div>
            </div>
            <div class="olp-activity-amount">${formatMoney(row.grand_total, row.currency)}</div>
          </div>`).join("")}
        </div>`;
    }

    /* ── Catalog ────────────────────────────────────────────── */
    async function renderCatalog(route) {
        setView(`<div class="olp-skeleton" style="height:52px;border-radius:12px;margin-bottom:16px;"></div><div class="olp-product-grid">${Array(6).fill('<div class="olp-skeleton" style="height:260px;border-radius:14px;"></div>').join("")}</div>`);

        const results = await api("orderlift.orderlift_client_portal.api.get_catalog", {
            search: route.search || "", featured: 0, limit: 200,
        }).catch(() => []);
        state.catalog = results || [];
        indexEntries(state.catalog);

        const brands   = uniqueSorted(state.catalog.map(r => r.brand).filter(Boolean));
        const groups   = uniqueSorted(state.catalog.map(r => r.item_group).filter(Boolean));
        const filtered = applyCatalogFilters(state.catalog, route);
        const viewMode = state.catalogView;

        setView(`
          <!-- Compact filter bar -->
          <div class="olp-filter-bar">
            <div class="olp-filter-search-wrap">
              ${iconSearch()}
              <input id="olp-filter-search" class="olp-filter-search-input"
                value="${escapeHtml(route.search||"")}"
                placeholder="Search products…">
              ${route.search ? `<button class="olp-filter-clear-btn" data-clear-search>×</button>` : ""}
            </div>
            <div class="olp-filter-chips">
              <select id="olp-filter-kind" class="olp-filter-chip-select">
                <option value="">All types</option>
                <option value="item"   ${route.kind==="item"   ?"selected":""}>Items</option>
                <option value="bundle" ${route.kind==="bundle" ?"selected":""}>Bundles</option>
              </select>
              ${brands.length ? `
              <select id="olp-filter-brand" class="olp-filter-chip-select">
                <option value="">All brands</option>
                ${brands.map(b=>`<option value="${escapeHtml(b)}" ${route.brand===b?"selected":""}>${escapeHtml(b)}</option>`).join("")}
              </select>` : ""}
              ${groups.length ? `
              <select id="olp-filter-group" class="olp-filter-chip-select">
                <option value="">All groups</option>
                ${groups.map(g=>`<option value="${escapeHtml(g)}" ${route.group===g?"selected":""}>${escapeHtml(g)}</option>`).join("")}
              </select>` : ""}
              <select id="olp-filter-sort" class="olp-filter-chip-select">
                <option value="sort"       ${!route.sort||route.sort==="sort"  ?"selected":""}>Default</option>
                <option value="price_asc"  ${route.sort==="price_asc"          ?"selected":""}>Price ↑</option>
                <option value="price_desc" ${route.sort==="price_desc"         ?"selected":""}>Price ↓</option>
                <option value="name"       ${route.sort==="name"               ?"selected":""}>A – Z</option>
              </select>
              <button id="olp-apply-filters" class="olp-btn olp-btn-primary olp-btn-sm">Apply</button>
            </div>
            <div class="olp-filter-end">
              <span class="olp-filter-count">${filtered.length} product${filtered.length!==1?"s":""}</span>
              <div class="olp-view-toggle">
                <button class="olp-view-btn ${viewMode==="grid"?"is-active":""}" data-view="grid" title="Grid view">${iconGridSmall()}</button>
                <button class="olp-view-btn ${viewMode==="list"?"is-active":""}" data-view="list" title="List view">${iconListSmall()}</button>
              </div>
            </div>
          </div>

          ${filtered.length
              ? (viewMode === "list"
                  ? `<div class="olp-card"><div class="olp-table-wrap">${renderCatalogListView(filtered)}</div></div>`
                  : `<div class="olp-product-grid">${renderProductCards(filtered)}</div>`)
              : `<div class="olp-card"><div class="olp-empty"><div class="olp-empty-title">No products found</div><div class="olp-empty-sub">Try clearing your filters.</div></div></div>`
          }
        `);
    }

    function renderCatalogListView(rows) {
        return `<table class="olp-table">
          <thead><tr><th>Product</th><th>Type</th><th>Brand</th><th>Group</th><th>Price</th><th></th></tr></thead>
          <tbody>${rows.map(row => `
            <tr>
              <td>
                <div class="olp-table-title">${escapeHtml(row.title||row.code)}</div>
                <div class="olp-table-sub">${escapeHtml(row.code||"")}</div>
              </td>
              <td><span class="olp-badge ${row.kind==="bundle"?"olp-badge-purple":"olp-badge-blue"}" style="font-size:10px;">${escapeHtml(row.kind||"item")}</span></td>
              <td style="color:var(--olp-text-2);font-size:12px;">${escapeHtml(row.brand||"—")}</td>
              <td style="color:var(--olp-text-2);font-size:12px;">${escapeHtml(row.item_group||"—")}</td>
              <td style="font-weight:600;color:var(--olp-blue);">${formatMoney(row.price_rate,row.currency)}</td>
              <td>
                <div class="olp-table-actions">
                  <button class="olp-btn olp-btn-sm" data-detail-kind="${escapeHtml(row.kind||"item")}" data-detail-code="${escapeHtml(row.code||"")}">View</button>
                  <button class="olp-btn olp-btn-primary olp-btn-sm" data-open-add="${escapeHtml(row.rule_name)}">+ Add</button>
                </div>
              </td>
            </tr>`).join("")}
          </tbody>
        </table>`;
    }

    /* ── Catalog detail ─────────────────────────────────────── */
    async function renderCatalogDetail(kind, code) {
        try {
            const entry = await api("orderlift.orderlift_client_portal.api.get_catalog_entry", { kind, code });
            indexEntries([entry]);
            setView(`
              <div class="olp-back-link" data-nav-page="catalog">${iconBack()} Back to catalog</div>
              <div class="olp-detail-grid">
                <div class="olp-card olp-pad">
                  <div class="olp-detail-media">
                    ${entry.image
                        ? `<img src="${escapeHtml(entry.image)}" alt="${escapeHtml(entry.title||"")}"/>`
                        : `<div style="text-align:center;color:var(--olp-text-3);">${iconBox()}<br><span style="font-size:11px;">No image</span></div>`}
                  </div>
                </div>
                <div class="olp-card olp-pad">
                  <div class="olp-inline-actions">
                    <span class="olp-badge ${kind==="bundle"?"olp-badge-purple":"olp-badge-blue"}">${kind==="bundle"?"Bundle":"Item"}</span>
                    ${entry.featured ? `<span class="olp-badge olp-badge-orange">★ Featured</span>` : ""}
                  </div>
                  <div class="olp-detail-title">${escapeHtml(entry.title||"")}</div>
                  <div class="olp-detail-sub">${escapeHtml(entry.description||"")}</div>
                  <div class="olp-detail-meta">
                    <span>${escapeHtml(entry.code||"")}</span>
                    ${entry.brand      ? `<span class="olp-detail-meta-sep">·</span><span>${escapeHtml(entry.brand)}</span>` : ""}
                    ${entry.item_group ? `<span class="olp-detail-meta-sep">·</span><span>${escapeHtml(entry.item_group)}</span>` : ""}
                  </div>
                  <div class="olp-detail-price">${formatMoney(entry.price_rate, entry.currency)}</div>
                  <div class="olp-divider"></div>
                  <div class="olp-info-grid">
                    ${infoStat("UOM",      entry.uom      || "—")}
                    ${infoStat("Material", entry.material || "—")}
                    ${infoStat("Weight",   entry.weight_kg ? `${Number(entry.weight_kg).toFixed(2)} kg` : "—")}
                    ${infoStat("Type",     kind==="bundle" ? "Bundle" : "Item")}
                  </div>
                  <!-- Inline quantity + add -->
                  <div class="olp-add-row" style="margin-top:18px;">
                    <div class="olp-qty-stepper">
                      <button class="olp-qty-stepper-btn" data-stepper-target="olp-detail-qty" data-stepper-dir="-1">−</button>
                      <input id="olp-detail-qty" class="olp-qty-stepper-input" type="number" min="1" value="1">
                      <button class="olp-qty-stepper-btn" data-stepper-target="olp-detail-qty" data-stepper-dir="1">+</button>
                    </div>
                    <button class="olp-btn olp-btn-primary" id="olp-detail-add-btn" data-rule-name="${escapeHtml(entry.rule_name)}">
                      ${iconBasket()} Add to basket
                    </button>
                    <button class="olp-btn" data-nav-page="request-quote">Open basket</button>
                  </div>
                  ${renderBundleChildren(entry.children||[])}
                </div>
              </div>`);
        } catch (err) { renderError(err); }
    }

    /* ── Requests ───────────────────────────────────────────── */
    async function renderRequests() {
        setView(`<div class="olp-skeleton" style="height:300px;border-radius:14px;"></div>`);
        const rows = await api("orderlift.orderlift_client_portal.api.get_my_requests").catch(() => []);
        setView(`
          <div class="olp-card">
            <div class="olp-card-head">
              <div><div class="olp-card-title">My Quote Requests</div><div class="olp-card-sub">${rows.length} total</div></div>
            </div>
            <div class="olp-table-wrap">${renderRequestTable(rows)}</div>
          </div>`);
    }

    /* ── Quotations ─────────────────────────────────────────── */
    async function renderQuotations() {
        setView(`<div class="olp-skeleton" style="height:300px;border-radius:14px;"></div>`);
        const rows = await api("orderlift.orderlift_client_portal.api.get_my_quotations").catch(() => []);
        setView(`
          <div class="olp-card">
            <div class="olp-card-head">
              <div><div class="olp-card-title">My Quotations</div><div class="olp-card-sub">${rows.length} available</div></div>
            </div>
            <div class="olp-table-wrap">${renderQuotationTable(rows)}</div>
          </div>`);
    }

    /* ── Request detail ─────────────────────────────────────── */
    async function renderRequestDetail(name) {
        try {
            const req = await api("orderlift.orderlift_client_portal.api.get_request_detail", { name });
            setView(`
              <div class="olp-back-link" data-nav-page="requests">${iconBack()} Back to requests</div>
              <div class="olp-detail-grid">
                <div>
                  <div class="olp-section-head" style="margin-bottom:14px;">
                    <div>
                      <div class="olp-section-title">${escapeHtml(req.name)}</div>
                      <div class="olp-section-sub">Submitted ${escapeHtml(fmtDate(req.submitted_on||""))}</div>
                    </div>
                    <span class="olp-status ${statusClass(req.status)}">${escapeHtml(req.status||"")}</span>
                  </div>
                  <div class="olp-card">
                    <div class="olp-table-wrap">${renderRequestLineTable(req.items||[], req.currency)}</div>
                    <div class="olp-total-bar">
                      <div style="font-size:12px;color:var(--olp-text-3);">
                        ${(req.items||[]).length} item${(req.items||[]).length!==1?"s":""} · qty ${req.total_qty||0}
                      </div>
                      <strong>${formatMoney(req.total_amount, req.currency)}</strong>
                    </div>
                  </div>
                  ${req.linked_quotation ? `
                  <div class="olp-card" style="margin-top:16px;">
                    <div class="olp-card-head"><div class="olp-card-title">Linked Quotation</div></div>
                    <div class="olp-pad">
                      <div class="olp-inline-actions">
                        <span class="olp-badge olp-badge-purple">${escapeHtml(req.linked_quotation)}</span>
                        ${req.quotation_pdf_url ? `<a class="olp-btn olp-btn-primary" href="${escapeHtml(req.quotation_pdf_url)}" target="_blank">${iconDoc()} Download PDF</a>` : ""}
                      </div>
                    </div>
                  </div>` : ""}
                </div>
                <div>
                  <div class="olp-info-block">
                    <div class="olp-info-title">Details</div>
                    ${infoRow("Reference",    req.name           || "—")}
                    ${infoRow("Customer",     req.customer       || "—")}
                    ${infoRow("Status",       req.status         || "—")}
                    ${infoRow("Items",        String((req.items||[]).length))}
                    ${infoRow("Total",        formatMoney(req.total_amount, req.currency))}
                    ${infoRow("Currency",     req.currency       || "—")}
                  </div>
                  <div class="olp-info-block">
                    <div class="olp-info-title">Notes</div>
                    <div class="olp-pad-sm olp-info-text">${escapeHtml(req.request_notes||"No notes provided.")}</div>
                  </div>
                  ${req.review_comment ? `
                  <div class="olp-info-block">
                    <div class="olp-info-title">Review Comment</div>
                    <div class="olp-pad-sm olp-info-text">${escapeHtml(req.review_comment)}</div>
                  </div>` : ""}
                  <div class="olp-inline-actions">
                    <button class="olp-btn olp-btn-sm" data-repeat-request="${escapeHtml(req.name)}">
                      ${iconBasket()} Re-add to basket
                    </button>
                  </div>
                </div>
              </div>`);
        } catch (err) { renderError(err); }
    }

    /* ── Account ────────────────────────────────────────────── */
    function renderAccount() {
        const user    = (state.bootstrap && state.bootstrap.user)    || {};
        const policy  = (state.bootstrap && state.bootstrap.policy)  || {};
        const metrics = (state.bootstrap && state.bootstrap.metrics) || {};
        const initials = makeInitials(user.customer_name || user.email || "U");
        setView(`
          <div class="olp-account-header">
            <div class="olp-account-avatar">${escapeHtml(initials)}</div>
            <div>
              <div class="olp-section-title">${escapeHtml(user.customer_name||"Portal User")}</div>
              <div class="olp-section-sub">${escapeHtml(user.email||"")} · ${escapeHtml(user.customer_group||"")}</div>
            </div>
          </div>
          <div class="olp-grid olp-grid-2">
            <div class="olp-card">
              <div class="olp-card-head"><div class="olp-card-title">Account Information</div></div>
              <div class="olp-pad-sm">
                <div class="olp-info-block" style="margin-bottom:0;">
                  ${infoRow("Customer Name",  user.customer_name   || "—")}
                  ${infoRow("Email",          user.email           || "—")}
                  ${infoRow("Customer Group", user.customer_group  || "—")}
                </div>
              </div>
            </div>
            <div class="olp-card">
              <div class="olp-card-head"><div class="olp-card-title">Portal Access</div></div>
              <div class="olp-pad-sm">
                <div class="olp-info-block" style="margin-bottom:0;">
                  ${infoRow("Quote Requests", policy.quote_request_allowed ? "✓ Enabled" : "Disabled")}
                  ${infoRow("Currency",       policy.currency || "MAD")}
                  ${infoRow("Products",       String(metrics.visible_products || 0))}
                  ${infoRow("Requests",       String(metrics.requests_total   || 0))}
                  ${infoRow("Quotations",     String(metrics.quotations_total || 0))}
                </div>
              </div>
            </div>
          </div>`);
    }

    /* ── Basket ─────────────────────────────────────────────── */
    function renderBasket() {
        const total    = getBasketTotal();
        const currency = getBasketCurrency();
        setView(`
          <div class="olp-detail-grid">
            <div class="olp-card">
              <div class="olp-card-head">
                <div><div class="olp-card-title">Quote Basket</div><div class="olp-card-sub">${state.basket.length} line${state.basket.length!==1?"s":""}</div></div>
                <button id="olp-clear-basket" class="olp-btn olp-btn-sm olp-btn-danger" ${state.basket.length?"":"disabled"}>Clear</button>
              </div>
              <div class="olp-table-wrap">${renderBasketTable()}</div>
              ${state.basket.length ? `<div class="olp-total-bar"><span>Estimated total</span><strong>${formatMoney(total,currency)}</strong></div>` : ""}
            </div>
            <div class="olp-card olp-pad">
              <div class="olp-section-title" style="margin-bottom:6px;">Submit Request</div>
              <div class="olp-section-sub" style="margin-bottom:14px;">Include notes or delivery requirements.</div>
              <div class="olp-input-wrap" style="margin-bottom:14px;">
                <label class="olp-field-label">Notes (optional)</label>
                <textarea id="olp-request-notes" class="olp-textarea" rows="5"
                  placeholder="Project name, delivery site, special requirements…"></textarea>
              </div>
              <div class="olp-info-block" style="margin-bottom:14px;">
                ${infoRow("Lines",            String(state.basket.length))}
                ${infoRow("Total qty",        String(state.basket.reduce((s,r)=>s+(r.qty||0),0)))}
                ${infoRow("Estimated total",  formatMoney(total, currency))}
              </div>
              <button id="olp-submit-request" class="olp-btn olp-btn-primary"
                style="width:100%;justify-content:center;" ${state.basket.length?"":"disabled"}>
                ${iconDoc()} Submit Quotation Request
              </button>
              <div class="olp-helper-text" style="margin-top:10px;text-align:center;">
                Prices are validated again on submission.
              </div>
            </div>
          </div>`);
    }

    /* ── Events ─────────────────────────────────────────────── */
    function bindEvents() {
        // User menu toggle
        root.addEventListener("click", (e) => {
            const trigger = e.target.closest("#olp-user-menu-trigger");
            const menu    = document.getElementById("olp-user-menu");
            if (trigger && menu) {
                const open = menu.style.display !== "none";
                menu.style.display = open ? "none" : "block";
                trigger.classList.toggle("is-open", !open);
                return;
            }
            // Close menu when clicking outside
            if (menu && !e.target.closest("#olp-user-menu") && !e.target.closest("#olp-user-menu-trigger")) {
                menu.style.display = "none";
                const t = document.getElementById("olp-user-menu-trigger");
                if (t) t.classList.remove("is-open");
            }
        });

        root.addEventListener("click", async (e) => {

            // Stepper buttons — input by id
            const stepperBtn = e.target.closest("[data-stepper-target]");
            if (stepperBtn) {
                const dir   = Number(stepperBtn.dataset.stepperDir || 0);
                const input = document.getElementById(stepperBtn.dataset.stepperTarget);
                if (input) { input.value = Math.max(1, Number(input.value || 1) + dir); input.dispatchEvent(new Event("change")); }
                return;
            }

            // Stepper buttons — basket by index
            const stepperBasket = e.target.closest("[data-stepper-basket]");
            if (stepperBasket) {
                const idx = Number(stepperBasket.dataset.stepperBasket);
                const dir = Number(stepperBasket.dataset.stepperDir || 0);
                if (state.basket[idx]) {
                    state.basket[idx].qty = Math.max(1, (state.basket[idx].qty || 1) + dir);
                    saveBasket(); render();
                }
                return;
            }

            // Detail add button (on product detail page)
            const detailAdd = e.target.closest("#olp-detail-add-btn");
            if (detailAdd) {
                const qtyEl = document.getElementById("olp-detail-qty");
                const qty   = qtyEl ? Number(qtyEl.value || 1) : 1;
                addToBasket(detailAdd.dataset.ruleName, qty);
                return;
            }

            // ── IMPORTANT: add-to-basket BEFORE detail navigation ──
            const addBtn = e.target.closest("[data-open-add]");
            if (addBtn) { openAddModal(addBtn.dataset.openAdd); return; }

            // View toggle
            const viewBtn = e.target.closest("[data-view]");
            if (viewBtn) {
                state.catalogView = viewBtn.dataset.view;
                renderRoute(parseRoute());
                return;
            }

            // Clear search
            if (e.target.closest("[data-clear-search]")) {
                navigate("catalog"); return;
            }

            // Nav
            const nav = e.target.closest("[data-nav-page]");
            if (nav) { navigate(nav.dataset.navPage); return; }

            // Product detail navigation (card body, not buttons)
            const detail = e.target.closest("[data-detail-kind]");
            if (detail) { navigate(`${detail.dataset.detailKind}/${detail.dataset.detailCode}`); return; }

            const repeat = e.target.closest("[data-repeat-request]");
            if (repeat) { await addRequestItemsToBasket(repeat.dataset.repeatRequest); return; }

            if (e.target.id === "olp-modal-close" || e.target.closest("#olp-modal-close") || e.target.classList.contains("olp-modal-backdrop")) {
                closeModal(); return;
            }
            if (e.target.id === "olp-modal-add") {
                const qty = document.getElementById("olp-modal-qty");
                addToBasket(e.target.getAttribute("data-rule-name"), qty ? Number(qty.value||1) : 1);
                closeModal(); return;
            }

            const remove = e.target.closest("[data-remove-basket]");
            if (remove) { state.basket.splice(Number(remove.dataset.removeBasket),1); saveBasket(); render(); return; }

            if (e.target.id === "olp-apply-filters") { applyFilterNavigation(); return; }
            if (e.target.id === "olp-submit-request") { await submitRequest(); return; }
            if (e.target.id === "olp-clear-basket")   { state.basket=[]; saveBasket(); render(); return; }

            // Logout
            if (e.target.id === "olp-logout-btn" || e.target.closest("#olp-logout-btn")) {
                if (window.frappe && typeof frappe.logout === "function") { frappe.logout(); return; }
                window.location.href = "/logout";
            }
        });

        root.addEventListener("change", (e) => {
            const qty = e.target.closest("[data-basket-qty]");
            if (!qty) return;
            const idx = Number(qty.dataset.basketQty);
            if (state.basket[idx]) { state.basket[idx].qty = Math.max(1, Number(qty.value||1)); saveBasket(); render(); }
        });

        root.addEventListener("keydown", (e) => {
            if (e.target.id === "olp-global-search" && e.key === "Enter")
                navigate(`catalog?search=${encodeURIComponent(e.target.value||"")}`);
            if (e.target.id === "olp-filter-search" && e.key === "Enter")
                applyFilterNavigation();
        });

        // Debounced live search in filter bar
        root.addEventListener("input", (e) => {
            if (e.target.id !== "olp-filter-search") return;
            clearTimeout(state.searchTimer);
            state.searchTimer = setTimeout(() => applyFilterNavigation(), 400);
        });

        window.addEventListener("popstate", render);
    }

    /* ── Basket logic ───────────────────────────────────────── */
    async function addToBasket(ruleName, qty) {
        const entry = getEntry(ruleName);
        if (!entry) { toast("Catalog entry could not be added.", "error"); return; }
        const existing = state.basket.find(r => r.rule_name === ruleName);
        if (existing) existing.qty += Math.max(1, qty||1);
        else state.basket.push({ ...entry, qty: Math.max(1, qty||1) });
        saveBasket();
        toast(`Added to basket — ${formatMoney((entry.price_rate||0)*qty, entry.currency)}`, "success");
        render();
    }

    async function addRequestItemsToBasket(requestName) {
        try {
            const req     = await api("orderlift.orderlift_client_portal.api.get_request_detail", { name: requestName });
            const catalog = state.catalog.length
                ? state.catalog
                : await api("orderlift.orderlift_client_portal.api.get_catalog", { featured:0, limit:200 }).catch(()=>[]);
            state.catalog = catalog;
            indexEntries(catalog);
            for (const row of (req.items||[])) {
                const matched = catalog.find(e => e.item_code===row.item_code || e.product_bundle===row.product_bundle);
                if (!matched) continue;
                const existing = state.basket.find(e => e.rule_name===matched.rule_name);
                if (existing) existing.qty += Number(row.qty||1);
                else state.basket.push({ ...matched, qty: Number(row.qty||1) });
            }
            saveBasket();
            toast("Items re-added to basket", "success");
            navigate("request-quote");
        } catch (err) { renderError(err); }
    }

    let _submitting = false;
    async function submitRequest() {
        if (_submitting) return;
        _submitting = true;

        // Immediately disable the button and show loading state
        const btn = document.getElementById("olp-submit-request");
        if (btn) { btn.disabled = true; btn.textContent = "Submitting…"; }

        try {
            const notes   = document.getElementById("olp-request-notes");
            const payload = { request_notes: notes ? notes.value : "", items: state.basket.map(r=>({rule_name:r.rule_name,qty:r.qty})) };
            const result  = await api("orderlift.orderlift_client_portal.api.submit_quote_request", { payload: JSON.stringify(payload) });
            state.basket  = []; saveBasket();
            toast(`Request ${result.name} submitted`, "success");
            navigate(`request/${result.name}`);
        } catch (err) {
            // Re-enable on failure so the user can retry
            if (btn) { btn.disabled = false; btn.innerHTML = `${iconDoc()} Submit Quotation Request`; }
            toast(err && err.message ? err.message : "Submission failed.", "error");
        } finally {
            _submitting = false;
        }
    }

    /* ── Render helpers ─────────────────────────────────────── */
    function renderProductCards(rows) {
        if (!rows || !rows.length) {
            return `<div class="olp-empty" style="grid-column:1/-1;"><div class="olp-empty-title">No products found</div><div class="olp-empty-sub">Try adjusting your filters.</div></div>`;
        }
        indexEntries(rows);
        return rows.map(row => `
          <div class="olp-product-card">
            <div class="olp-product-image-wrap"
                 data-detail-kind="${escapeHtml(row.kind||"item")}" data-detail-code="${escapeHtml(row.code||"")}">
              ${row.image
                  ? `<img src="${escapeHtml(row.image)}" alt="${escapeHtml(row.title||"")}" loading="lazy">`
                  : `<div class="olp-product-placeholder">${iconBox()}<span>${escapeHtml(row.brand||row.kind||"ITEM")}</span></div>`}
              <div class="olp-product-badges">
                ${row.featured    ? `<span class="olp-badge olp-badge-orange">★</span>` : ""}
                ${row.kind==="bundle" ? `<span class="olp-badge olp-badge-purple">Bundle</span>` : ""}
              </div>
              <div class="olp-product-overlay">
                <button class="olp-btn olp-btn-white olp-btn-sm" data-open-add="${escapeHtml(row.rule_name)}">
                  + Add to basket
                </button>
              </div>
            </div>
            <div class="olp-product-body"
                 data-detail-kind="${escapeHtml(row.kind||"item")}" data-detail-code="${escapeHtml(row.code||"")}">
              <div class="olp-product-name">${escapeHtml(row.title||row.code)}</div>
              <div class="olp-product-code">${escapeHtml(row.code||"")}${row.brand?` · ${escapeHtml(row.brand)}`:""}</div>
              <div class="olp-product-price-mini">${formatMoney(row.price_rate, row.currency)}</div>
              <div class="olp-product-footer">
                <span class="olp-tag">${escapeHtml(row.item_group||row.kind||"")}</span>
                <button class="olp-btn olp-btn-primary olp-btn-xs" data-open-add="${escapeHtml(row.rule_name)}">+ Add</button>
              </div>
            </div>
          </div>`).join("");
    }

    function renderRequestTable(rows) {
        if (!rows.length) return `<div class="olp-empty"><div class="olp-empty-title">No requests yet</div><div class="olp-empty-sub">Browse the catalog and add items to your quote basket.</div></div>`;
        return `<table class="olp-table">
          <thead><tr><th>Reference</th><th>Status</th><th>Submitted</th><th>Qty</th><th>Total</th><th>Actions</th></tr></thead>
          <tbody>${rows.map(row=>`
            <tr>
              <td><div class="olp-table-title">${escapeHtml(row.name)}</div></td>
              <td><span class="olp-status ${statusClass(row.status)}">${escapeHtml(row.status||"")}</span></td>
              <td style="color:var(--olp-text-3);font-size:12px;">${escapeHtml(fmtDate(row.submitted_on||row.modified||""))}</td>
              <td style="color:var(--olp-text-2);">${row.total_qty||"—"}</td>
              <td style="font-weight:600;">${formatMoney(row.total_amount,row.currency)}</td>
              <td><div class="olp-table-actions">
                <button class="olp-btn olp-btn-sm" data-nav-page="request/${escapeHtml(row.name)}">View</button>
                <button class="olp-btn olp-btn-sm olp-btn-ghost" data-repeat-request="${escapeHtml(row.name)}">Re-add</button>
              </div></td>
            </tr>`).join("")}
          </tbody></table>`;
    }

    function renderQuotationTable(rows) {
        if (!rows.length) return `<div class="olp-empty"><div class="olp-empty-title">No quotations yet</div><div class="olp-empty-sub">Quotations appear once requests are processed.</div></div>`;
        return `<table class="olp-table">
          <thead><tr><th>Quotation</th><th>Status</th><th>Date</th><th>Valid Until</th><th>Total</th><th>Actions</th></tr></thead>
          <tbody>${rows.map(row=>`
            <tr>
              <td><div class="olp-table-title">${escapeHtml(row.quotation||"")}</div></td>
              <td><span class="olp-status ${statusClass(row.status)}">${escapeHtml(row.status||"")}</span></td>
              <td style="color:var(--olp-text-3);font-size:12px;">${escapeHtml(fmtDate(String(row.transaction_date||"")))}</td>
              <td style="color:var(--olp-text-3);font-size:12px;">${escapeHtml(String(row.valid_till||"—"))}</td>
              <td style="font-weight:600;">${formatMoney(row.grand_total,row.currency)}</td>
              <td><div class="olp-table-actions">
                <button class="olp-btn olp-btn-sm" data-nav-page="request/${escapeHtml(row.request_name)}">Request</button>
                ${row.pdf_url?`<a class="olp-btn olp-btn-primary olp-btn-sm" href="${escapeHtml(row.pdf_url)}" target="_blank">${iconDoc()} PDF</a>`:""}
                <button class="olp-btn olp-btn-sm olp-btn-ghost" data-repeat-request="${escapeHtml(row.request_name)}">Re-add</button>
              </div></td>
            </tr>`).join("")}
          </tbody></table>`;
    }

    function renderRequestLineTable(rows, currency) {
        if (!rows.length) return `<div class="olp-empty">No items.</div>`;
        return `<table class="olp-table">
          <thead><tr><th>Product</th><th>Type</th><th>Brand</th><th>Qty</th><th>Unit Price</th><th>Total</th></tr></thead>
          <tbody>${rows.map(row=>`
            <tr>
              <td>
                <div class="olp-table-title">${escapeHtml(row.item_name||row.item_code||"")}</div>
                <div class="olp-table-sub">${escapeHtml(row.item_code||"")}</div>
              </td>
              <td><span class="olp-badge olp-badge-blue" style="font-size:10px;">${escapeHtml(row.item_type||"Item")}</span></td>
              <td style="color:var(--olp-text-2);font-size:12px;">${escapeHtml(row.brand||"—")}</td>
              <td style="font-weight:600;">${row.qty} <span style="color:var(--olp-text-3);font-size:11px;">${escapeHtml(row.uom||"")}</span></td>
              <td>${formatMoney(row.unit_price, currency)}</td>
              <td style="font-weight:600;">${formatMoney(row.line_total, currency)}</td>
            </tr>`).join("")}
          </tbody></table>`;
    }

    function renderBasketTable() {
        if (!state.basket.length) return `<div class="olp-empty">
          <div class="olp-empty-title">Basket is empty</div>
          <div class="olp-empty-sub"><button class="olp-btn olp-btn-primary olp-btn-sm" data-nav-page="catalog">Browse catalog</button></div>
        </div>`;
        return `<table class="olp-table">
          <thead><tr><th>Product</th><th>Qty</th><th>Unit Price</th><th>Line Total</th><th></th></tr></thead>
          <tbody>${state.basket.map((row,idx)=>`
            <tr>
              <td>
                <div class="olp-table-title">${escapeHtml(row.title||row.code)}</div>
                <div class="olp-table-sub">${escapeHtml(row.code||"")}${row.brand?` · ${escapeHtml(row.brand)}`:""}</div>
              </td>
              <td style="width:110px;">
                <div class="olp-qty-stepper olp-qty-stepper-sm">
                  <button class="olp-qty-stepper-btn" data-stepper-basket="${idx}" data-stepper-dir="-1">−</button>
                  <input class="olp-qty-stepper-input" type="number" min="1" value="${row.qty||1}" data-basket-qty="${idx}" style="width:42px;">
                  <button class="olp-qty-stepper-btn" data-stepper-basket="${idx}" data-stepper-dir="1">+</button>
                </div>
              </td>
              <td>${formatMoney(row.price_rate||0, row.currency)}</td>
              <td style="font-weight:600;">${formatMoney((row.price_rate||0)*(row.qty||0), row.currency)}</td>
              <td><button class="olp-btn olp-btn-xs olp-btn-danger" data-remove-basket="${idx}">×</button></td>
            </tr>`).join("")}
          </tbody></table>`;
    }

    function renderBundleChildren(rows) {
        if (!rows.length) return "";
        return `
          <div class="olp-divider"></div>
          <div class="olp-card-title" style="margin-bottom:10px;">Bundle Components</div>
          <div class="olp-table-wrap">
            <table class="olp-table">
              <thead><tr><th>Item</th><th>Brand</th><th>Qty</th><th>UOM</th></tr></thead>
              <tbody>${rows.map(r=>`
                <tr>
                  <td>${escapeHtml(r.item_code||"")}</td>
                  <td style="color:var(--olp-text-3);">${escapeHtml(r.brand||"—")}</td>
                  <td>${r.qty}</td>
                  <td>${escapeHtml(r.uom||"")}</td>
                </tr>`).join("")}
              </tbody>
            </table>
          </div>`;
    }

    /* ── Modal ──────────────────────────────────────────────── */
    function openAddModal(ruleName) {
        const entry = getEntry(ruleName);
        if (!entry) { toast("Catalog entry not found.", "error"); return; }
        const modal = document.getElementById("olp-modal-root");
        modal.innerHTML = `
          <div class="olp-modal-backdrop">
            <div class="olp-modal-card">
              <div class="olp-card-head">
                <div>
                  <div class="olp-card-title">Add to Quote Basket</div>
                  <div class="olp-card-sub">${escapeHtml(entry.code||"")}${entry.brand?` · ${escapeHtml(entry.brand)}`:""}</div>
                </div>
                <button id="olp-modal-close" class="olp-modal-close">&times;</button>
              </div>
              <div class="olp-pad">
                <div style="display:flex;gap:12px;margin-bottom:16px;">
                  ${entry.image ? `<img src="${escapeHtml(entry.image)}" style="width:72px;height:72px;border-radius:10px;object-fit:cover;flex-shrink:0;">` : ""}
                  <div>
                    <div class="olp-section-title" style="font-size:15px;">${escapeHtml(entry.title||entry.code)}</div>
                    <div class="olp-detail-price" style="margin-top:4px;font-size:18px;">${formatMoney(entry.price_rate, entry.currency)}</div>
                    ${entry.description ? `<div style="font-size:12px;color:var(--olp-text-3);margin-top:4px;">${escapeHtml((entry.description||"").substring(0,120))}${(entry.description||"").length>120?"…":""}</div>` : ""}
                  </div>
                </div>
                <div class="olp-info-grid" style="margin-bottom:16px;">
                  ${infoStat("UOM",      entry.uom      || "—")}
                  ${infoStat("Material", entry.material || "—")}
                  ${infoStat("Weight",   entry.weight_kg ? `${Number(entry.weight_kg).toFixed(2)} kg` : "—")}
                </div>
                <div class="olp-input-wrap" style="margin-bottom:18px;">
                  <label class="olp-field-label">Quantity</label>
                  <div class="olp-qty-stepper">
                    <button class="olp-qty-stepper-btn" data-stepper-target="olp-modal-qty" data-stepper-dir="-1">−</button>
                    <input id="olp-modal-qty" class="olp-qty-stepper-input" type="number" min="1" value="1">
                    <button class="olp-qty-stepper-btn" data-stepper-target="olp-modal-qty" data-stepper-dir="1">+</button>
                  </div>
                </div>
                <div class="olp-inline-actions" style="justify-content:flex-end;">
                  <button class="olp-btn" id="olp-modal-close">Cancel</button>
                  <button class="olp-btn olp-btn-primary" id="olp-modal-add" data-rule-name="${escapeHtml(ruleName)}">
                    ${iconBasket()} Add to basket
                  </button>
                </div>
              </div>
            </div>
          </div>`;
    }

    function closeModal() {
        const m = document.getElementById("olp-modal-root");
        if (m) m.innerHTML = "";
    }

    /* ── Guest ──────────────────────────────────────────────── */
    function renderGuest() {
        root.innerHTML = `
          <div class="olp-shell" style="display:flex;align-items:center;justify-content:center;min-height:100vh;">
            <div class="olp-auth-box">
              <div class="olp-auth-icon">${iconBuildingStore()}</div>
              <div class="olp-auth-title">Orderlift B2B Portal</div>
              <div class="olp-auth-sub">
                Portal access is available only for invited B2B customers.
                Please sign in with your invited account.
              </div>
              <a class="olp-btn olp-btn-primary olp-link-btn" href="${escapeHtml(loginUrl)}"
                 style="width:100%;justify-content:center;">Sign in to your account</a>
            </div>
          </div>`;
    }

    function renderError(err) {
        setView(`<div class="olp-card olp-pad"><div class="olp-empty">
          <div class="olp-empty-title">Something went wrong</div>
          <div class="olp-empty-sub">${escapeHtml(err&&err.message?err.message:"Portal data could not be loaded.")}</div>
        </div></div>`);
    }

    /* ── Toast ──────────────────────────────────────────────── */
    function toast(message, type) {
        // Try frappe first
        if (window.frappe && typeof frappe.show_alert === "function") {
            frappe.show_alert({ message, indicator: type === "error" ? "red" : "green" }); return;
        }
        const r = document.getElementById("olp-toast-root");
        if (!r) return;
        const el = document.createElement("div");
        el.className = `olp-toast olp-toast-${type||"info"}`;
        el.textContent = message;
        r.appendChild(el);
        setTimeout(() => el.classList.add("olp-toast-in"), 10);
        setTimeout(() => { el.classList.remove("olp-toast-in"); setTimeout(() => el.remove(), 300); }, 3000);
    }

    /* ── Router ─────────────────────────────────────────────── */
    function parseRoute() {
        const path   = window.location.pathname.replace(/^\/b2b-portal\/?/, "");
        const [page] = path.split("?");
        const segs   = page.split("/").filter(Boolean);
        const params = new URLSearchParams(window.location.search);
        if (!segs.length) return { page:"dashboard", search: params.get("search")||"" };
        if (segs[0]==="catalog") return { page:"catalog", search:params.get("search")||"", kind:params.get("kind")||"", brand:params.get("brand")||"", group:params.get("group")||"", sort:params.get("sort")||"sort" };
        if (segs[0]==="request-quote") return { page:"request-quote" };
        if (segs[0]==="requests")      return { page:"requests" };
        if (segs[0]==="quotations")    return { page:"quotations" };
        if (segs[0]==="request" && segs[1]) return { page:"request", param:decodeURIComponent(segs[1]) };
        if ((segs[0]==="item"||segs[0]==="bundle") && segs[1]) return { page:segs[0], param:decodeURIComponent(segs[1]) };
        if (segs[0]==="account") return { page:"account" };
        return { page:"dashboard", search:params.get("search")||"" };
    }

    function navigate(target) {
        const url = target.startsWith("/") ? target : `/b2b-portal/${target}`;
        window.history.pushState({}, "", url);
        render();
    }

    function setView(html) {
        const el = document.getElementById("olp-main");
        if (el) el.innerHTML = html;
    }

    function applyFilterNavigation() {
        const p = new URLSearchParams();
        const g = id => { const el=document.getElementById(id); return el?el.value:""; };
        if (g("olp-filter-search")) p.set("search", g("olp-filter-search"));
        if (g("olp-filter-kind"))   p.set("kind",   g("olp-filter-kind"));
        if (g("olp-filter-brand"))  p.set("brand",  g("olp-filter-brand"));
        if (g("olp-filter-group"))  p.set("group",  g("olp-filter-group"));
        if (g("olp-filter-sort"))   p.set("sort",   g("olp-filter-sort"));
        navigate(`catalog${p.toString()?`?${p.toString()}`:""}`);
    }

    /* ── Catalog helpers ────────────────────────────────────── */
    function indexEntries(rows) { (rows||[]).forEach(r => { if (r&&r.rule_name) state.entryIndex[r.rule_name]=r; }); }
    function getEntry(ruleName) {
        if (state.entryIndex[ruleName]) return state.entryIndex[ruleName];
        const flat = state.catalog.find(r => r.rule_name===ruleName);
        if (flat) state.entryIndex[ruleName]=flat;
        return flat||null;
    }
    function uniqueSorted(values) { return [...new Set(values)].sort((a,b)=>String(a).localeCompare(String(b))); }
    function applyCatalogFilters(rows, route) {
        const out = [...(rows||[])].filter(row => {
            if (route.kind  && row.kind      !==route.kind)  return false;
            if (route.brand && row.brand     !==route.brand) return false;
            if (route.group && row.item_group!==route.group) return false;
            return true;
        });
        if      (route.sort==="price_asc")  out.sort((a,b)=>Number(a.price_rate||0)-Number(b.price_rate||0));
        else if (route.sort==="price_desc") out.sort((a,b)=>Number(b.price_rate||0)-Number(a.price_rate||0));
        else if (route.sort==="name")       out.sort((a,b)=>String(a.title||a.code||"").localeCompare(String(b.title||b.code||"")));
        return out;
    }

    /* ── Basket helpers ─────────────────────────────────────── */
    function getBasketTotal()    { return state.basket.reduce((acc,r)=>acc+((r.price_rate||0)*(r.qty||0)),0); }
    function getBasketCurrency() { return (state.basket[0]&&state.basket[0].currency)||(state.bootstrap&&state.bootstrap.policy&&state.bootstrap.policy.currency)||"MAD"; }
    function loadBasket() { try { return JSON.parse(window.localStorage.getItem("orderlift_b2b_basket")||"[]"); } catch(e){return[];} }
    function saveBasket() { window.localStorage.setItem("orderlift_b2b_basket", JSON.stringify(state.basket)); }

    /* ── API ────────────────────────────────────────────────── */
    async function api(method, args) {
        if (window.frappe && typeof frappe.call === "function") {
            const res = await frappe.call({ method, args: args||{} });
            return res.message;
        }
        const response = await fetch(`/api/method/${method}`, {
            method:"POST", credentials:"same-origin",
            headers:{ "Content-Type":"application/json", "X-Frappe-CSRF-Token": window.csrf_token||"" },
            body: JSON.stringify(args||{}),
        });
        const payload = await response.json();
        if (!response.ok || payload.exc_type)
            throw new Error((payload._server_messages && JSON.parse(payload._server_messages)[0]) || payload.message || "Request failed");
        return payload.message;
    }

    /* ── Utilities ──────────────────────────────────────────── */
    function pageTitle(page) {
        return ({dashboard:"Dashboard",catalog:"Catalog","request-quote":"Quote Basket",requests:"My Requests",quotations:"My Quotations",request:"Request Detail",item:"Product Detail",bundle:"Bundle Detail",account:"My Account"})[page]||"B2B Portal";
    }
    function makeInitials(s) { return ((s||"U").match(/\b\w/g)||[]).slice(0,2).join("").toUpperCase()||"U"; }
    function navBtn(target, label, current, icon, badge) {
        return `<button class="olp-nav-item ${current===target?"is-active":""}" data-nav-page="${escapeHtml(target)}">
          <span class="olp-nav-icon">${icon}</span><span class="olp-nav-label">${escapeHtml(label)}</span>
          ${badge?`<span class="olp-nav-badge">${badge}</span>`:""}
        </button>`;
    }
    function kpiCard(label, value, sub, color, icon) {
        return `<div class="olp-kpi">
          <div class="olp-kpi-header">
            <div class="olp-kpi-label">${escapeHtml(label)}</div>
            <div class="olp-kpi-icon olp-kpi-icon-${color}">${icon}</div>
          </div>
          <div class="olp-kpi-value">${escapeHtml(String(value))}</div>
          <div class="olp-kpi-sub">${escapeHtml(sub)}</div>
        </div>`;
    }
    function infoStat(label, value) { return `<div class="olp-stat-chip"><span>${escapeHtml(label)}</span><strong>${escapeHtml(String(value))}</strong></div>`; }
    function infoRow(label, value)  { return `<div class="olp-info-row"><span>${escapeHtml(label)}</span><strong>${escapeHtml(String(value))}</strong></div>`; }
    function statusClass(s)       { return `olp-status-${String(s||"draft").toLowerCase().replace(/\s+/g,"-")}`; }
    function statusDotColor(s) {
        const v = String(s||"").toLowerCase();
        if (v.includes("approved")||v.includes("quotation")) return "green";
        if (v.includes("submitted")||v.includes("review"))   return "blue";
        if (v.includes("rejected"))                          return "red";
        return "orange";
    }
    function formatMoney(value, currency) {
        return `${currency||"MAD"} ${Number(value||0).toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2})}`;
    }
    function fmtDate(str) {
        if (!str) return "";
        try { const d=new Date(str); if(isNaN(d))return str; return d.toLocaleDateString("en-US",{month:"short",day:"numeric",year:"numeric"}); } catch(e){return str;}
    }
    function escapeHtml(v) {
        return String(v==null?"":v).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
    }
    function id(s) { return document.getElementById(s); }

    /* ── Icons ──────────────────────────────────────────────── */
    function iconGrid()  { return `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><rect x="1" y="1" width="6" height="6" rx="1.5"/><rect x="9" y="1" width="6" height="6" rx="1.5"/><rect x="1" y="9" width="6" height="6" rx="1.5"/><rect x="9" y="9" width="6" height="6" rx="1.5"/></svg>`; }
    function iconList()  { return `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M2 4h12M2 8h8M2 12h10"/></svg>`; }
    function iconBasket(){ return `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M4 6L6 2h4l2 4"/><path d="M1 6h14l-1.5 7H2.5z"/></svg>`; }
    function iconDoc()   { return `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M3 2h10a1 1 0 011 1v10a1 1 0 01-1 1H3a1 1 0 01-1-1V3a1 1 0 011-1z"/><path d="M5 6h6M5 9h4"/></svg>`; }
    function iconQuote() { return `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M3 2h10a1 1 0 011 1v10a1 1 0 01-1 1H3a1 1 0 01-1-1V3a1 1 0 011-1z"/><path d="M5 5h6M5 8h6M5 11h3"/></svg>`; }
    function iconUser()  { return `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><circle cx="8" cy="5" r="3"/><path d="M2 14c0-3.3 2.7-6 6-6s6 2.7 6 6"/></svg>`; }
    function iconSearch(){ return `<svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="6.5" cy="6.5" r="4.5"/><path d="M10.5 10.5L14 14"/></svg>`; }
    function iconBack()  { return `<svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M10 4L6 8l4 4"/></svg>`; }
    function iconBox()   { return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>`; }
    function iconBuildingStore(){ return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 9l1-5h16l1 5"/><path d="M3 9a3 3 0 006 0m0 0a3 3 0 006 0m0 0a3 3 0 006 0"/><path d="M5 9v11h14V9"/><path d="M9 14h6v6H9z"/></svg>`; }
    function iconGridSmall() { return `<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="1" y="1" width="6" height="6" rx="1"/><rect x="9" y="1" width="6" height="6" rx="1"/><rect x="1" y="9" width="6" height="6" rx="1"/><rect x="9" y="9" width="6" height="6" rx="1"/></svg>`; }
    function iconListSmall() { return `<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 4h10M3 8h10M3 12h10"/></svg>`; }
    function iconChevron()   { return `<svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 6l4 4 4-4"/></svg>`; }
    function iconKey()       { return `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><circle cx="6" cy="6" r="3.5"/><path d="M8.5 8.5L14 14M11 12l1.5 1.5M13 11l1.5 1.5"/></svg>`; }
    function iconLogout()    { return `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M6 2H3a1 1 0 00-1 1v10a1 1 0 001 1h3"/><path d="M11 11l3-3-3-3"/><path d="M14 8H6"/></svg>`; }

})();
