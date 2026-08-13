# Customer Delivery Stock Reservation

Orderlift uses Pick Lists for prepared customer allocations and permits direct delivery only from unreserved stock.

## Required Flow

1. Submit the Sales Order.
2. Create a Pick List from the submitted Sales Order.
3. Submit the Pick List after choosing warehouse, batch, serial, and picked quantity.
4. Pick List submission automatically reserves the available picked quantity.
5. Physically label the prepared stock in the source warehouse with customer, Sales Order, Pick List, and reserved quantity.
6. Create the Delivery Note from the reserved Pick List.
7. Submit the Delivery Note only when goods leave the warehouse.
8. Create the Sales Invoice without moving stock again.

## Enforcement

Delivery Note rows created from a Pick List require:

- Submitted Pick List reference.
- Pick List Item reference.
- Sales Order row reference.
- Picked quantity on the Pick List row.
- Stock-reserved quantity on the Pick List row.
- Delivery quantity not greater than picked or reserved stock quantity.

Direct Delivery Notes are allowed without a Pick List when the requested quantity does not exceed unreserved stock:

`unreserved stock = actual stock - active Stock Reservation Entries`

Direct rows for the same item and warehouse are aggregated. Reserved serial numbers and reserved batch quantities cannot be used. If the Delivery Note's own Sales Order row has an active reservation, create the Delivery Note from its Pick List instead.

Cancelling a Pick List cancels its open Stock Reservation Entries.

## Shortages

Shortage handling is manual.

If a customer orders more than available stock, reserve only what is available and review the remaining shortage manually. Do not auto-create Material Requests from the stock-reservation notification flow.

## Notifications

Sales Order submission notifies enabled users who:

- Have the `stock_reservation_management` capability.
- Have access to the Sales Order company.

Notification code must not hardcode recipient role names. Manage recipients through role capabilities and company permissions.
