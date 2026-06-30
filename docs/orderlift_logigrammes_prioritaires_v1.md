# Logigrammes prioritaires Orderlift - V1

Ces logigrammes Mermaid couvrent les procedures 1 a 15 en s'appuyant sur le fonctionnement actuel de l'application Orderlift: modules natifs ERPNext, pages Orderlift, hooks serveur, pipelines CRM/logistique, pricing, SAV, SIG, training, finance et droits par societe.

## Conventions

- Les documents natifs ERPNext sont notes tels quels: `Sales Order`, `Purchase Order`, `Delivery Note`, etc.
- Les objets/pages Orderlift sont notes tels quels: `Pricing Sheet`, `Forecast Load Plan`, `SAV Ticket`, `Campaign Manager`, etc.
- Les noeuds `Guardrail` representent des validations bloqueantes ou alertes systeme.
- Les noeuds `Dashboard` representent les vues de pilotage utilisees par l'equipe.

## 1. Gestion de l'operation d'achats

```mermaid
flowchart TD
  subgraph S1[Declenchement du besoin]
    A1["Besoin stock, projet ou commande client"] --> A2{"Origine du besoin"}
    A2 -->|Stock bas| A3["Reorder Manager / Material Request"]
    A2 -->|Projet installation| A4["Project / Sales Order"]
    A2 -->|Achat manuel| A5["Demande achat interne"]
  end

  subgraph S2[Preparation achat]
    A3 --> B1["Verifier Item, UOM, packaging profile"]
    A4 --> B1
    A5 --> B1
    B1 --> B2{"Supplier existe et qualifie ?"}
    B2 -->|Non| B3["Creer / completer Supplier"]
    B3 --> B4["Verifier prix, delai, paiement, conformite"]
    B4 --> B5{"Supplier valide ?"}
    B5 -->|Non| B6["Rechercher autre fournisseur"]
    B5 -->|Oui| B7["Request for Quotation"]
    B2 -->|Oui| B7
    B7 --> B8["Comparer offres fournisseur"]
  end

  subgraph S3[Commande et validation]
    B8 --> C1["Purchase Order"]
    C1 --> C2["Guardrail: packaging, prix, societe, fournisseur"]
    C2 --> C3{"PO valide ?"}
    C3 -->|Non| C4["Corriger ou annuler PO"]
    C4 --> C1
    C3 -->|Oui| C5["Soumettre Purchase Order"]
  end

  subgraph S4[Reception et stock]
    C5 --> D1{"Import / inbound gere par Orderlift ?"}
    D1 -->|Oui| D2["Forecast Load Plan / Container Planning"]
    D1 -->|Non| D3["Livraison fournisseur directe"]
    D2 --> D4["Purchase Receipt"]
    D3 --> D4
    D4 --> D5["Quality Inspection"]
    D5 --> D6{"QC accepte ?"}
    D6 -->|Oui| D7["Stock Entry vers stock disponible"]
    D6 -->|Non| D8["Stock Entry vers rejet / retour"]
    D7 --> D9["Stock Ledger + Stock Dashboard"]
    D8 --> D9
  end
```

## 2. Pricing - definition et actualisation des prix de vente

```mermaid
flowchart TD
  subgraph P1[Donnees de base]
    A["Item + dimensions + HS code + matiere douane"] --> B["Buying Price List / Item Price"]
    B --> C["Pricing Scenario: charges, transport, customs"]
    A --> D["Selling / benchmark price lists"]
    D --> E["Pricing Benchmark Policy"]
  end

  subgraph P2[Contexte client et agent]
    F["Customer / Prospect"] --> G["CRM Business Type + CRM Segment"]
    G --> H["Customer Segmentation Engine"]
    H --> I["Tier + modifiers"]
    J["Sales Person / agent"] --> K["Agent Pricing Rules"]
    K --> L["Agent Dynamic Pricing Config"]
  end

  subgraph P3[Calcul Pricing Sheet]
    C --> M["Pricing Sheet / Pricing Builder"]
    E --> M
    I --> M
    L --> M
    M --> N["Calcul landed cost"]
    N --> O["Calcul benchmark reference"]
    O --> Q{"Sources benchmark suffisantes ?"}
    Q -->|Non| R["Fallback margin + warning"]
    Q -->|Oui| S{"Regle ratio trouvee ?"}
    S -->|Non| R
    S -->|Oui| T["Marge cible benchmark"]
    R --> U["Prix projete"]
    T --> U
    U --> V["Apply tier, group, zone modifiers"]
  end

  subgraph P4[Validation et publication]
    V --> W{"Guardrails pricing OK ?"}
    W -->|Non| X["Revision Pricing Manager"]
    X --> M
    W -->|Oui| Y["Prix final valide"]
    Y --> Z1["Generate Quotation"]
    Y --> Z2["Update Selling Price List / Item Price"]
    Z2 --> Z3["Catalogue Prix Articles"]
  end
```

