frappe.ui.form.on('Customer Segmentation Engine', {
    refresh(frm) {
        if (frm.doc.is_active) {
            frm.add_custom_button(__('Calculate Now'), function () {
                frappe.call({
                    method: 'calculate_segments',
                    doc: frm.doc,
                    freeze: true,
                    freeze_message: __('Evaluating segmentation rules...'),
                    callback: function (r) {
                        if (r.message) {
                            frm.events.render_results(frm, r.message);
                        }
                    }
                });
            }, __('Actions'));

            frm.add_custom_button(__('Apply to Customers'), function () {
                frappe.confirm(
                    __('This will update the Tier field on all matched customers. Continue?'),
                    function () {
                        frappe.call({
                            method: 'apply_segments',
                            doc: frm.doc,
                            freeze: true,
                            freeze_message: __('Applying segments to customers...'),
                            callback: function (r) {
                                if (r.message) {
                                    frm.events.render_results(frm, r.message);
                                }
                            }
                        });
                    }
                );
            }, __('Actions'));
        }
    },

    render_results(frm, results) {
        if (!results || !results.length) {
            frm.fields_dict.results_html.$wrapper.html(
                '<p style="color: var(--text-muted);">No customers matched.</p>'
            );
            return;
        }

        let html = '<div style="border:1px solid var(--border-color);border-radius:8px;overflow:hidden;">';
        html += '<table class="table table-bordered" style="margin:0;font-size:12px;">';
        html += '<thead style="background:#fafafa;"><tr>';
        html += '<th>ID</th><th>Customer</th><th>Segment</th>';
        html += '<th>Variables</th><th>Confidence</th>';
        html += '</tr></thead><tbody>';

        const segmentColors = {
            'Gold': 'background:#fef3c7;color:#b45309;',
            'Silver': 'background:#f3f4f6;color:#4b5563;',
            'Bronze': 'background:#fff7ed;color:#9a3412;',
            'Eco': 'background:#ecfdf5;color:#065f46;',
        };

        results.forEach(r => {
            const seg = r.assigned_segment || 'Unmatched';
            const style = segmentColors[seg] || 'background:#f3f4f6;color:#6b7280;';
            const vars = r.variables || {};
            const varStr = Object.entries(vars)
                .map(([k, v]) => `${k}: ${typeof v === 'number' ? v.toLocaleString() : v}`)
                .join(' | ');

            html += '<tr>';
            html += `<td style="color:#6b7280;">${r.customer}</td>`;
            html += `<td style="font-weight:600;">${r.customer_name}</td>`;
            html += `<td><span style="display:inline-block;padding:2px 8px;border-radius:12px;font-weight:600;font-size:11px;${style}">${seg}</span></td>`;
            html += `<td style="color:#6b7280;font-size:11px;">${varStr}</td>`;
            html += `<td style="color:#059669;font-weight:600;">${r.confidence}%</td>`;
            html += '</tr>';
        });

        html += '</tbody></table></div>';
        html += `<div style="font-size:11px;color:var(--text-muted);margin-top:8px;">${results.length} customers evaluated.</div>`;

        frm.fields_dict.results_html.$wrapper.html(html);
    }
});
