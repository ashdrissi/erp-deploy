# Logistics UAT Checklist

## 23.1 Partial shipment vs full order
- Create a Sales Order with 10 lines.
- Generate first Delivery Note with 5 lines only.
- Run `Run Container Analysis` on Delivery Note.
- Validate totals and recommendation only reflect shipped lines.

## 23.2 Heavy-low-volume vs light-high-volume
- Test DN A with dense items (high kg, low m3).
- Test DN B with bulky items (low kg, high m3).
- Confirm limiting factor changes to `weight` for A and `volume` for B.

## 23.3 Dispatcher manual override + resync
- Create Container Load Plan and manually add/remove Delivery Notes.
- Run `Run Logistics Analysis`.
- Run `Suggest Shipments` and verify dashboard updates.
- Ensure no duplicate DN assignment across active plans.

## 23.4 Cancel/reopen/reassign edge cases
- Submit a Container Load Plan and verify Delivery Notes lock.
- Cancel the plan and verify DN lock is released.
- Reassign same DN to a new plan and submit.
- Cancel Delivery Note and verify latest Shipment Analysis is marked `cancelled`.