## 3. Recrutement d'un intermediaire / apporteur d'affaires

```mermaid
flowchart TD
  subgraph R1[Qualification]
    A["Candidat agent / apporteur"] --> B["Collecter profil, zone, portefeuille, experience"]
    B --> C{"Profil commercial credible ?"}
    C -->|Non| D["Archiver / relance future"]
    C -->|Oui| E["Creer Sales Person"]
  end

  subgraph R2[Activation ERP]
    E --> F{"Besoin acces ERP ?"}
    F -->|Oui| G["Creer User + roles limites + company access"]
    F -->|Non| H["Agent suivi par commercial interne"]
    G --> I["Agent Pricing Rules"]
    H --> I
    I --> J["Price lists autorisees"]
    J --> K["Scenario pricing + customs + benchmark autorises"]
    K --> L["Contrat / accord commission"]
  end

  subgraph R3[Cycle commission]
    L --> M["Agent genere Lead / Opportunity / Quotation"]
    M --> N["Quotation Item stocke source_sales_person et commission"]
    N --> O["Sales Order soumis"]
    O --> P["Hook: create Sales Commission"]
    P --> Q["Status = Approved"]
    Q --> R["Sales Invoice"]
    R --> S{"Invoice totalement payee ?"}
    S -->|Non| Q
    S -->|Oui| T["Status = To Pay"]
    T --> U["Commission Dashboard: validation payout"]
    U --> V["Status = Paid"]
  end
```

## 4. Gestion de l'operation logistique

```mermaid
flowchart TD
  subgraph L1[Classification source]
    A["Document source"] --> B{"Source"}
    B -->|Import achat| C["Purchase Order"]
    B -->|Export / vente| D["Sales Order"]
    B -->|Distribution locale| E["Delivery Note / dispatch"]
    C --> F["flow_scope = Inbound"]
    D --> G["flow_scope = Outbound"]
    E --> H["flow_scope = Domestic"]
  end

  subgraph L2[Decision responsabilite]
    F --> I["shipping_responsibility = Orderlift"]
    G --> J{"Shipping responsibility"}
    J -->|Customer| K["Preparation pickup client"]
    J -->|Orderlift| M["Planification Orderlift"]
    H --> N{"Mouvement client ou interne ?"}
    N -->|Client| O["Delivery Trip"]
    N -->|Interne| P["Stock Entry"]
  end

  subgraph L3[Planning]
    I --> Q["Forecast Load Plan"]
    M --> Q
    Q --> R["Selection Container Profile"]
    R --> S["Ajouter sources ou free items"]
    S --> T["Calcul poids, volume, utilisation"]
    T --> U{"Capacite OK ?"}
    U -->|Non| V["Changer container / lignes"]
    V --> S
    U -->|Oui| W["Status Planning -> Ready"]
  end

  subgraph L4[Execution]
    W --> X["Sources liees + plan verrouille"]
    X --> Y["Loading"]
    Y --> Z["In Transit"]
    Z --> AA["Delivered"]
    K --> AB["Delivery Note / release stock"]
    O --> AA
    P --> AA
  end
```

## 5. Gestion des entrees / sorties du stock

