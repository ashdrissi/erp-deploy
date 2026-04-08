frappe.pages["portal-review-board"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Portal Review Board"),
        single_column: true,
    });
    page.main.addClass("prb-root");
    injectStyles();
    renderSkeleton(page);
    loadBoard(page);
};

async function loadBoard(page) {
    try {
        const r = await frappe.call({ method: "orderlift.orderlift_client_portal.page.portal_review_board.portal_review_board.get_board_data" });
        renderQueue(page, r.message?.queue || []);
    } catch (e) {
        page.main.find("#prb-queue").html(`<div class="prb-empty">${__("Portal review data could not be loaded.")}</div>`);
    }
}

function renderSkeleton(page) {
    page.main.html(`
      <div class="prb-wrapper">
        <div class="prb-hero">
          <div>
            <div class="prb-eyebrow">${__("Orderlift · Portal Review")}</div>
            <div class="prb-title">${__("Quotation Request Review Board")}</div>
            <div class="prb-sub">${__("Review, approve, reject, and convert B2B portal requests into official quotations.")}</div>
          </div>
        </div>
        <div class="prb-card"><div class="prb-body"><div class="prb-filters"><input id="prb-search" class="form-control" placeholder="${__("Search request, customer, group, or user")}"><select id="prb-status" class="form-control"><option value="">${__("All Statuses")}</option><option value="Submitted">${__("Submitted")}</option><option value="Under Review">${__("Under Review")}</option><option value="Approved">${__("Approved")}</option></select><button id="prb-apply-filters" class="btn btn-default">${__("Apply")}</button></div></div></div>
        <div class="prb-card"><div class="prb-body"><div class="prb-filters"><input id="prb-search" class="form-control" placeholder="${__("Search request, customer, group, or user")}"><select id="prb-status" class="form-control"><option value="">${__("All Statuses")}</option><option value="Submitted">${__("Submitted")}</option><option value="Under Review">${__("Under Review")}</option><option value="Approved">${__("Approved")}</option></select><button id="prb-apply-filters" class="btn btn-default">${__("Apply")}</button></div></div></div>
        <div class="prb-card"><div class="prb-head"><div class="prb-head-title">${__("Requests Awaiting Action")}</div></div><div id="prb-queue" class="prb-body"><div class="prb-empty">${__("Loading...")}</div></div></div>
        <div id="prb-modal"></div>
      </div>
    `);

    page.main.on("click", async (event) => {
        const row = event.target.closest("[data-open-request]");
        if (row) {
            await openRequest(row.getAttribute("data-open-request"));
            return;
        }
        const actionBtn = event.target.closest("[data-review-action]");
        if (actionBtn) {
            await submitAction(actionBtn.getAttribute("data-review-action"), actionBtn.getAttribute("data-request-name"));
            return;
        }
        if (event.target.id === "prb-apply-filters") {
            await loadBoard(cur_page.page);
            return;
        }
        if (event.target.id === "prb-close" || event.target.classList.contains("prb-modal-backdrop")) {
            closeModal();
        }
    });
}

function renderQueue(page, rows) {
    const search = (page.main.find("#prb-search").val() || "").toLowerCase().trim();
    const status = page.main.find("#prb-status").val() || "";
    rows = rows.filter((row) => {
        if (status && row.status !== status) return false;
        if (!search) return true;
        const haystack = [row.name, row.customer, row.customer_group, row.portal_user, row.status].filter(Boolean).join(" ").toLowerCase();
        return haystack.includes(search);
    });
    if (!rows.length) {
        page.main.find("#prb-queue").html(`<div class="prb-empty">${__("No portal requests need action right now.")}</div>`);
        return;
    }
    page.main.find("#prb-queue").html(rows.map((row) => `
      <div class="prb-row">
        <div>
          <div class="prb-row-title">${frappe.utils.escape_html(row.name)}</div>
          <div class="prb-row-sub">${frappe.utils.escape_html(row.customer || "")} · ${frappe.utils.escape_html(row.customer_group || "")} · ${frappe.utils.escape_html(row.status || "")}</div>
        </div>
        <div class="prb-row-amount">${frappe.format(row.total_amount || 0, {fieldtype:'Currency'}, {only_value:true})}</div>
        <div class="prb-actions">${row.linked_quotation ? `<a class="btn btn-default btn-sm" href="/app/quotation/${frappe.utils.escape_html(row.linked_quotation)}">${__("Quotation")}</a>` : ""}<button class="btn btn-default btn-sm" data-open-request="${frappe.utils.escape_html(row.name)}">${__("Review")}</button></div>
      </div>
    `).join(""));
}

