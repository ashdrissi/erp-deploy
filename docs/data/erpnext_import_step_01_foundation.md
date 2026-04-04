# ERPNext Import Step 01 Foundation

## Scope

This step defines the base masters and mapping needed before loading real product and pricing data into ERPNext.

Primary source chosen for import prep:
- `PRICING ORDER LIFT TURKEY - MOROCCO _v07.02.2026 (2).xlsx`
- Authoritative sheet: `Pricing sheet clean`

Supporting reference only:
- `Pricing Turkey` for source cost / reference buying prices
- `Pricing & Edition Devis_V01.2026 (3).xlsm` for quote validation and price cross-checking

## Why This Sheet Was Chosen

- It contains the same core item reference family used by the quote workbook.
- It is the cleanest selling-price oriented sheet.
- It has structured columns for `Ref`, `Description`, `Composante`, `Unite`, `Poids`, and three Morocco price levels.
- It avoids using the quote workbook as the master source of truth.

## Extracted Master Facts

- Item rows found: `171`
- Unique item codes: `169`
- Duplicate item codes: `2`
- Unique component families: `11`
- UOM values found: `Pc`, `SET`, `M`, plus invalid `0` on 2 rows

## ERPNext Object Mapping

### 1. Item Group

Source column:
- `Composante`

ERPNext target:
- `Item Group`

Clean import values are listed in `item_groups_step_01.csv`.

### 2. UOM

Source column:
- `Unite`

ERPNext target:
- `UOM`

Clean import values are listed in `uom_step_01.csv`.

### 3. Item

Recommended initial mapping:

| Source Column | ERPNext Field | Notes |
| --- | --- | --- |
| `Ref` | `Item Code` | Primary unique key |
| `Description` | `Item Name` | Keep business-facing description |
| `Description` | `Description` | Same as item name for phase 1 |
| `Composante` | `Item Group` | Use cleaned values from item group master |
| `Unite` | `Stock UOM` | Must be normalized first |
| `Poids` | `Weight Per Unit` | Keep numeric value only |
| constant | `Disabled` | `0` for active catalog |

Optional later fields:
- `Default Supplier`
- `Country of Origin`
- custom field for source material / steel type
- custom field for source comment
- custom field for KDV possibility

### 4. Price List

Recommended ERPNext price lists for phase 1:
- `Turkey Source Cost` -> buying/reference, `USD`
- `Morocco Min` -> selling, `MAD`
- `Morocco Normal` -> selling, `MAD`
- `Morocco With Stock` -> selling, `MAD`

These are listed in `price_lists_step_01.csv`.

### 5. Item Price

Recommended initial mapping:

| Source Sheet | Source Column | ERPNext Field |
| --- | --- | --- |
| `Pricing Turkey` | `PRICE IN TURKEY (without kdv) + LOCAL TRANSP 'USD'` | `Price List Rate` on `Turkey Source Cost` |
| `Pricing sheet clean` | `Prix a proposer ss stock (min)` | `Price List Rate` on `Morocco Min` |
| `Pricing sheet clean` | `Prix a proposer (normal)` | `Price List Rate` on `Morocco Normal` |
| `Pricing sheet clean` | `Prix a proposer avec stock` | `Price List Rate` on `Morocco With Stock` |

Recommended ERPNext item price columns:
- `Item Code`
- `Price List`
- `Currency`
- `Price List Rate`
- `Selling`
- `Buying`
- `UOM`

## Review Issues Found In Step 01

### Invalid UOM rows

These two rows have `Unite = 0`, which is not importable as a UOM:
- `IT.33` `CABLE REGULATEUR (6mm)`
- `IT.37` `SERRE CABLE DIAM 6,5mm *`

Action:
- confirm correct UOM before import, likely `Pc` or `M`
- do not auto-correct without business confirmation

### Duplicate item code rows

These rows reuse item codes, which blocks direct ERPNext `Item` import because `Item Code` must be unique:
- `IT.1-17`
  - `CABINE  1000/900 PANORAMIQUE`
  - `SET ARCADE TYPE L VVVF 2V`
- `IT.1-18`
  - `CABINE  1100/1000 PANORAMIQUE`
  - `SET ARCADE TYPE L GEARLESS`

Action:
- split these into unique business item codes before import
- do not import until code ownership is confirmed

### Component family requiring confirmation

Two rows use component family `GOSE`:
- `IT.39` `GOSE 96 CM (50 KG)`
- `IT.81` `GOSE 76CM - 31KG`

Action:
- keep as its own item group for now
- confirm whether `GOSE` is a real business family name or should be merged into another category

## What Is Ready After This Step

- Item Group master list
- UOM master list
- Price List master list
- issue list for cleanup before import
- agreed mapping from Excel columns to ERPNext doctypes

## What Is Blocked Before Step 02 Import Output

- duplicate item codes must be resolved first
- invalid UOM values on 2 rows must be corrected or confirmed

## What Comes Next In Step 02

- generate the cleaned `Item` import dataset from `Pricing sheet clean`
- generate the `Item Price` import dataset from `Pricing sheet clean` and `Pricing Turkey`
- flag any rows with missing or invalid values during transformation