```mermaid
flowchart TD
  subgraph ST1[Declencheurs]
    A["Mouvement stock"] --> B{"Type"}
    B -->|Entree achat| C["Purchase Receipt"]
    B -->|Sortie vente| D["Sales Order submitted"]
    B -->|Transfert interne| E["Stock Entry"]
    B -->|SAV| F["SAV Ticket stock action"]
  end

  subgraph ST2[Entrees]
    C --> G["Quality Inspection"]
    G --> H{"QC accepte ?"}
    H -->|Oui| I["Route vers stock disponible"]
    H -->|Non| J["Route vers reject / return warehouse"]
  end

  subgraph ST3[Sorties]
    D --> K["Notification Stock Manager"]
    K --> L["Verifier Stock Balance"]
    L --> M{"Disponible ?"}
    M -->|Non| N["Material Request / achat"]
    M -->|Oui| O["Pick List / Delivery Note"]
    N --> O
    O --> P["Delivery Note submitted"]
  end

  subgraph ST4[Traçabilite]
    E --> Q["Warehouse source -> cible"]
    F --> Q
    I --> R["Stock Ledger"]
    J --> R
    P --> R
    Q --> R
    R --> S["Stock Balance + Stock Dashboard"]
  end
```

## 6. Actualisation de la database articles

```mermaid
flowchart TD
  subgraph DB1[Creation ou enrichissement]
    A["Nouvel article / fiche incomplete"] --> B["Item"]
    B --> C["Item Category"]
    C --> D["Code article auto si vide"]
    D --> E["Item Group + nom FR + UOM"]
  end

  subgraph DB2[Donnees techniques]
    E --> F["Poids, volume, longueur, largeur, hauteur"]
    F --> G["Specifications dynamiques: taille, capacite, finition, tension"]
    G --> H["Packaging Profiles"]
    H --> I{"Packaging valide ?"}
    I -->|Non| J["Corriger default, UOM, doublons"]
    J --> H
    I -->|Oui| K["HS code + Douane Material"]
  end

  subgraph DB3[Prix et publication]
    K --> L["Buying Price Builder / Item Price buying"]
    L --> M["Pricing Builder / Item Price selling"]
    M --> N["Images / catalogue si disponible"]
    N --> O{"Fiche complete ?"}
    O -->|Non| P["Completer champs manquants"]
    P --> E
    O -->|Oui| Q["Catalogue Prix Articles"]
    Q --> R["Disponible pour achat, vente, stock, logistique"]
  end
```

## 7. Creation de contenu marketing terrain

```mermaid
flowchart TD
  subgraph MK1[Capture terrain]
    A["Operation terrain"] --> B{"Origine"}
    B -->|Installation| C["Project / SIG"]
    B -->|Livraison| D["Delivery Note / Forecast Load Plan"]
    B -->|SAV| E["SAV Ticket"]
    B -->|Visite commerciale| F["Partner Campaign Target"]
    C --> G["Photos, videos, temoignage, localisation"]
    D --> G
    E --> G
    F --> G
  end

  subgraph MK2[Validation]
    G --> H["Joindre aux documents ou Communication"]
    H --> I["Selection contenu exploitable"]
    I --> J{"Valide marketing ?"}
    J -->|Non| K["Demander reprise / correction"]
    K --> G
    J -->|Oui| L["Preparateur campagne"]
  end

  subgraph MK3[Diffusion]
    L --> M["Campaign Builder"]
    M --> N{"Canal"}
    N -->|Email| O["Email preview"]
    N -->|WhatsApp| P["Template / click-to-chat / webhook"]
    N -->|Call| Q["Script appel"]
    N -->|Visit| R["Agenda visite + ToDo"]
    N -->|Other| S["Notes manuelles"]
    O --> T["Campaign Manager"]
    P --> T
    Q --> T
    R --> T
    S --> T
    T --> U["Diffusion + suivi statuts cibles"]
  end
```

## 8. Suivi de projet d'installation d'ascenseur

