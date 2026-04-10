# Logistics Workflow Map

This document maps the logistics process document-by-document for the four supported scenarios:

1. Import managed by Orderlift
2. Domestic distribution in Morocco
3. Export managed by customer
4. Export managed by Orderlift

## Core Decision Fields

Use these fields to classify logistics behavior early and carry the decision forward:

- `flow_scope`
  - `Inbound`
  - `Domestic`
  - `Outbound`
- `shipping_responsibility`
  - `Orderlift`
  - `Customer`

## Where The Decision Should Be Made

- `Purchase Order`
  - use for inbound/import decisions
- `Sales Order`
  - use for outbound decisions
- `Delivery Note` or internal dispatch request
  - use for domestic distribution decisions

These values should be inherited by downstream documents instead of being decided again inside planning screens.

---

## Document Roles

### Purchase Order

Used for:

- inbound/import procurement
- supplier-side consolidation candidates

Should hold:

- `flow_scope = Inbound`
- `shipping_responsibility = Orderlift`
- supplier
- origin country
- origin port
- expected arrival warehouse

### Sales Order

Used for:

- outbound commercial commitment

Should hold:

- `flow_scope = Outbound`
- `shipping_responsibility = Orderlift` or `Customer`
- final destination/customer delivery mode

### Delivery Note

Used for:

- physical outbound issue from stock
- domestic distribution execution source
- outbound shipment source when Orderlift handles shipping

Should hold or inherit:

- `flow_scope`
- `shipping_responsibility`
- destination zone / Morocco region when relevant

### Container Load Plan

Used for:

- planning and grouping shipments into a container/load

Should be a planning layer, not the original place where the scenario is decided.

Should inherit:

- `flow_scope`
- `shipping_responsibility`
- source document type

### Shipment Analysis

Used for:

- recommendation snapshot
- capacity/utilization results

Should inherit planning context from the source and/or load plan.

### Purchase Receipt

Used for:

- physical receipt into stock after import/inbound delivery

Relevant to:

- inbound/import flow

### Quality Inspection

Used for:

- post-receipt QC control

Relevant to:

- inbound/import flow

### Stock Entry

Used for:

- warehouse routing after QC
- internal transfer/distribution support

### Delivery Trip

Used for:

- execution layer only
- vehicle + driver + stops

Best fit:

- domestic Morocco distribution
- outbound deliveries handled by Orderlift

Not suitable as the main planning document for import container consolidation.

---

## Scenario 1: Import Managed By Orderlift

### Business Intent

You buy from suppliers abroad, consolidate inbound goods into a container, receive them in Morocco, then make them available for stock and later distribution.

### Document Flow

1. `Purchase Order`
- source document
- marks the flow as inbound
- carries supplier/origin/procurement intent

2. `Container Load Plan`
- groups multiple inbound POs or inbound shipment candidates
- plans container fill
- may include suggested replenishment items for low stock if they can join the same inbound container

3. `Shipment Analysis`
- stores recommendation/utilization snapshot for the inbound plan

4. `Purchase Receipt`
- records physical arrival into Morocco warehouse/QC zone

5. `Quality Inspection`
- evaluates received items

6. `Stock Entry`
- routes QC-passed goods to usable stock
- routes QC-failed goods to return/reject stock

7. `Delivery Note` or internal dispatch request
- optional later step when stock is redistributed in Morocco

### Key Ownership

- planning: `Purchase Order` + `Container Load Plan`
- receiving/QC: `Purchase Receipt` + `Quality Inspection`
- routing: `Stock Entry`

---

## Scenario 2: Domestic Distribution In Morocco

### Business Intent

Goods are already in Morocco and need to be distributed to branches, warehouses, projects, or customers.

### Document Flow

1. `Delivery Note` or internal dispatch request
- source document for local movement
- marks the flow as domestic

2. `Container Load Plan`
- optional planning step if grouping is needed
- can represent truck/load batching rather than overseas container planning

3. `Delivery Trip`
- execution layer
- assigns vehicle, driver, and stops

4. `Stock Entry`
- used when movement is warehouse-to-warehouse rather than customer delivery

### Key Ownership

- planning: `Delivery Note` / dispatch + optional `Container Load Plan`
- execution: `Delivery Trip`

---

## Scenario 3: Export Managed By Customer

### Business Intent

You sell the goods, but the customer arranges shipment and transport.

### Document Flow

1. `Sales Order`
- source document
- marks the flow as outbound
- marks shipping responsibility as customer

2. `Delivery Note`
- prepares goods for release or pickup

3. Optional `Shipment Analysis`
- advisory only, if you still want a forecast for internal visibility

### What Should Not Happen

- no internal container planning is required as an operational obligation
- no `Delivery Trip` unless Orderlift is actually executing a local leg

### Key Ownership

- commercial readiness: `Sales Order`
- stock release: `Delivery Note`

---

## Scenario 4: Export Managed By Orderlift

### Business Intent

You sell the goods and also arrange shipment/logistics for the outbound movement.

### Document Flow

1. `Sales Order`
- source document
- marks the flow as outbound
- marks shipping responsibility as Orderlift

2. `Delivery Note`
- source of actual outbound goods to ship

3. `Container Load Plan`
- groups outbound delivery notes into the planned shipment/container

4. `Shipment Analysis`
- stores capacity and utilization results

5. `Delivery Trip`
- optional execution layer if there is a local transport leg Orderlift manages

### Key Ownership

- planning: `Sales Order` + `Delivery Note` + `Container Load Plan`
- execution: `Delivery Trip` when local movement is involved

---

## Recommended Inheritance Rules

### From Purchase Order

Copy into downstream inbound planning docs:

- `flow_scope = Inbound`
- `shipping_responsibility = Orderlift`
- supplier
- origin attributes

### From Sales Order

Copy into downstream outbound docs:

- `flow_scope = Outbound`
- `shipping_responsibility`
- customer destination attributes

### From Delivery Note

Copy into execution docs:

- domestic/outbound scope
- destination zone / Morocco region

### Into Container Load Plan

Always inherit from source docs rather than deciding there.

---

## Practical System Split

### Planning Layer

Use custom logistics documents for:

- consolidation
- recommendation
- load/container fill
- utilization

Main docs:

- `Container Load Plan`
- `Shipment Analysis`

### Execution Layer

Use ERPNext native execution where appropriate:

- `Delivery Trip` for vehicle/driver/stop execution
- `Stock Entry` for internal warehouse movement
- `Purchase Receipt` for inbound receipt

---

## Recommended Next Implementation Direction

1. Add `flow_scope` and `shipping_responsibility` to the source documents:
- `Purchase Order`
- `Sales Order`
- `Delivery Note`
- `Container Load Plan`

2. Restrict current outbound planning logic so it only applies to:
- `Outbound + Orderlift`

3. Add inbound planning support sourced from `Purchase Order`

4. Use `Delivery Trip` for domestic and locally executed outbound delivery

5. Keep import container planning separate from `Delivery Trip`
