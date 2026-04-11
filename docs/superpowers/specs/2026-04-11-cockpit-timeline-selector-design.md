# Cockpit Timeline Selector — Design Spec
Date: 2026-04-11

## Summary
Replace the Frappe Link field CLP selector with a full-screen 3-panel dashboard. Vanilla JS IIFE workspace bundle (consistent with existing sig_map, clp_dashboard patterns). Visual design from user-provided React mockup.

## Layout (3 panels)

```
┌──────┬──────────────────────┬──────────────────────────────────────┐
│ Icon │  Timeline Sidebar    │  Main Content                        │
│ Nav  │  (320px)             │  (flex-1)                            │
│(64px)│                      │                                      │
│      │  [Search]            │  Header: plan name | tab pills       │
│      │                      │  [Overview] [Manage]  [Run Analysis] │
│      │  ● Apr 15            │                                      │
│      │  EU-North Express    │  Overview tab:                       │
│      │  Hamburg ░░▓▓        │    KPI cards (4-col grid)            │
│      │                      │    Shipment list + Optimization panel│
│      │  ○ Apr 18            │                                      │
│      │  Asia-Pacific ...    │  Manage tab:                         │
│      │                      │    Queue col + Active col (DnD)      │
│      │  ○ Apr 20 ...        │                                      │
└──────┴──────────────────────┴──────────────────────────────────────┘
```

## Files

| File | Action |
|------|--------|
| `public/js/logistics_hub_cockpit_v2.js` | CREATE — vanilla JS IIFE, exports `orderliftCockpitV2.mount` |
| `public/css/logistics_hub_cockpit_v2.css` | CREATE — all styles for v2 shell |
| `orderlift_logistics/page/logistics_hub_cockpit/logistics_hub_cockpit.js` | REPLACE — thin loader (~40 lines) |
| `orderlift_logistics/doctype/container_load_plan/container_load_plan.py` | ADD — `get_load_plans_list` endpoint |

## Panel 1 — Icon Nav (64px)
- Truck logo (blue pill)
- Dashboard icon (active, links to cockpit)
- Package icon (links to CLP list)
- TrendingUp icon (links to analytics)
- Bell (no-op)
- User avatar (no-op)
- All SVG inline, no external icon lib

## Panel 2 — Timeline Sidebar (320px)
- Header: "Load Plans" label + search input
- Scrollable list, sorted departure_date ASC
- Each card: departure date (blue, small), status badge, plan label, destination, mini weight+volume bars
- Selected: blue border + dot ring
- Unselected: grey dot, hover shadow
- Vertical timeline line connecting dots

## Panel 3 — Main Content

### Header (80px)
- Left: container icon + plan label (18px bold) + plan ID + container type (12px muted)
- Center: tab pills — `Overview` | `Manage` (pill with animated underline/fill)
- Right: `Auto-Suggest` button + `Run Analysis` button (blue)

### Overview Tab
**KPI row (4 cols):**
1. Departure card — date large, days-until sub
2. Shipments card — count, validation status
3. Utilization card (col-span-2) — weight gauge + volume gauge animated

**Content grid (3 cols):**
- col-span-2: Included Shipments list — each row: icon, DN + customer, weight badge, volume badge, remove button
- col-span-1 right panel:
  - Dark card: Load Optimization (efficiency %, limiting factor, tip text)
  - White card: Alerts (over_capacity = red, incomplete_data = amber, departure within 3 days = amber)

### Manage Tab
Exact existing cockpit queue/active layout (ol-cc-* classes) reused inside the tab panel. Capacity gauges stay in active column header. Search bar above both columns.

## API

### New: `get_load_plans_list`
```python
@frappe.whitelist()
def get_load_plans_list():
    plans = frappe.db.get_all("Container Load Plan",
        fields=["name", "container_label", "container_profile", "destination_zone",
                "departure_date", "status", "analysis_status",
                "weight_utilization_pct", "volume_utilization_pct",
                "total_weight_kg", "total_volume_m3",
                "max_weight_kg", "max_volume_m3"],
        order_by="departure_date asc, creation asc"
    )
    return plans
```

### Existing (unchanged)
- `get_cockpit_data(load_plan_name)` — used when plan selected
- `append_shipments`, `remove_shipment`, `reorder_shipments`, `set_shipment_selected` — used in Manage tab
- `suggest_shipments`, `run_load_plan_analysis` — action buttons

## State
```js
{
  plans: [],           // from get_load_plans_list
  selectedPlanId: null,
  cockpitData: null,   // from get_cockpit_data
  activeTab: 'overview',
  searchQuery: '',
  loading: false
}
```

## Design Tokens (from mockup)
- BG: `#F8FAFC`
- White panels: `#ffffff`
- Border: `#E2E8F0` (slate-200)
- Primary blue: `#2563EB`
- Text primary: `#0F172A`
- Text muted: `#64748B`
- Status Planning: slate-100/700
- Status Ready: blue-50/700
- Status Loading: amber-50/700
- Status In Transit: indigo-50/700
- Status Delivered: emerald-50/700
- Status Cancelled: red-50/700

## Loader (logistics_hub_cockpit.js replacement)
Same pattern as project_map.js:
- on_page_load: make_app_page, hide toolbar, mount once
- on_page_show: no-op
- Loads CSS + JS from assets, calls orderliftCockpitV2.mount(root, { preloadPlan })
- Stretch layout to full viewport height