```mermaid
flowchart TD
  subgraph IP1[Avant-vente]
    A["Lead / Opportunity installation"] --> B["Opportunity Pipeline"]
    B --> C["CRM Business Type = Installation"]
    C --> D["Visite / donnees site"]
    D --> E["Support BET / Dimensioning Set"]
    E --> F["Pricing Sheet"]
    F --> G["Quotation"]
    G --> H{"Client accepte ?"}
    H -->|Non| I["Relance / revision / perdu"]
    I --> B
  end

  subgraph IP2[Commande et lancement]
    H -->|Oui| J["Contract"]
    J --> K["Sales Order"]
    K --> L["Validation acompte / conditions"]
    L --> M["Creer Project lie"]
    M --> N["Project Pipeline"]
  end

  subgraph IP3[Execution SIG]
    N --> O["Taches installation + planning equipe"]
    O --> P["Achats / logistique si necessaire"]
    P --> Q["SIG: site, geolocalisation, QC template"]
    Q --> R["Installation"]
    R --> S["Mobile QC / checklist"]
    S --> T{"QC complet ?"}
    T -->|Non| U["Completion guard: projet bloque"]
    U --> R
    T -->|Oui| V["Mise en service"]
  end

  subgraph IP4[Cloture]
    V --> W["Reception client"]
    W --> X["Project Complete"]
    X --> Y["Facturation finale / reporting marge"]
  end
```

## 9. Suivi des demandes SAV

```mermaid
flowchart TD
  subgraph SV1[Capture reclamation]
    A["Reclamation client"] --> B["SAV Ticket"]
    B --> C["reported_via: Appel, Portail, Email, WhatsApp"]
    C --> D["Auto-fill depuis Serial No / Sales Order / Delivery Note / Customer"]
    D --> E["Calcul garantie, jours depuis livraison, recurrence, severite"]
  end

  subgraph SV2[Qualification]
    E --> F{"Defect type"}
    F -->|Installation Defect| G["Project obligatoire"]
    F -->|Product Defect| H["Item obligatoire"]
    F -->|Supplier Defect| I["Purchase Receipt obligatoire"]
    F -->|Other| J["Description anomalie"]
    G --> K["Assign Technician"]
    H --> K
    I --> K
    J --> K
  end

  subgraph SV3[Intervention]
    K --> L["Status = Assigned + notification"]
    L --> M["Task intervention"]
    M --> N["Status = In Progress"]
    N --> O{"Piece a remplacer / retour ?"}
    O -->|Oui| P["Stock Entry depuis SAV Ticket"]
    O -->|Non| Q["Intervention terrain"]
    P --> Q
  end

  subgraph SV4[Resolution]
    Q --> R["Resolution report"]
    R --> S{"Rapport renseigne ?"}
    S -->|Non| T["Guardrail: resolution bloquee"]
    T --> R
    S -->|Oui| U["Status = Resolved"]
    U --> V{"Manager accepte ?"}
    V -->|Non| W["Reject closure -> In Progress"]
    W --> Q
    V -->|Oui| X["Status = Closed + closure_date"]
    X --> Y["SAV Dashboard + retour satisfaction"]
  end
```

## 10. Montee en competence RH

```mermaid
flowchart TD
  subgraph HR1[Conception]
    A["Besoin competence"] --> B["Training Level"]
    B --> C["Training Program"]
    C --> D["Training Modules"]
    D --> E["Files, notes, liens, duree estimee"]
    E --> F{"Quiz requis ?"}
    F -->|Oui| G["Training Quiz + Questions + Options"]
    F -->|Non| H["Programme pret"]
    G --> H
  end

  subgraph HR2[Assignation]
    H --> I["Training Program Assignment"]
    I --> J["Employee"]
    J --> K["Training Center"]
  end

  subgraph HR3[Apprentissage]
    K --> L["Ouvrir module"]
    L --> M["Mark Module Studied"]
    M --> N{"Quiz requis pour valider ?"}
    N -->|Non| O["Employee Training Progress"]
    N -->|Oui| P["Start Quiz Attempt"]
    P --> Q["Submit answers"]
    Q --> R{"Score >= seuil ?"}
    R -->|Non| S["Tentative echouee / reprendre"]
    S --> P
    R -->|Oui| O
  end

  subgraph HR4[Performance]
    O --> T["Training Leaderboard"]
    T --> U["Performance Metrics / Snapshots"]
    U --> V["Appraisal / evolution ressource"]
  end
```

