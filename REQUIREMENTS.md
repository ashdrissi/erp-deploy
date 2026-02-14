# Orderlift ERP — Functional Requirements
# Orderlift ERP — Cahier des Charges Fonctionnel

**Project / Projet :** Custom ERP Implementation (V0) – Multi-Company & Logistics  
**Provider / Prestataire :** Syntax Line  
**Client :** Orderlift  
**Contract Start / Début du Contrat :** February 9, 2026  
**Document Version :** V0.1  

---

## Table of Contents / Sommaire

1. [Project Overview](#1-project-overview)
2. [Organizational Structure](#2-organizational-structure)
3. [Core Architecture & ERPNext Configuration](#3-core-architecture--erpnext-configuration)
4. [Item Master (Base Articles)](#4-item-master-base-articles)
5. [Sales, Pricing & Commissions](#5-sales-pricing--commissions)
6. [B2B Client Portal](#6-b2b-client-portal)
7. [Logistics Intelligence](#7-logistics-intelligence)
8. [Stock Management (Multi-Warehouse)](#8-stock-management-multi-warehouse)
9. [Inter-Company & Inter-Warehouse Transfers](#9-inter-company--inter-warehouse-transfers)
10. [CRM & Customer Management](#10-crm--customer-management)
11. [SAV – After-Sales Service](#11-sav--after-sales-service)
12. [SIG – Geo-location & Project Tracking](#12-sig--geo-location--project-tracking)
13. [HR Module](#13-hr-module)
14. [Purchases & Suppliers](#14-purchases--suppliers)
15. [Automated Documents (PDF)](#15-automated-documents-pdf)
16. [Analytics & Dashboards](#16-analytics--dashboards)
17. [Implementation Approach Summary](#17-implementation-approach-summary)

---

## 1. Project Overview

**EN:** Orderlift is a multi-entity company operating in the elevator parts industry. The parent company handles manufacturing, cost management, and international export. Multiple antenna companies handle local distribution, installation, and maintenance in their respective countries. This ERP system centralizes all operations across all entities on a single ERPNext v15 instance.

**FR:** Orderlift est une entreprise multi-entités opérant dans le secteur des pièces d'ascenseurs. La société mère gère la fabrication, les coûts de revient et l'export international. Plusieurs sociétés antennes gèrent la distribution locale, l'installation et la maintenance dans leurs pays respectifs. Ce système ERP centralise toutes les opérations de toutes les entités sur une seule instance ERPNext v15.

**Technology Stack / Stack Technique :** ERPNext v15 · Frappe Framework · Python · JavaScript · MariaDB · Docker  
**Custom App :** `orderlift` (installed alongside ERPNext core — core is never modified)

---

## 2. Organizational Structure

**EN:** The system must support the following entity structure:

**FR:** Le système doit supporter la structure d'entités suivante :

```
Parent Company (Société Mère)
│   Role: Manufacturing / Cost Management / International Export
│   Manages: Item Master, Cost Prices, Inter-company Sales
│
├── Antenna Company — Morocco (Société Antenne — Maroc)
│       Role: Import / Local Distribution / Installation / Maintenance
│
├── Antenna Company — France (Société Antenne — France)
│       Role: Import / Local Distribution / Installation / Maintenance
│
└── Antenna Company — Turkey (Société Antenne — Turquie)  [TBD with client]
        Role: Import / Local Distribution / Installation / Maintenance
```

- Each company can have multiple warehouses / Chaque société peut avoir plusieurs entrepôts
- Each company operates independently but shares the centralized Item Master / Chaque société opère indépendamment mais partage la base articles centralisée
- Inter-company transactions are tracked and reconciled / Les transactions inter-sociétés sont suivies et réconciliées

**ERPNext Mechanism:** Built-in `Company` doctype. Each entity is a separate ERPNext Company. Inter-company transactions use ERPNext's native inter-company Sales/Purchase Order linking.

---

## 3. Core Architecture & ERPNext Configuration

**Summary / Résumé :** Foundation setup — no custom code required, pure ERPNext configuration exported as fixture JSON files for reproducibility.

### 3.1 Companies / Sociétés
- [ ] Create Parent Company with currency, fiscal year, chart of accounts
- [ ] Create each Antenna Company linked to Parent
- [ ] Configure inter-company relationships for automated purchase/sales order mirroring
- [ ] Set up company-specific cost centers

**ERPNext:** `Company` doctype · `Cost Center` · Chart of Accounts setup

### 3.2 Warehouses / Entrepôts
- [ ] Each company has warehouses for: Real Stock, Transit Stock, Reserved Stock, Return Stock
- [ ] Warehouse naming convention: `[Company Prefix]-[Type]` (e.g., `OL-MA-REAL`, `OL-MA-TRANSIT`)
- [ ] Minimum stock thresholds configured per item per warehouse

**ERPNext:** `Warehouse` doctype · `Item Reorder` doctype

### 3.3 User Roles & Permissions / Rôles & Permissions
- [ ] `Orderlift Admin` — full access across all companies
- [ ] `Stock Manager` — stock operations, transfer validation
- [ ] `Sales Manager` — sales, pricing, commission visibility
- [ ] `Commercial` — own sales pipeline, CRM, limited pricing
- [ ] `Technician` — SAV tickets assigned to them only
- [ ] `Accountant` — invoicing, financial reports
- [ ] `B2B Portal Client` — portal access only, own orders only

**ERPNext:** `Role` · `Role Profile` · `User Permission` doctypes

### 3.4 Currency & Pricing Zones / Devises & Zones de Prix
- [ ] Multi-currency support (MAD, EUR, USD, TRY — [TBD with client])
- [ ] Geographic pricing zones mapped to cities or regions per antenna company
- [ ] Price lists per zone: `Pricelist-MA-Casablanca`, `Pricelist-MA-Marrakech`, etc. [TBD with client]

**ERPNext:** `Currency` · `Price List` doctypes

---

## 4. Item Master (Base Articles)

**Summary / Résumé :** A centralized article database managed exclusively by the parent company. All antenna companies read from it but cannot modify cost prices.

**ERPNext Mechanism:** Standard `Item` doctype + custom child tables and custom fields added via the `orderlift` app fixtures. Core Item doctype is not modified — fields are added through the Custom Field mechanism.

### 4.1 Standard Fields (already in ERPNext)
- Item Code (unique), Item Name, Item Group (with parent-child hierarchy / famille-sous-famille)
- Unit of Measure, Stock UOM
- Is Active / Is Inactive (`disabled` flag)

### 4.2 Custom Fields to Add / Champs Personnalisés à Ajouter

| Field Label (EN) | Field Label (FR) | Field Type | Notes |
|---|---|---|---|
| Technical Characteristics | Caractéristiques Techniques | Long Text | Free text or structured |
| Unit Weight (kg) | Poids Unitaire (kg) | Float | For logistics calculation |
| Unit Volume (m³) | Volume Unitaire (m³) | Float | For logistics calculation |
| Packaging Type | Type d'Emballage | Select | Box / Pallet / Crate |
| Units per Pallet | Unités par Palette | Int | |
| Pallet Weight (kg) | Poids Palette (kg) | Float | Auto-calculated |
| Pallet Volume (m³) | Volume Palette (m³) | Float | Auto-calculated |
| Current Cost Price | Coût de Revient Actuel | Currency | Managed by parent only |
| Cost Price Updated On | Coût MàJ le | Date | Auto-set on save |
| Market Reference Price | Prix Marché de Référence | Currency | Collected systematically |

### 4.3 Cost Price History / Historique des Coûts de Revient

**EN:** Every time the parent company updates a cost price, the previous value must be archived with a timestamp. Cost history must also track costs at each lifecycle stage plus general cost allocation (salaries, rent, subscriptions).

**FR:** Chaque mise à jour du coût de revient par la société mère doit archiver la valeur précédente avec horodatage. L'historique doit aussi tracer les coûts par étape du cycle de vie plus la répartition des charges générales (salariés, loyer, abonnements).

**ERPNext Mechanism:** Custom child Doctype `Item Cost History` linked to `Item`.

| Field | Type | Notes |
|---|---|---|
| Date | Date | Auto-set |
| Cost Price | Currency | Snapshot value |
| Lifecycle Stage | Select | Raw Material / Production / Packaging / Export / [TBD] |
| General Cost Allocation | Currency | Proportion of overhead allocated to this item |
| Updated By | Link → User | Auto-set |
| Notes | Small Text | |

### 4.4 Price Grids / Grilles Tarifaires

**EN:** Multiple sales price grids per item based on geographic zone and quantity brackets.

**FR:** Plusieurs grilles de prix de vente par article selon la zone géographique et les tranches de quantité.

**ERPNext Mechanism:** `Item Price` records per `Price List`. One Price List per geographic zone. Quantity-based pricing via `Pricing Rule` doctype.

---

## 5. Sales, Pricing & Commissions

**Summary / Résumé :** Complete Order-to-Cash workflow with advanced margin control, dynamic pricing, and full commission tracking per salesperson and per project.

### 5.1 Order-to-Cash Workflow

```
Quotation (Devis)
    │
    ▼
[Client Approval]
    │
    ▼
Sales Order (Commande)
    │
    ├──► Stock Reservation (Réservation Stock)
    │
    ▼
Delivery Note (Bon de Livraison)
    │
    ▼
Sales Invoice (Facture)
    │
    ▼
Payment Entry (Paiement)
```

**ERPNext Mechanism:** Standard ERPNext Sales cycle. Workflow states added via `Workflow` doctype on `Sales Order`.

### 5.2 Advanced Pricing / Pricing Avancé

- [ ] Cost price sourced from parent company (read-only on antenna companies)
- [ ] Option to include or exclude local transport costs per quote line
- [ ] Per-article margin adjustment directly in the Quotation
- [ ] Global margin visibility per Quotation, per Customer, per Project
- [ ] Dynamic pricing = f(item base price, geographic zone, quantity, optional transport)
- [ ] Market price collection: systematic logging of competitor/market prices per item

**ERPNext Mechanism:**
- Margin fields: standard `Quotation Item` fields (gross profit %, margin amount)
- Transport toggle: custom field on `Quotation Item` — `Include Transport` (Check)
- Market price: custom Doctype `Market Price Entry`

**Custom Doctype: `Market Price Entry`**

| Field | Type |
|---|---|
| Item | Link → Item |
| Date | Date |
| Source / Competitor | Data |
| Market Price | Currency |
| Currency | Link → Currency |
| Zone | Data |
| Notes | Small Text |

### 5.3 Commissions / Commissions Commerciales

**EN:** Commissions are calculated per salesperson per project and tracked through paid/pending states.

**FR:** Les commissions sont calculées par commercial et par projet et suivies entre états payé/en attente.

**Custom Doctype: `Sales Commission`**

| Field | Type | Notes |
|---|---|---|
| Salesperson | Link → Sales Person | |
| Project | Link → Project | |
| Sales Order | Link → Sales Order | |
| Sales Invoice | Link → Sales Invoice | |
| Commission Rate (%) | Percent | |
| Commission Amount | Currency | Auto-calculated |
| Status | Select | Pending / Approved / Paid |
| Payment Date | Date | |
| Notes | Small Text | |

- [ ] Commission rate configurable per salesperson (default) and overridable per project
- [ ] Commission amount auto-calculated on Sales Invoice submission
- [ ] Report: commissions payées / à payer par commercial et par période

---

## 6. B2B Client Portal

**Summary / Résumé :** A secure web interface for B2B clients to browse the catalog, get dynamic quotes, and place orders — connected directly to ERPNext inventory and pricing.

**ERPNext Mechanism:** Frappe portal framework (`/www/` pages in `orderlift` app) + custom `Portal Order` Doctype. Authentication via standard Frappe user portal with `B2B Portal Client` role.

### 6.1 Access & Account Management / Accès & Gestion de Compte

- [ ] Client self-registration form at `/register`
- [ ] Manual account validation by an administrator before first login
- [ ] Role-based access: clients see only their own orders, quotes, and invoices
- [ ] Secure login via Frappe session management

### 6.2 Catalog & Dynamic Pricing / Catalogue & Pricing Dynamique

- [ ] Display available items with technical specs, images, unit weight/volume
- [ ] Price shown is computed dynamically: f(item, client geographic zone, quantity)
- [ ] Pricing zones assigned to client at account creation [TBD: zone = city, region, or country]
- [ ] Price updates transparently when quantity changes (AJAX, no page reload)
- [ ] Items marked inactive are hidden from the portal

### 6.3 Quotation Workflow / Workflow Devis

```
Client selects items + quantities on portal
    │
    ▼
System computes price (pricing engine)
    │
    ▼
Auto-generated Quotation PDF (branded)
    │
    ▼
Quotation emailed to client automatically
    │
    ▼
Commercial notified (email + ERPNext notification)
    │
    ▼
Client confirms via portal (or email link)
    │
    ▼
Quotation converted to Sales Order in ERPNext
    │
    ▼
Stock reservation triggered
```

- [ ] Quote validity: configurable per client or globally (default: 10 days)
- [ ] Client can view all past quotes and their status from portal dashboard
- [ ] Client can re-order from a past order with one click

### 6.4 Portal Order Doctype

**Custom Doctype: `Portal Order`** (staging area before becoming a Sales Order)

| Field | Type | Notes |
|---|---|---|
| Portal Client | Link → Customer | |
| Status | Select | Draft / Submitted / Converted / Cancelled |
| Items (child table) | Table → Portal Order Item | |
| Pricing Zone | Data | Inherited from Customer |
| Total Amount | Currency | Auto-calculated |
| Linked Quotation | Link → Quotation | Set after conversion |
| Linked Sales Order | Link → Sales Order | Set after conversion |
| Notes | Small Text | |

---

## 7. Logistics Intelligence

**Summary / Résumé :** A proprietary algorithm that calculates total shipment volume and weight for an order (or consolidated multi-client shipment) and recommends the optimal container or truck type.

**ERPNext Mechanism:** Custom Doctype `Shipment Plan` + Python module `orderlift/logistics/utils/container_optimizer.py`.

### 7.1 Inputs to the Algorithm / Entrées de l'Algorithme

- [ ] List of items with quantities (from one or multiple Sales Orders)
- [ ] Unit weight and volume per item (from Item Master)
- [ ] Packaging dimensions (pallet/box data from Item Master)
- [ ] Number of destination clients (for multi-client consolidation)
- [ ] Destination zone (affects truck vs container recommendation)

### 7.2 Algorithm Logic / Logique de l'Algorithme

```
For each item line:
    Line Volume = Unit Volume × Quantity (+ packaging overhead)
    Line Weight = Unit Weight × Quantity (+ packaging overhead)

Total Shipment Volume = Σ Line Volumes
Total Shipment Weight = Σ Line Weights

Recommendation logic:
    IF weight < 500kg AND volume < 2m³  → Small Van / Petit Camion
    IF weight < 3,500kg                 → Standard Truck / Camion Standard
    IF weight < 22,000kg               → Full Truck Load (FTL)
    IF international destination        → Container (20ft or 40ft based on volume)
    IF volume > 33m³                   → 40ft Container
    ELSE                               → 20ft Container
    [Thresholds TBD with client]
```

### 7.3 Custom Doctype: `Shipment Plan`

| Field | Type | Notes |
|---|---|---|
| Reference | Data | Auto-numbered |
| Sales Orders (child table) | Table | Links to one or more Sales Orders |
| Items Summary (child table) | Table | Consolidated item list |
| Total Weight (kg) | Float | Auto-calculated |
| Total Volume (m³) | Float | Auto-calculated |
| Number of Clients | Int | |
| Destination Zone | Data | |
| Recommended Transport | Data | Output of algorithm |
| Override Transport | Select | Manual override if needed |
| Generated Documents | Section | Links to Packing List, BL |

### 7.4 Outputs / Sorties
- [ ] Recommended transport type displayed clearly
- [ ] Auto-generate Packing List from the Shipment Plan
- [ ] Auto-generate pre-loading quality checklist (`Fiche de Contrôle avant Chargement`)

---

## 8. Stock Management (Multi-Warehouse)

**Summary / Résumé :** Each warehouse tracks 4 stock categories. Stock reservation requires manager validation. Automatic alerts on threshold breach.

**ERPNext Mechanism:** Standard ERPNext `Stock Ledger Entry` · `Warehouse` · `Item Reorder`. Stock categories managed via dedicated warehouses per type (ERPNext best practice — no core modification).

### 8.1 Stock Categories per Warehouse / Catégories de Stock par Entrepôt

| Category (EN) | Catégorie (FR) | ERPNext Warehouse Suffix | Notes |
|---|---|---|---|
| Real Stock | Stock Réel | `-REAL` | Available for sale |
| Reserved Stock | Stock Réservé | `-RESERVED` | Linked to a confirmed Sales Order |
| Transit Stock | Stock Transit | `-TRANSIT` | Goods in movement between entities |
| Return Stock | Stock Retour | `-RETURN` | Returned goods pending inspection |

### 8.2 Stock Reservation Workflow / Workflow Réservation Stock

```
Sales Order confirmed by commercial
    │
    ▼
System checks Real Stock availability
    │
    ├── [Sufficient] ──► Reservation Request created
    │                         │
    │                         ▼
    │                    Stock Manager notified
    │                         │
    │                         ▼
    │                    Manager validates reservation
    │                         │
    │                         ▼
    │                    Stock moved: REAL → RESERVED warehouse
    │
    └── [Insufficient] ──► Alert sent to Stock Manager + Commercial
                               │
                               ▼
                          Reorder process triggered (see Module 14)
```

- [ ] Reservation validated exclusively by `Stock Manager` role
- [ ] Reservation linked to specific Sales Order — cannot be released without cancelling the order
- [ ] Automatic low-stock alert when quantity falls below `minimum threshold` on Item Reorder record

**ERPNext Mechanism:** `Stock Entry` (Material Transfer) between warehouses · `Workflow` on a custom `Stock Reservation Request` Doctype · `Notification` Doctype for alerts.

---

## 9. Inter-Company & Inter-Warehouse Transfers

**Summary / Résumé :** Goods move from the parent company to antenna companies and between warehouses within a company via a validated 5-step workflow.

### 9.1 Transfer Workflow / Workflow Transfert

```
Step 1 — Transfer Request / Demande de Transfert
    Antenna company or warehouse creates a transfer request
    │
    ▼
Step 2 — Sender Validation / Validation Entrepôt Expéditeur
    Source warehouse manager approves and prepares goods
    │
    ▼
Step 3 — Preparation / Préparation
    Goods physically prepared, packing list generated
    │
    ▼
Step 4 — Transit / Transit
    Goods shipped, stock moved to TRANSIT warehouse
    Tracking reference assigned
    │
    ▼
Step 5 — Reception & Quality Control / Réception & Contrôle
    Destination confirms receipt, quality check performed
    Stock moved: TRANSIT → REAL at destination
    Any discrepancy logged as a quality issue
```

**ERPNext Mechanism:**
- Inter-company: `Purchase Order` (antenna) ↔ `Sales Order` (parent) via ERPNext inter-company feature
- Intra-company: `Stock Entry` (Material Transfer) with Workflow states
- Custom `Workflow` on `Stock Entry` enforcing the 5 steps

### 9.2 Transfer Document
- [ ] Auto-generate a transfer document (PDF) at Step 3 with item list, quantities, weights, volumes
- [ ] Document references both the source and destination entity/warehouse
- [ ] Signed off digitally at Step 5 by the receiving manager

---

## 10. CRM & Customer Management

**Summary / Résumé :** Full customer lifecycle management with structured contact programming, interaction history, project stage tracking, configurable notifications per profile per stage, and media attachment support.

**ERPNext Mechanism:** ERPNext `Customer` · `Contact` · `Lead` · `Opportunity` doctypes extended with custom child tables and a configurable notification engine in the `orderlift` app.

### 10.1 Customer Records / Fiches Clients

- [ ] Customer classification: Installer / Distributor / Internal (`customer_type` custom field)
- [ ] Financial situation visible: outstanding balance, payment history
- [ ] Full history: quotes, orders, deliveries, invoices linked from Customer record
- [ ] Attach any document or media (contract, ID, photos) to Customer record

**ERPNext Mechanism:** Standard `Customer` doctype + custom field `Customer Classification` (Select).

### 10.2 Interaction History / Historique des Interactions

**Custom Child Doctype: `Customer Interaction`** (linked to Customer and/or Project)

| Field | Type | Notes |
|---|---|---|
| Date & Time | Datetime | |
| Type | Select | Call / Email / Visit / WhatsApp / Instagram |
| Direction | Select | Inbound / Outbound |
| Contact Person | Link → Contact | |
| Handled By | Link → User | Commercial or Manager |
| Summary | Text | |
| Next Action | Small Text | |
| Next Action Date | Date | Triggers reminder |
| Attachments | Attach | |

### 10.3 Project Lifecycle & Stage Tracking / Suivi du Cycle de Vie Projet

**EN:** Each customer project moves through configurable stages. Each stage can have specific notification rules: who gets notified, at what frequency, and what trigger type.

**FR:** Chaque projet client progresse à travers des étapes configurables. Chaque étape peut avoir des règles de notification spécifiques : qui est notifié, à quelle fréquence, et selon quel déclencheur.

**Custom Doctype: `Project Stage Template`** (defines available stages — configurable by admin)

| Field | Type |
|---|---|
| Stage Name (EN) | Data |
| Stage Name (FR) | Data |
| Description | Small Text |
| Default Assigned Role | Link → Role |
| Notification Rules (child table) | Table → Stage Notification Rule |

**Custom Child Doctype: `Stage Notification Rule`**

| Field | Type | Notes |
|---|---|---|
| Notify Role | Link → Role | e.g., `Commercial`, `Sales Manager` |
| Notify Specific User | Link → User | Optional override |
| Trigger | Select | On Entry / On Deadline / Recurring |
| Frequency | Select | Once / Daily / Weekly / Custom |
| Frequency Days | Int | If Custom frequency |
| Notification Channel | Select | Email / ERPNext Alert / Both |
| Message Template | Text | Jinja2 template |

**Project Record** (ERPNext `Project` doctype extended with custom fields):

| Custom Field | Type | Notes |
|---|---|---|
| Current Stage | Link → Project Stage Template | |
| Stage History (child table) | Table | Log of stage changes with timestamps |
| Assigned Profile (for specific stage) | Link → User | Temporary assignment for a stage |
| Customer | Link → Customer | |

### 10.4 Contact Programming / Programmation des Contacts

- [ ] Schedule recurring contacts per customer based on `Customer Classification`
  - e.g., Installers → contact every 30 days; Distributors → every 14 days [TBD]
- [ ] Scheduled contacts appear as Tasks assigned to the responsible Commercial
- [ ] Overdue contacts trigger an escalation notification to the Sales Manager

### 10.5 Social Integration / Intégration Réseaux Sociaux

- [ ] WhatsApp: log outbound messages sent via WhatsApp as `Customer Interaction` records (manual logging or via WhatsApp Business API if available)
- [ ] Instagram: log DMs as interactions (manual logging or via Instagram Graph API if available)
- [ ] API availability to be confirmed — manual logging as fallback

---

## 11. SAV – After-Sales Service

**Summary / Résumé :** A complete ticketing system for declaring, assigning, tracking, and mandatorily closing after-sales anomalies. Included in V0.

**ERPNext Mechanism:** Custom Doctype `SAV Ticket` with a `Workflow` enforcing mandatory closure documentation.

### 11.1 SAV Ticket Workflow / Workflow Ticket SAV

```
Anomaly declared (call or portal form)
    │
    ▼
SAV Ticket created (Status: Open / Ouvert)
    Linked to: Customer, Installation Project (optional), Item (optional)
    │
    ▼
Ticket assigned to Technician
    Technician receives email + ERPNext notification
    (Status: Assigned / Affecté)
    │
    ▼
Technician acknowledges and works on issue
    (Status: In Progress / En cours)
    │
    ▼
Technician submits resolution report (mandatory)
    Resolution description required — cannot close without it
    (Status: Resolved / Résolu)
    │
    ▼
SAV Manager validates closure
    (Status: Closed / Clôturé)
    │
    └── [Rejected] ──► Returns to In Progress with manager's comments
```

### 11.2 Custom Doctype: `SAV Ticket`

| Field | Type | Notes |
|---|---|---|
| Ticket ID | Data | Auto-numbered |
| Customer | Link → Customer | |
| Contact | Link → Contact | |
| Reported Via | Select | Call / Portal / Email / WhatsApp |
| Item Concerned | Link → Item | Optional |
| Installation Project | Link → Project | Optional |
| Anomaly Description | Text | Mandatory on creation |
| Priority | Select | Low / Medium / High / Critical |
| Assigned Technician | Link → User | |
| Status | Select | Open / Assigned / In Progress / Resolved / Closed |
| Intervention Date | Date | |
| Resolution Report | Text | Mandatory before status → Resolved |
| Attachments (photos, docs) | Attach Multiple | |
| Closed By | Link → User | |
| Closure Date | Datetime | Auto-set |
| SLA Breach | Check | Auto-flagged if resolution exceeds threshold [TBD] |

---

## 12. SIG – Geo-location & Project Tracking

**Summary / Résumé :** Map-based visualization of all installation projects with real-time status and on-site quality control checklists. Included in V0.

**ERPNext Mechanism:** Custom Doctype `Installation Project` + a Frappe web page rendering a Leaflet.js map (`/project-map`). Accessible from Desk and optionally from the portal.

### 12.1 Custom Doctype: `Installation Project`

| Field | Type | Notes |
|---|---|---|
| Project Name | Data | |
| Customer | Link → Customer | |
| Sales Order | Link → Sales Order | |
| Address | Text | Full installation address |
| Latitude | Float | For map pin |
| Longitude | Float | For map pin |
| Current Status | Select | Planned / In Progress / On Hold / Completed |
| Assigned Technician | Link → User | |
| Current Stage | Link → Project Stage Template | Shared stage engine from Module 10 |
| Quality Checklists (child table) | Table → QC Checklist Item | |
| Photos / Documents | Attach Multiple | |
| Completion Date | Date | |

### 12.2 Quality Control Checklist / Formulaire Contrôle Qualité

**Custom Child Doctype: `QC Checklist Item`**

| Field | Type |
|---|---|
| Check Point (EN) | Data |
| Check Point (FR) | Data |
| Status | Select: Pass / Fail / N/A |
| Comment | Small Text |
| Photo | Attach |

- [ ] Checklist templates configurable by admin (different templates per project type)
- [ ] Checklist filled on-site by technician (mobile-friendly Desk view)
- [ ] Project cannot be marked `Completed` without all checklist items resolved

### 12.3 Map View / Vue Cartographique

- [ ] Desk page at `/app/installation-project-map` renders all Installation Projects as pins on a Leaflet.js map
- [ ] Pin color indicates status: Blue = Planned, Orange = In Progress, Red = On Hold, Green = Completed
- [ ] Click on pin opens Installation Project record
- [ ] Filter by status, technician, customer, date range

---

## 13. HR Module

**Summary / Résumé :** Employee records, leave/attendance tracking, and resource evaluation. Provided primarily by ERPNext HRMS (already installed) with configuration and minor extensions. Included in V0.

**ERPNext Mechanism:** ERPNext `HRMS` app — standard configuration + custom fields.

### 13.1 Employee Records / Dossiers Employés

- [ ] Job description per employee (`Job Description` doctype — standard HRMS)
- [ ] Contact details, emergency contacts
- [ ] Qualifications and certifications (custom child table on `Employee`)
- [ ] Documents attached (contracts, IDs, diplomas)

### 13.2 Leave & Attendance / Congés & Présences

- [ ] Leave requests and approvals (`Leave Application` — standard HRMS)
- [ ] Attendance tracking (`Attendance` — standard HRMS)
- [ ] Travel tracking: custom field `Travel Request` or use HRMS `Travel Request` doctype

### 13.3 Resource Evaluation / Évaluation des Ressources

- [ ] New hire evaluation form (custom Doctype `Employee Evaluation`)
- [ ] Training path tracking: courses assigned, completed, pending
- [ ] Operational validation: sign-off that a technician is field-ready for a specific equipment type

**Custom Doctype: `Employee Evaluation`**

| Field | Type |
|---|---|
| Employee | Link → Employee |
| Evaluation Date | Date |
| Evaluator | Link → User |
| Type | Select: New Hire / Annual / Post-Training |
| Criteria (child table) | Table → Evaluation Criterion |
| Overall Score | Float |
| Validated for Field Work | Check |
| Notes | Text |

---

## 14. Purchases & Suppliers

**Summary / Résumé :** Full supplier and installer management with purchase order tracking, reception quality control, and automated reordering.

**ERPNext Mechanism:** Standard ERPNext `Supplier` · `Purchase Order` · `Purchase Receipt` doctypes + configuration. Custom fields for contractual document management.

### 14.1 Supplier & Partner Management / Gestion Fournisseurs & Partenaires

- [ ] Supplier records with classification: Supplier / Installer / Partner
- [ ] Contractual documents attached to Supplier record (contracts, certifications)
- [ ] Supplier performance score visible on Supplier record (auto-calculated from lead time data)

**Custom Fields on `Supplier`:**

| Field | Type |
|---|---|
| Supplier Classification | Select: Supplier / Installer / Partner |
| Average Lead Time (days) | Float — auto-calculated |
| Reliability Score (%) | Float — auto-calculated |
| Contractual Documents | Attach Multiple |

### 14.2 Purchase Order & Lead Time / Commandes & Délais

- [ ] Standard Purchase Order workflow (ERPNext native)
- [ ] Expected delivery date mandatory on each PO line
- [ ] Automatic alert if delivery date is exceeded without a receipt
- [ ] Lead time history tracked per supplier per item

### 14.3 Reception & Quality Control / Réception & Contrôle Qualité

```
Purchase Order sent to supplier
    │
    ▼
Expected delivery date tracked
    │
    ▼
Goods received → Purchase Receipt created
    │
    ▼
Quality inspection step (mandatory for flagged items)
    QC pass → Stock moved to REAL warehouse
    QC fail → Stock moved to RETURN warehouse + supplier notified
```

**ERPNext Mechanism:** `Purchase Receipt` + `Quality Inspection` doctypes (standard ERPNext).

### 14.4 Automatic Reordering / Réapprovisionnement Automatique

- [ ] Minimum stock threshold per item per warehouse (configured in `Item Reorder`)
- [ ] When Real Stock falls below threshold: automatic `Purchase Order` draft created
- [ ] Notification sent to Purchasing Manager for validation before submission
- [ ] Preferred supplier per item configured in `Item Supplier` child table

**ERPNext Mechanism:** `Reorder Level` (standard) + `Notification` doctype for alerts.

---

## 15. Automated Documents (PDF)

**Summary / Résumé :** All key documents auto-generated with Orderlift corporate branding using Frappe Print Formats (Jinja2 HTML templates). Auto-numbered with full traceability.

**ERPNext Mechanism:** `Print Format` records stored in the `orderlift` app under `print_formats/`. No core modification — Print Formats are app-level Jinja2 HTML files.

| Document (EN) | Document (FR) | Based on ERPNext Doctype | Auto-Numbering |
|---|---|---|---|
| Quotation | Devis | `Quotation` | QT-YYYY-XXXXX |
| Sales Order | Commande Client | `Sales Order` | SO-YYYY-XXXXX |
| Delivery Note | Bon de Livraison | `Delivery Note` | DN-YYYY-XXXXX |
| Packing List | Liste de Colisage | `Delivery Note` (custom section) | PL-YYYY-XXXXX |
| Invoice | Facture | `Sales Invoice` | INV-YYYY-XXXXX |
| Transfer Document | Bon de Transfert | `Stock Entry` | TR-YYYY-XXXXX |
| Pre-loading Checklist | Fiche Contrôle Chargement | `Shipment Plan` | CHK-YYYY-XXXXX |

- [ ] All documents include Orderlift logo, company header, footer with page numbers
- [ ] Bilingual documents (French primary + English secondary) [TBD with client]
- [ ] PDF sent automatically by email on document submission
- [ ] All documents linked back to their source record for traceability

---

## 16. Analytics & Dashboards

**Summary / Résumé :** Role-specific dashboards and reports giving real-time visibility into stock health, supplier performance, and financial margins.

**ERPNext Mechanism:** Frappe `Dashboard` + `Dashboard Chart` + `Report` (Query Report or Script Report) doctypes. All defined in the `orderlift` app.

### 16.1 Stock KPIs / KPIs Stock

| Indicator (EN) | Indicateur (FR) | Type |
|---|---|---|
| Stock Rotation Rate | Taux de Rotation des Stocks | Dashboard Chart |
| Time to Stockout | Délai avant Rupture | Dashboard Chart |
| Overstock Items | Articles en Surstock | Query Report |
| Slow-Moving Items | Articles à Faible Rotation | Query Report |
| Current Stock by Warehouse | Stock Actuel par Entrepôt | Dashboard Chart |

### 16.2 Supplier Performance / Performance Fournisseurs

| Indicator (EN) | Indicateur (FR) | Type |
|---|---|---|
| Average Lead Time per Supplier | Délai Moyen par Fournisseur | Dashboard Chart |
| On-Time Delivery Rate | Taux de Livraison à Temps | Dashboard Chart |
| Supplier Reliability Score | Score Fiabilité Fournisseur | Query Report |

### 16.3 Financial Insights / Insights Financiers

| Indicator (EN) | Indicateur (FR) | Type |
|---|---|---|
| Margin per Project | Marge par Projet | Script Report |
| Margin per Customer | Marge par Client | Script Report |
| Delivery Time vs Target | Délai Livraison vs Cible | Dashboard Chart |
| Revenue by Antenna Company | CA par Société Antenne | Dashboard Chart |
| Commission Summary | Récapitulatif Commissions | Script Report |

### 16.4 Operational Goals / Objectifs Opérationnels

- Reduce stockouts / Réduire les ruptures de stock
- Reduce supplier lead times / Réduire les délais fournisseurs
- Avoid overstock and slow-moving items / Éviter le surstock et les articles à faible rotation

---

## 17. Implementation Approach Summary

### The Rule: Never Modify ERPNext Core
All customization lives in the `orderlift` Frappe app at `erp-deploy/apps/orderlift/`. Core ERPNext, Frappe, and HRMS files are never modified. This ensures upgradability, security, and maintainability.

### ERPNext Module Mapping Table

| Contract Deliverable | ERPNext Mechanism | Custom Code | Core Modified? |
|---|---|---|---|
| Multi-company structure | `Company` doctype configuration | No — fixtures only | No |
| Multi-warehouse + stock types | `Warehouse` doctype, one warehouse per stock type | No — fixtures only | No |
| User roles & permissions | `Role` · `Role Profile` · `User Permission` | No — configuration | No |
| Item Master extensions | Custom Fields on `Item` via fixture | Yes — field definitions | No |
| Item cost price history | Custom child Doctype `Item Cost History` | Yes — full doctype | No |
| Item price grids | `Price List` + `Pricing Rule` configuration | No — configuration | No |
| Order-to-Cash workflow | Standard Sales cycle + `Workflow` on `Sales Order` | Minimal — workflow config | No |
| Commission tracking | Custom Doctype `Sales Commission` + server hook | Yes — full doctype + logic | No |
| Market price collection | Custom Doctype `Market Price Entry` | Yes — full doctype | No |
| Dynamic pricing engine | Custom Python module `pricing_engine.py` | Yes — algorithm | No |
| B2B Client Portal | Frappe `/www/` pages + custom `Portal Order` Doctype | Yes — pages + doctype | No |
| Logistics optimizer | Custom Doctype `Shipment Plan` + `container_optimizer.py` | Yes — algorithm | No |
| Branded PDF templates | `Print Format` Jinja2 HTML files (per document type) | Yes — 7 templates | No |
| Stock reservation workflow | Custom `Stock Reservation Request` Doctype + Workflow | Yes — doctype + workflow | No |
| Inter-company transfers | ERPNext native inter-company + `Workflow` on `Stock Entry` | Minimal — workflow config | No |
| CRM interaction history | Custom child Doctype `Customer Interaction` | Yes — full doctype | No |
| Project stage notifications | Custom Doctypes `Project Stage Template` + `Stage Notification Rule` | Yes — notification engine | No |
| Contact programming / scheduling | ERPNext `Task` + scheduled job in `orderlift` app | Yes — scheduled job | No |
| WhatsApp / Instagram integration | Manual logging via `Customer Interaction` (API if available) | Minimal — logging form | No |
| SAV ticketing + workflow | Custom Doctype `SAV Ticket` + `Workflow` | Yes — full doctype + workflow | No |
| SIG geo-tracking map | Custom Doctype `Installation Project` + Leaflet.js page | Yes — doctype + map page | No |
| QC checklists (SIG) | Custom child Doctype `QC Checklist Item` + template system | Yes — full doctype | No |
| HR records | HRMS configuration + custom fields on `Employee` | Minimal — config + fields | No |
| Employee evaluation | Custom Doctype `Employee Evaluation` | Yes — full doctype | No |
| Purchase / supplier management | Standard `Supplier` · `Purchase Order` + custom fields | Minimal — fields + config | No |
| Goods receipt + quality control | `Purchase Receipt` + `Quality Inspection` (standard ERPNext) | No — configuration | No |
| Auto reorder | `Item Reorder` configuration + `Notification` doctype | No — configuration | No |
| Stock KPI dashboards | Frappe `Dashboard` + `Dashboard Chart` | Yes — custom reports | No |
| Supplier performance reports | Frappe `Query Report` | Yes — custom SQL reports | No |
| Financial margin reports | Frappe `Script Report` | Yes — custom Python reports | No |

### Custom App Structure / Structure de l'App Personnalisée

```
erp-deploy/apps/orderlift/
├── setup.py
├── MANIFEST.in
├── requirements.txt
└── orderlift/
    ├── __init__.py
    ├── hooks.py                  # App metadata, event hooks, scheduled tasks
    ├── modules.txt               # Module declarations
    ├── patches.txt
    ├── config/
    │   └── desktop.py            # Desk module icons
    ├── fixtures/                 # JSON: custom fields, workflows, roles, print formats
    ├── sales/
    │   ├── doctype/
    │   │   ├── sales_commission/
    │   │   └── market_price_entry/
    │   └── utils/
    │       └── commission_calculator.py
    ├── portal/
    │   ├── doctype/
    │   │   └── portal_order/
    │   ├── www/                  # Web-accessible pages
    │   └── utils/
    │       └── pricing_engine.py
    ├── logistics/
    │   ├── doctype/
    │   │   └── shipment_plan/
    │   └── utils/
    │       └── container_optimizer.py
    ├── crm/
    │   ├── doctype/
    │   │   ├── customer_interaction/
    │   │   ├── project_stage_template/
    │   │   └── stage_notification_rule/
    │   └── utils/
    │       └── notification_scheduler.py
    ├── sav/
    │   └── doctype/
    │       └── sav_ticket/
    ├── sig/
    │   ├── doctype/
    │   │   └── installation_project/
    │   └── www/
    │       └── project-map.html
    ├── hr/
    │   └── doctype/
    │       └── employee_evaluation/
    ├── print_formats/            # Jinja2 HTML branded PDF templates
    └── public/
        ├── css/orderlift.css
        └── js/orderlift.js
```

### Development Phases / Phases de Développement

| Phase | Weeks | Focus |
|---|---|---|
| 1 — Foundation | 1–4 | ERPNext config, companies, warehouses, roles, Item Master, data import |
| 2 — Custom Development | 5–8 | `orderlift` app: all custom Doctypes, portal, logistics, PDF templates |
| 3 — UAT & Revisions | 9–10 | Client testing, Revision Rounds 1 & 2 |
| 4 — Final Polish | 11–12 | Live utilization, Revision Round 3, training, sign-off |

---

*Document maintained by Syntax Line · Last updated: February 2026*
