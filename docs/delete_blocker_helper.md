# Delete Blocker Helper

The global Desk delete helper recursively previews the current document's readable downstream link blockers. Shared dependencies are shown once, and selected blockers are deleted deepest-first before the requested parent.

The cascade direction is downstream only: it deletes documents that block deletion of the requested document. It does not delete upstream/master source records that the requested document points to. For example, deleting a Quotation can delete downstream Sales Orders or other blockers if selected, but it must not delete the linked Customer or Opportunity. Master/reference records are kept and only removable link rows are unlinked.

Master/reference records are not treated as children. If a Prospect, Customer, Lead, Contact, Supplier, Item, or similar master record links to the document being deleted, the safe action is to remove the link row/reference from that master record, not to cascade-delete the master record itself.

## Standard Access

- The user must have native delete permission on the parent and every selected blocker.
- Submitted parents and blockers remain locked.
- Restricted blocker details are hidden.
- Master/reference records are shown as blockers but cannot be selected for cascade deletion.
- Ledger rows are not independent cascade targets; users select and cancel/delete their source business voucher instead. Ledger links that are not exact source-voucher links, such as stock history by `item_code`, remain locked blockers.
- The whole operation rolls back if links change or any deletion fails.

## Privileged Access

The `delete_submitted_blockers` role capability enables the override only inside this helper.

- Read permission is still required for the parent and every visible blocker.
- Missing native delete permission is overridden for selected blockers and the parent.
- Submitted records are cancelled through native Frappe hooks before deletion.
- Existing GL Entry, Payment Ledger Entry, Advance Payment Ledger Entry, and Stock Ledger Entry records are never selectable as standalone cascade blockers; review and select the source business voucher instead.
- During privileged hard deletion of each source voucher, the helper runs native `on_trash` cleanup first, then removes any remaining GL Entry and Stock Ledger Entry rows matching the exact `voucher_type` and `voucher_no`. It also removes remaining Payment Ledger Entry and Advance Payment Ledger Entry rows owned by that exact voucher and delinked rows whose exact against-voucher is being deleted.
- The ledger cleanup is transactional with the full cascade and applies only to this privileged helper. Normal ERPNext cancellation/deletion behavior and the site-wide `delete_linked_ledger_entries` setting are unchanged.
- Native link checks still run; blockers that appear or change after preview stop and roll back the operation.
- Standard non-custom DocTypes remain protected.
- Frappe's Deleted Document records preserve the normal recoverable deletion snapshot.

The default managed role matrix grants this capability to `Orderlift Admin`. `System Manager` retains the capability through the existing hardcoded capability policy.