## 11. Demande de support technique BET

```mermaid
flowchart TD
  subgraph BET1[Origine demande]
    A["Besoin etude / dimensionnement / validation"] --> B{"Document source"}
    B -->|Avant-vente| C["Opportunity"]
    B -->|Devis| D["Pricing Sheet"]
    B -->|Projet| E["Project"]
    B -->|Incident| F["SAV Ticket"]
  end

  subgraph BET2[Formalisation]
    C --> G["Task / ToDo BET"]
    D --> G
    E --> G
    F --> G
    G --> H["Joindre plans, mesures, contraintes, photos"]
    H --> I{"Type support"}
    I -->|Dimensionnement| J["Dimensioning Set"]
    I -->|Validation technique| K["Analyse BET"]
    I -->|Non-conformite| L["QC / SAV review"]
  end

  subgraph BET3[Sortie]
    J --> M["Liste articles + quantites + regles"]
    K --> N["Avis technique / validation"]
    L --> O["Actions correctives"]
    M --> P["MAJ Pricing Sheet / Quotation"]
    N --> P
    O --> Q["MAJ Project / SAV Ticket"]
    P --> R["Reponse au demandeur"]
    Q --> R
    R --> S["Cloture Task BET"]
  end
```

## 12. Operation de vente - Distribution B2B

```mermaid
flowchart TD
  subgraph B2B1[CRM]
    A["Lead / Prospect / Customer"] --> B["CRM Business Type = Distribution"]
    B --> C["CRM Segment: Grossiste, Revendeur, Installateur"]
    C --> D["Opportunity Pipeline"]
    D --> E{"Besoin qualifie ?"}
    E -->|Non| F["Relance / perdu"]
  end

  subgraph B2B2[Offre]
    E -->|Oui| G["Pricing Sheet"]
    G --> H["Articles, quantites, prix, remise, commission"]
    H --> I["Quotation"]
    I --> J{"Client accepte ?"}
    J -->|Non| K["Revision devis"]
    K --> G
  end

  subgraph B2B3[Commande et livraison]
    J -->|Oui| L["Sales Order"]
    L --> M["Sales Order Pipeline"]
    M --> N["Notification Stock Manager"]
    N --> O{"Stock disponible ?"}
    O -->|Non| P["Material Request / Purchase flow"]
    O -->|Oui| Q["Delivery Note"]
    P --> Q
    Q --> R{"Livraison geree par Orderlift ?"}
    R -->|Oui| S["Forecast Load Plan / Delivery Trip"]
    R -->|Non| T["Pickup client"]
    S --> U["Delivered"]
    T --> U
  end

  subgraph B2B4[Finance]
    U --> V["Sales Invoice"]
    V --> W["Payment Entry"]
    W --> X["Commission sync si agent"]
    X --> Y["Sale Financial Dashboard"]
  end
```

## 13. Operation de vente - Installation B2C / projets

```mermaid
flowchart TD
  subgraph B2C1[Qualification]
    A["Lead B2C / projet"] --> B["CRM Business Type = Installation"]
    B --> C["CRM Segment: Individu / Promoteur / Installateur"]
    C --> D["Opportunity Pipeline"]
    D --> E["Visite site / collecte besoin"]
    E --> F["Support BET"]
  end

  subgraph B2C2[Devis]
    F --> G["Dimensioning Set"]
    G --> H["Pricing Sheet"]
    H --> I["Quotation projet"]
    I --> J{"Accord client ?"}
    J -->|Non| K["Revision technique ou commerciale"]
    K --> F
  end

  subgraph B2C3[Contrat et execution]
    J -->|Oui| L["Contract"]
    L --> M["Sales Order"]
    M --> N["Acompte / validation finance"]
    N --> O["Project installation"]
    O --> P["Planning equipe + tasks"]
    P --> Q["Achats / logistique"]
    Q --> R["Installation"]
  end

  subgraph B2C4[Controle et cloture]
    R --> S["SIG QC checklist"]
    S --> T{"QC + reception OK ?"}
    T -->|Non| U["Actions correctives"]
    U --> R
    T -->|Oui| V["Mise en service"]
    V --> W["Facture finale + paiement"]
    W --> X["Project Complete"]
  end
```