async function openRequest(name) {
    const r = await frappe.call({ method: "orderlift.orderlift_client_portal.page.portal_review_board.portal_review_board.get_request", args: { name } });
    const req = r.message || {};
    const modal = document.getElementById("prb-modal");
    modal.innerHTML = `
      <div class="prb-modal-backdrop">
        <div class="prb-modal-card">
          <div class="prb-head"><div class="prb-head-title">${frappe.utils.escape_html(req.name || "")}</div><button id="prb-close" class="prb-close">&times;</button></div>
          <div class="prb-body">
            <div class="prb-summary">${frappe.utils.escape_html(req.customer || "")} · ${frappe.utils.escape_html(req.customer_group || "")} · ${frappe.utils.escape_html(req.status || "")}</div>
            <div class="prb-lines">${(req.items || []).map((row) => `<div class="prb-line"><strong>${frappe.utils.escape_html(row.item_name || row.item_code || "")}</strong><span>${row.qty} × ${frappe.format(row.unit_price || 0, {fieldtype:'Currency'}, {only_value:true})}</span><em>${frappe.format(row.line_total || 0, {fieldtype:'Currency'}, {only_value:true})}</em></div>`).join("")}</div>
            <textarea id="prb-comment" class="form-control" rows="4" placeholder="${__("Review comment")}">${frappe.utils.escape_html(req.review_comment || req.request_notes || "")}</textarea>
            <div class="prb-inline-actions">
              <button class="btn btn-default" data-review-action="reject" data-request-name="${frappe.utils.escape_html(req.name || "")}">${__("Reject")}</button>
              <button class="btn btn-default" data-review-action="approve" data-request-name="${frappe.utils.escape_html(req.name || "")}">${__("Approve")}</button>
              <button class="btn btn-primary" data-review-action="create_quotation" data-request-name="${frappe.utils.escape_html(req.name || "")}">${__("Create Quotation")}</button>
            </div>
          </div>
        </div>
      </div>
    `;
}

async function submitAction(action, name) {
    const review_comment = document.getElementById("prb-comment")?.value || "";
    const r = await frappe.call({
        method: "orderlift.client_portal.api.review_request_action",
        args: { name, action, review_comment },
    });
    frappe.show_alert({ message: __("Request updated"), indicator: "green" });
    closeModal();
    await loadBoard(cur_page.page);
    return r.message;
}

function closeModal() {
    const modal = document.getElementById("prb-modal");
    if (modal) modal.innerHTML = "";
}

function injectStyles() {
    if (document.getElementById("prb-styles")) return;
    const style = document.createElement("style");
    style.id = "prb-styles";
    style.textContent = `
      .prb-root { background: linear-gradient(180deg,#f8fafc 0%,#ede9fe 100%); min-height: calc(100vh - 88px); }
      .prb-wrapper { max-width: 1240px; margin:0 auto; padding:24px; }
      .prb-hero,.prb-card,.prb-row,.prb-modal-card { background: rgba(255,255,255,.92); border:1px solid rgba(148,163,184,.16); box-shadow:0 18px 50px rgba(15,23,42,.08); }
      .prb-hero,.prb-card { border-radius: 22px; }
      .prb-hero { padding:26px; margin-bottom:18px; }
      .prb-eyebrow { font-size:12px; text-transform:uppercase; letter-spacing:.12em; color:#64748b; margin-bottom:8px; }
      .prb-title { font-size:30px; font-weight:700; }
      .prb-sub { margin-top:8px; color:#475569; }
      .prb-head { padding:18px 20px 12px; display:flex; justify-content:space-between; align-items:center; }
      .prb-head-title { font-weight:700; font-size:18px; }
      .prb-body { padding:0 18px 18px; }
      .prb-filters { display:grid; grid-template-columns:minmax(0,1.4fr) 220px 120px; gap:12px; padding-top:18px; }
      .prb-row { display:grid; grid-template-columns:minmax(0,1.6fr) 140px 120px; gap:14px; align-items:center; border-radius:14px; padding:14px; margin-bottom:10px; }
      .prb-row-title { font-weight:700; }
      .prb-row-sub { margin-top:4px; color:#64748b; font-size:12px; }
      .prb-row-amount { font-weight:700; text-align:right; }
      .prb-actions { text-align:right; }
      .prb-empty { padding:24px 8px; text-align:center; color:#64748b; }
      .prb-modal-backdrop { position:fixed; inset:0; background:rgba(15,23,42,.52); display:flex; align-items:center; justify-content:center; padding:18px; z-index:1000; }
      .prb-modal-card { width:min(760px,100%); border-radius:22px; overflow:hidden; }
      .prb-close { border:0; background:transparent; font-size:28px; cursor:pointer; color:#64748b; }
      .prb-summary { margin-bottom:12px; color:#475569; }
      .prb-lines { display:grid; gap:10px; margin-bottom:14px; }
      .prb-line { display:grid; grid-template-columns:minmax(0,1.6fr) 140px 120px; gap:12px; padding:12px; border-radius:12px; background:#f8fafc; }
      .prb-line span,.prb-line em { color:#475569; font-style:normal; text-align:right; }
      .prb-inline-actions { display:flex; justify-content:flex-end; gap:10px; margin-top:14px; }
      @media (max-width: 980px) { .prb-filters,.prb-row,.prb-line { grid-template-columns:1fr; } .prb-row-amount,.prb-actions,.prb-line span,.prb-line em { text-align:left; } }
    `;
    document.head.appendChild(style);
}
