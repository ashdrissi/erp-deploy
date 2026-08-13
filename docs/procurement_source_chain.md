# Procurement Source Chain

The Commercial Source Chain section is read-only traceability on Material Request,
Purchase Order, Purchase Receipt, and Purchase Invoice forms.

It follows native item references only:

```
Opportunity -> Quotation -> Sales Order -> Material Request -> Purchase Order -> Purchase Receipt -> Purchase Invoice
```

The section groups item rows by source chain. A document with more than one source
shows each chain separately. Manually entered items without a source are shown in a
separate warning group.

Purchase Invoice items do not have native Sales Order fields. The section resolves
their Sales Order through Purchase Receipt, Purchase Order, and Material Request item
references when those links exist.

This feature is not an accounting dimension. It never sets or changes Project, Cost
Center, Sales Order, Material Request, or other accounting fields. When a user cannot
read an upstream document, its identifier remains visible for traceability but is plain
text and cannot be opened.

Use the standard ERPNext mappings to preserve the chain:

1. Create a Material Request from the Sales Order.
2. Create the Purchase Order from the Material Request.
3. Create the Purchase Receipt and Purchase Invoice from the Purchase Order or
   Purchase Receipt.

Manual purchasing lines remain valid, but are intentionally identified as unlinked.