## 14. Innovation et amelioration continue

```mermaid
flowchart TD
  subgraph IC1[Detection]
    A["Inefficacite, bug metier ou idee"] --> B{"Source"}
    B -->|Utilisateur| C["ToDo / Task"]
    B -->|KPI| D["Dashboards CRM, Pricing, Stock, Logistics, Finance"]
    B -->|Projet / SAV| E["Project / SAV feedback"]
    B -->|Management| F["Reunion amelioration"]
  end

  subgraph IC2[Analyse]
    C --> G["Qualifier probleme"]
    D --> G
    E --> G
    F --> G
    G --> H["Mesurer impact: cout, delai, marge, satisfaction"]
    H --> I["Prioriser"]
    I --> J{"Decision"}
    J -->|Rejeter| K["Archiver avec raison"]
    J -->|Quick win| L["Action operationnelle"]
    J -->|Config ERP| M["Status Control / Menu / Permissions"]
    J -->|Dev app| N["Specification changement Orderlift"]
  end

  subgraph IC3[Mise en oeuvre]
    L --> O["Implementer"]
    M --> O
    N --> O
    O --> P["Tester avec utilisateurs"]
    P --> Q{"Resultat OK ?"}
    Q -->|Non| R["Requalifier / corriger"]
    R --> G
    Q -->|Oui| S["Deployer / documenter"]
    S --> T["Suivi KPI mensuel"]
  end
```

## 15. Lancement d'une nouvelle campagne commerciale

```mermaid
flowchart TD
  subgraph CP1[Preparation]
    A["Objectif campagne"] --> B["Cible: segment, client, prospect, zone, articles"]
    B --> C["Campaign Builder"]
    C --> D["Partner Campaign"]
    D --> E{"Campaign Action Type"}
    E -->|Email| F["Sujet + body email"]
    E -->|WhatsApp| G["Message + Twilio ou webhook si auto"]
    E -->|Call| H["Script appel"]
    E -->|Visit| I["Sujet visite + agenda"]
    E -->|Other| J["Notes manuelles"]
  end

  subgraph CP2[Cibles et preflight]
    F --> K["Partner Campaign Targets"]
    G --> K
    H --> K
    I --> K
    J --> K
    K --> L["Preview placeholders par cible"]
    L --> M["Preflight check"]
    M --> N{"Blocage ?"}
    N -->|Oui| O["Corriger contact, contenu, statut, provider"]
    O --> M
  end

  subgraph CP3[Execution]
    N -->|Non| P["Campaign Manager"]
    P --> Q{"Execution"}
    Q -->|Email| R["Send / schedule Email Queue"]
    Q -->|WhatsApp| S["Click-to-chat ou automated send"]
    Q -->|Call| T["Marquer contacte"]
    Q -->|Visit| U["Creer / update ToDo visite"]
    Q -->|Other| V["Suivi manuel"]
  end

  subgraph CP4[Conversion]
    R --> W["Update target status"]
    S --> W
    T --> W
    U --> W
    V --> W
    W --> X{"Interet commercial ?"}
    X -->|Non| Y["Completed / Closed"]
    X -->|Oui| Z["Create Prospect / Opportunity / Quotation"]
    Z --> AA["Campaign rollup sur documents CRM/Sales"]
  end
```

## V2 a produire ensuite

Les procedures 16 a 25 peuvent etre ajoutees dans un second document ou une section V2:

- Validation financiere des achats et engagements.
- Gestion des commissions commerciales.
- Gestion des reclamations client hors SAV technique.
- Cloture financiere d'un projet.
- Controle qualite installation / livraison.
- Benchmark marche structure.
- Creation / validation fournisseur.
- Gestion des sous-traitants installation / transport.
- Gestion des droits utilisateurs ERP.
- Reporting mensuel de performance.
