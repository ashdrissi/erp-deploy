(function () {
    const STYLE_ID = "ol-cp-form-style-20260411c";

    if (!document.getElementById(STYLE_ID)) {
        const style = document.createElement("style");
        style.id = STYLE_ID;
        style.textContent = `
            .ol-cp-shell {
                display:flex; flex-direction:column; gap:18px; margin-bottom:18px;
            }
            .ol-cp-head {
                display:flex; justify-content:space-between; align-items:flex-start; gap:16px; flex-wrap:wrap;
                background:linear-gradient(135deg,#fff8f1 0%,#ffffff 58%);
                border:1px solid #f3e3d0; border-radius:18px; padding:22px 24px;
                box-shadow:0 1px 4px rgba(15,23,42,.04), 0 10px 22px rgba(15,23,42,.04);
            }
            .ol-cp-head__eyebrow { font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:.08em; color:#9b8f82; }
            .ol-cp-head__title { font-size:24px; font-weight:800; color:#0f172a; line-height:1.1; margin-top:6px; }
            .ol-cp-head__sub { font-size:13px; color:#6b7280; margin-top:6px; max-width:68ch; }
            .ol-cp-head__meta { display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }
            .ol-cp-pill {
                display:inline-flex; align-items:center; gap:6px; padding:5px 10px; border-radius:999px;
                background:#fff; border:1px solid #e6ddd3; color:#6b6259; font-size:11px; font-weight:700;
            }
            .ol-cp-pill--active { background:#f0fdf4; border-color:#bbf7d0; color:#15803d; }
            .ol-cp-pill--inactive { background:#f8fafc; border-color:#e2e8f0; color:#64748b; }
            .ol-cp-stats { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; width:min(560px,100%); }
            .ol-cp-stat { background:#fff; border:1px solid #f1f5f9; border-radius:14px; padding:14px; }
            .ol-cp-stat__label { font-size:10px; font-weight:800; text-transform:uppercase; letter-spacing:.08em; color:#94a3b8; }
            .ol-cp-stat__value { margin-top:6px; font-size:22px; font-weight:900; color:#0f172a; line-height:1; }
            .ol-cp-stat__sub { margin-top:4px; font-size:11px; color:#94a3b8; }

            .ol-cp-form {
                display:grid; grid-template-columns:minmax(0,1.4fr) minmax(280px,.9fr); gap:18px;
            }
            .ol-cp-form-main, .ol-cp-form-side { display:flex; flex-direction:column; gap:18px; }
            .ol-cp-form-side { position:sticky; top:12px; }
            .ol-cp-card {
                background:#fff; border:1px solid #e8e0d5; border-radius:16px; padding:18px 20px;
                box-shadow:0 1px 3px rgba(15,23,42,.04),0 10px 22px rgba(15,23,42,.04);
            }
            .ol-cp-card__title { font-size:16px; font-weight:800; color:#0f172a; }
            .ol-cp-card__sub { font-size:12px; color:#9b8f82; margin-top:4px; line-height:1.55; }
            .ol-cp-card__head { margin-bottom:16px; }
            .ol-cp-grid {
                display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px 16px;
            }
            .ol-cp-grid > [data-fieldname],
            .ol-cp-notes > [data-fieldname] {
                background:#faf8f5; border:1px solid #efe7dc; border-radius:12px; padding:12px 14px; margin:0;
            }
            .ol-cp-notes textarea { min-height:140px; }
            .ol-cp-notes > [data-fieldname] .control-label { display:block; }
            .ol-cp-shell [data-fieldname] .control-label {
                font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:.05em; color:#9b8f82; margin-bottom:6px;
            }
            .ol-cp-shell input,
            .ol-cp-shell select,
            .ol-cp-shell textarea,
            .ol-cp-shell .awesomplete input {
                border-radius:10px !important; background:#fff !important;
            }
            .ol-cp-capacity { display:flex; flex-direction:column; gap:10px; }
            .ol-cp-capacity-row { background:#faf8f5; border:1px solid #efe7dc; border-radius:12px; padding:12px 14px; }
            .ol-cp-capacity-head { display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:8px; }
            .ol-cp-capacity-label { font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:.05em; color:#7c7168; }
            .ol-cp-capacity-value { font-size:12px; font-weight:700; color:#0f172a; }
            .ol-cp-bar { height:8px; background:#f0ebe3; border-radius:999px; overflow:hidden; }
            .ol-cp-bar > span { display:block; height:100%; border-radius:999px; }
            .ol-cp-bar--weight > span { background:linear-gradient(90deg,#3b82f6,#2563eb); }
            .ol-cp-bar--volume > span { background:linear-gradient(90deg,#8b5cf6,#6366f1); }
            .ol-cp-bar--density > span { background:linear-gradient(90deg,#ec4899,#db2777); }
            .ol-cp-zones { display:flex; flex-wrap:wrap; gap:8px; }
            .ol-cp-zone-pill {
                display:inline-flex; align-items:center; padding:5px 10px; border-radius:999px;
                background:#fff7ed; color:#c2410c; border:1px solid #fed7aa; font-size:11px; font-weight:700;
            }
            .ol-cp-zone-empty { font-size:12px; color:#94a3b8; font-style:italic; }
            .ol-cp-side-list { display:flex; flex-direction:column; gap:10px; }
            .ol-cp-side-item { background:#faf8f5; border:1px solid #efe7dc; border-radius:12px; padding:12px 14px; }
            .ol-cp-side-item__label { font-size:10px; font-weight:800; text-transform:uppercase; letter-spacing:.08em; color:#94a3b8; }
            .ol-cp-side-item__value { margin-top:4px; font-size:15px; font-weight:700; color:#0f172a; }
            .ol-cp-side-item__sub { margin-top:2px; font-size:11px; color:#64748b; }
            .ol-cp-hide { display:none !important; }
            @media (max-width:1180px) { .ol-cp-form { grid-template-columns:1fr; } .ol-cp-form-side { position:static; } }
            @media (max-width:768px) { .ol-cp-stats, .ol-cp-grid { grid-template-columns:1fr; } .ol-cp-head, .ol-cp-card { padding:16px; } .ol-cp-head__title { font-size:21px; } }
        `;
        document.head.appendChild(style);
    }

    frappe.ui.form.on("Container Profile", {
        refresh(frm) {
            _renderForm(frm);
            _addButtons(frm);
        },
        container_name: _renderForm,
        container_code: _renderForm,
        container_type: _renderForm,
        cost_rank: _renderForm,
        max_weight_kg: _renderForm,
        max_volume_m3: _renderForm,
        is_active: _renderForm,
        allowed_zones: _renderForm,
        active_from: _renderForm,
        active_to: _renderForm,
        notes: _renderForm,
    });

    function _renderForm(frm) {
        const wrapper = frm.layout && frm.layout.wrapper;
        if (!wrapper) return;

        wrapper.querySelectorAll('.form-message-container .form-message').forEach((node) => node.remove());

        const existing = wrapper.querySelector('.ol-cp-shell');
        if (existing) existing.remove();

        const mainSection = wrapper.querySelector('.layout-main-section');
        const form = mainSection && mainSection.querySelector('form');
        if (!mainSection || !form) return;

        const shell = document.createElement('section');
        shell.className = 'ol-cp-shell';
        shell.innerHTML = _shellHtml(frm.doc);
        mainSection.prepend(shell);

        const mainTarget = shell.querySelector('#ol-cp-grid-main');
        const notesTarget = shell.querySelector('#ol-cp-grid-notes');

        [
            'container_name', 'container_code', 'container_type', 'cost_rank',
            'max_weight_kg', 'max_volume_m3', 'is_active', 'allowed_zones',
            'active_from', 'active_to'
        ].forEach((fieldname) => _mountField(frm, fieldname, mainTarget));
        _mountField(frm, 'notes', notesTarget);

        _hideOriginalFormChrome(wrapper, form, shell);
    }

    function _shellHtml(doc) {
        const weight = Number(doc.max_weight_kg || 0);
        const volume = Number(doc.max_volume_m3 || 0);
        const density = weight > 0 && volume > 0 ? (weight / volume) : 0;
        const zones = String(doc.allowed_zones || '').split(',').map((z) => z.trim()).filter(Boolean);
        const active = !!doc.is_active;

        return `
            <div class="ol-cp-head">
                <div>
                    <div class="ol-cp-head__eyebrow">${__('Container Profile')}</div>
                    <div class="ol-cp-head__title">${_esc(doc.container_name || doc.name || __('New Container Profile'))}</div>
                    <div class="ol-cp-head__sub">${__('Maintain planning-ready transport profiles in a cleaner edit workspace instead of raw field stack.')}</div>
                    <div class="ol-cp-head__meta">
                        <span class="ol-cp-pill ${active ? 'ol-cp-pill--active' : 'ol-cp-pill--inactive'}">${active ? __('Active') : __('Inactive')}</span>
                        <span class="ol-cp-pill">${_esc(doc.container_type || __('Type not set'))}</span>
                        <span class="ol-cp-pill">${__('Rank')} ${_esc(String(doc.cost_rank || 0))}</span>
                    </div>
                </div>
                <div class="ol-cp-stats">
                    ${_statCard(__('Max Weight'), _fmtWeight(weight), __('Capacity ceiling'))}
                    ${_statCard(__('Max Volume'), _fmtVolume(volume), __('Space ceiling'))}
                    ${_statCard(__('Density'), density ? `${density.toFixed(0)} kg/m³` : '0 kg/m³', __('Packing efficiency'))}
                    ${_statCard(__('Zones'), zones.length ? String(zones.length) : __('All'), __('Coverage'))}
                </div>
            </div>

            <div class="ol-cp-form">
                <div class="ol-cp-form-main">
                    <div class="ol-cp-card">
                        <div class="ol-cp-card__head">
                            <div>
                                <div class="ol-cp-card__title">${__('Profile Configuration')}</div>
                                <div class="ol-cp-card__sub">${__('Edit actual fields here. Controls stay native Frappe, layout now clean and responsive.')}</div>
                            </div>
                        </div>
                        <div id="ol-cp-grid-main" class="ol-cp-grid"></div>
                    </div>

                    <div class="ol-cp-card">
                        <div class="ol-cp-card__head">
                            <div>
                                <div class="ol-cp-card__title">${__('Notes')}</div>
                                <div class="ol-cp-card__sub">${__('Record carrier notes, operational limits, and planning assumptions.')}</div>
                            </div>
                        </div>
                        <div id="ol-cp-grid-notes" class="ol-cp-notes"></div>
                    </div>
                </div>

                <div class="ol-cp-form-side">
                    <div class="ol-cp-card">
                        <div class="ol-cp-card__head">
                            <div>
                                <div class="ol-cp-card__title">${__('Capacity Snapshot')}</div>
                                <div class="ol-cp-card__sub">${__('Quick read for planners before they use this profile in load plans.')}</div>
                            </div>
                        </div>
                        <div class="ol-cp-capacity">
                            ${_bar(__('Weight capacity'), _fmtWeight(weight), Math.min((weight / 30000) * 100, 100), 'weight')}
                            ${_bar(__('Volume capacity'), _fmtVolume(volume), Math.min((volume / 100) * 100, 100), 'volume')}
                            ${_bar(__('Density signal'), density ? `${density.toFixed(0)} kg / m³` : '0 kg / m³', Math.min((density / 1200) * 100, 100), 'density')}
                        </div>
                    </div>

                    <div class="ol-cp-card">
                        <div class="ol-cp-card__head">
                            <div>
                                <div class="ol-cp-card__title">${__('Coverage & Availability')}</div>
                                <div class="ol-cp-card__sub">${__('Decision support for dispatchers and planners.')}</div>
                            </div>
                        </div>
                        <div class="ol-cp-side-list">
                            <div class="ol-cp-side-item">
                                <div class="ol-cp-side-item__label">${__('Coverage')}</div>
                                <div class="ol-cp-side-item__value">${zones.length ? __('Restricted') : __('All Zones')}</div>
                                <div class="ol-cp-side-item__sub">${zones.length ? `<div class="ol-cp-zones">${zones.map((z) => `<span class="ol-cp-zone-pill">${_esc(z)}</span>`).join('')}</div>` : `<span class="ol-cp-zone-empty">${__('No zone restriction configured')}</span>`}</div>
                            </div>
                            <div class="ol-cp-side-item">
                                <div class="ol-cp-side-item__label">${__('Availability')}</div>
                                <div class="ol-cp-side-item__value">${active ? __('Dispatch Ready') : __('Standby')}</div>
                                <div class="ol-cp-side-item__sub">${_activeWindow(doc.active_from, doc.active_to)}</div>
                            </div>
                            <div class="ol-cp-side-item">
                                <div class="ol-cp-side-item__label">${__('Planning Action')}</div>
                                <div class="ol-cp-side-item__value">${__('View Linked Plans')}</div>
                                <div class="ol-cp-side-item__sub">${__('Use toolbar button to open load plans filtered by this profile.')}</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    function _mountField(frm, fieldname, target) {
        if (!target) return;
        const field = frm.fields_dict[fieldname];
        if (!field || !field.wrapper) return;
        const node = field.wrapper.closest('[data-fieldname]') || field.wrapper;
        target.appendChild(node);
    }

    function _hideOriginalFormChrome(wrapper, form, shell) {
        wrapper.querySelectorAll('.form-message-container .form-message').forEach((node) => node.remove());
        const pageForm = wrapper.querySelector('.page-form');
        if (pageForm) pageForm.classList.add('ol-cp-hide');
        const originalFormColumns = wrapper.querySelectorAll('.layout-main-section > .std-form-layout > .form-layout > .form-page > .form-section');
        originalFormColumns.forEach((node) => {
            if (!node.contains(shell)) node.classList.add('ol-cp-hide');
        });
        form.classList.add('ol-cp-hide');
    }

    function _addButtons(frm) {
        if (frm.__olCpButtons) return;
        frm.__olCpButtons = true;
        if (!frm.doc.__islocal) {
            frm.add_custom_button(__('View Load Plans'), () => {
                frappe.route_options = { container_profile: frm.doc.name };
                frappe.set_route('List', 'Container Load Plan');
            });
        }
    }

    function _statCard(label, value, sub) {
        return `<div class="ol-cp-stat"><div class="ol-cp-stat__label">${_esc(label)}</div><div class="ol-cp-stat__value">${_esc(value)}</div><div class="ol-cp-stat__sub">${_esc(sub)}</div></div>`;
    }

    function _bar(label, value, pct, tone) {
        return `<div class="ol-cp-capacity-row"><div class="ol-cp-capacity-head"><span class="ol-cp-capacity-label">${_esc(label)}</span><span class="ol-cp-capacity-value">${_esc(value)}</span></div><div class="ol-cp-bar ol-cp-bar--${tone}"><span style="width:${Number(pct || 0).toFixed(1)}%"></span></div></div>`;
    }

    function _fmtWeight(v) {
        const n = Number(v || 0);
        return n >= 1000 ? `${(n / 1000).toFixed(1).replace(/\.0$/, '')} t` : `${n.toFixed(0)} kg`;
    }

    function _fmtVolume(v) {
        return `${Number(v || 0).toFixed(1)} m³`;
    }

    function _activeWindow(fromDate, toDate) {
        if (!fromDate && !toDate) return __('Always available unless disabled');
        const parts = [];
        if (fromDate) parts.push(`${__('From')} ${_fmtDate(fromDate)}`);
        if (toDate) parts.push(`${__('Until')} ${_fmtDate(toDate)}`);
        return parts.join(' · ');
    }

    function _fmtDate(d) {
        try {
            return new Date(d).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
        } catch (e) {
            return d || '';
        }
    }

    function _esc(v) {
        return frappe.utils.escape_html(String(v || ''));
    }
})();
