# Logigrammes Orderlift - version demarrage 0-6 mois

Source analysee: `import-lists/Organisation et Logigramme _version démarrage.docx`.

Cette version reprend la logique du document de demarrage: equipe reduite, DG implique, peu de validations, execution rapide, et separation claire des roles operationnels.

## Roles de demarrage

- Direction Generale.
- Responsable Vente Distribution.
- Responsable Vente Installation.
- Responsable Achat.
- Responsable Stock.
- Responsable Projet installation et maintenance.
- Responsable Admin, pricing et importation.
- Responsable Logistique.
- BET interne ou externe.
- AC1: agent commercial partenaire autonome, generalement externe et commissionne.
- AC2: agent commercial coordination et suivi, lien entre clients/partenaires non qualifies digitalement et le systeme.
- AC3: agent commercial point de vente, rattache a un showroom ou depot.

## Carte des processus

```mermaid
flowchart TD
  P01["P01 Gestion des achats"]
  P02["P02 Pricing"]
  P03["P03 Benchmark prix marche"]
  P04["P04 Recrutement intermediaires"]
  P05["P05 Gestion logistique"]
  P06["P06 Entrees / sorties stock"]
  P07["P07 Base articles"]
  P08["P08 Vente Distribution"]
  P09["P09 Vente Installation"]
  P10["P10 Campagnes commerciales"]
  P11["P11 Support technique BET"]
  P12["P12 Creation contenu marketing"]
  P13["P13 SAV"]
  P14["P14 Developpement RH"]
  P15["P15 Administration / Finance / RH"]
  P16["P16 Pilotage et tableaux de bord"]

  P07 --> P02
  P03 --> P02
  P02 --> P08
  P02 --> P09
  P04 --> P08
  P04 --> P09
  P08 --> P06
  P08 --> P05
  P09 --> P01
  P09 --> P05
  P09 --> P13
  P11 --> P08
  P11 --> P09
  P12 --> P10
  P15 --> P01
  P15 --> P08
  P15 --> P09
  P01 --> P06
  P06 --> P16
  P08 --> P16
  P09 --> P16
  P13 --> P16
```

## P01 - Gestion des achats

```mermaid
flowchart TD
  A["Besoin stock ou projet"] --> B["Consultation fournisseurs"]
  B --> C["Analyse prix et delais"]
  C --> D{"Validation achat"}
  D -->|Admin / Stock valide| E["Commande fournisseur"]
  D -->|Refuse ou incomplet| C
  E --> F["Validation paiement"]
  F --> G{"DG valide paiement ?"}
  G -->|Non| H["Achat en attente"]
  G -->|Oui| I["Reception marchandises"]
  I --> J["Controle reception"]
  J --> K{"Conforme ?"}
  K -->|Non| L["Litige fournisseur / correction"]
  K -->|Oui| M["Entree stock ERP"]
  M --> N["Stock disponible"]

  R1["Resp Stock"] -. declenche .-> A
  R2["Resp Achat"] -. execute .-> B
  R3["Admin / Resp Stock"] -. valide .-> D
  R4["DG"] -. valide .-> F
```

## P02 - Pricing

```mermaid
flowchart TD
  A["Notification changement prix achat"] --> B["Mise a jour prix achat"]
  B --> C["Validation et consolidation prix achat"]
  C --> D["Mise a jour logiques de charges"]
  D --> E["Integration sortie P03 benchmark marche"]
  E --> F["Calcul prix de vente"]
  F --> G{"Validation DG"}
  G -->|Non| H["Correction pricing"]
  H --> F
  G -->|Oui| I["Publication automatique ERP"]
  I --> J["Prix disponibles pour devis et catalogue"]

  R1["Resp Achat / societe mere"] -. informe .-> A
  R2["Admin pricing importation"] -. consolide .-> C
  R3["DG"] -. valide .-> G
```

## P03 - Benchmark prix marche

```mermaid
flowchart TD
  A["ERP notifie liste articles cibles"] --> B["Collecte prix marche"]
  B --> C["Saisie / consolidation donnees marche"]
  C --> D["Analyse et recommandations ERP"]
  D --> E["Liste recommandee des prix de vente"]
  E --> F["Alimentation P02 Pricing"]

  R1["Vente Distribution"] -. collecte .-> B
  R2["AC1 / AC2 / AC3"] -. collecte terrain .-> B
  R3["ERP"] -. analyse .-> D
  R4["Vente Distribution"] -. consolide .-> E
```

## P04 - Recrutement intermediaires

```mermaid
flowchart TD
  A["Identification intermediaire"] --> B["Qualification profil"]
  B --> C{"Validation DG / Vente Distribution"}
  C -->|Non| D["Archivage candidat"]
  C -->|Oui| E["Convention avec AC1"]
  E --> F["Formation et partage catalogue / prix min / prix normal"]
  F --> G{"Agent qualifie digitalement ?"}
  G -->|Non| H["Affecter AC2 de suivi"]
  G -->|Oui| I["Creation compte ERP"]
  H --> J["Mise au point commerciale"]
  I --> J
  J --> K["Agent operationnel"]

  R1["DG / Vente Distribution"] -. identifie et valide .-> C
  R2["RH"] -. forme .-> F
  R3["AC2"] -. assiste .-> H
```

## P05 - Gestion logistique

```mermaid
flowchart TD
  A["Demande transport"] --> B["Planification moyen de transport"]
  B --> C["Confirmation moyen de transport"]
  C --> D["Notification responsable point A"]
  D --> E["Livraison / transfert"]
  E --> F["Confirmation reception point B"]
  F --> G{"Reception confirmee ?"}
  G -->|Non| H["Traitement ecart / relance"]
  H --> E
  G -->|Oui| I["Cloture logistique"]
  I --> J["Evaluation par responsable point B"]

  R1["Stock / Projet"] -. demande .-> A
  R2["Logistique"] -. planifie et livre .-> B
  R3["Stock / Achat / Client"] -. confirme .-> F
```

## P06 - Entrees / sorties stock

```mermaid
flowchart TD
  A["Notification mouvement stock"] --> B{"Type mouvement"}

  B -->|Entree| C["Preparation bon d'entree ERP"]
  C --> D["Preparation equipe dechargement optionnelle"]
  D --> E["Controle marchandises"]
  E --> F{"Conforme ?"}
  F -->|Non| G["Ecart / rejet / correction"]
  F -->|Oui| H["Classement articles depot"]
  H --> I["Mise a jour ERP"]
  I --> J["Inventaire / stock disponible"]

  B -->|Sortie| K["Preparation bon de sortie"]
  K --> L["Preparation bon de livraison"]
  L --> M["Preparation articles"]
  M --> N["Notification logistique"]
  N --> O["Chargement"]
  O --> P["Signature bon de sortie via ERP"]
  P --> Q["Stock decremente"]

  R1["ERP"] -. notifie suite commande ou requete .-> A
  R2["Stock"] -. execute .-> C
  R3["Logistique / Stock"] -. veille signature .-> P
```

## P07 - Base articles

```mermaid
flowchart TD
  A["Besoin nouvel article"] --> B["Creation Item ERP"]
  B --> C["Complement technique optionnel"]
  C --> D["Complement achat"]
  D --> E["Complement donnees douane / importation"]
  E --> F["Affectation local ou global"]
  F --> G{"Validation stock"}
  G -->|Non| H["Completer fiche article"]
  H --> C
  G -->|Oui| I["Activation ERP"]
  I --> J["Article utilisable achats, stock, pricing, vente"]

  R1["Vente / Projet / Stock"] -. declenche .-> A
  R2["Stock"] -. cree et valide .-> B
  R3["BET"] -. complete technique .-> C
  R4["Achat"] -. complete achat .-> D
  R5["Admin importation"] -. complete douane .-> E
  R6["Societe mere"] -. affecte .-> F
```

## P08 - Vente Distribution

```mermaid
flowchart TD
  subgraph S1[Sprint 1 - Opportunite]
    A["Creation opportunite"] --> B["Qualification optionnelle"]
    B --> C{"Support technique requis ?"}
    C -->|Oui| D["Support BET"]
    C -->|Non| E["Devis"]
    D --> E
    E --> F["Negociation"]
    F --> G{"Decision client"}
    G -->|Perdue| H["Motif perte"]
    H --> I["Cloture opportunite perdue"]
    G -->|Gagnee| J["Paiement avance"]
    J --> K["Confirmation paiement"]
    K --> L["Creation Sales Order"]
    L --> M["Cloture opportunite gagnee"]
  end

  subgraph S2[Sprint 2 - Sales Order]
    L --> N["Verification stock"]
    N --> O{"Stock suffisant ?"}
    O -->|Non| P["Demande achat"]
    P --> Q["Reception stock"]
    O -->|Oui| R["Preparation commande"]
    Q --> R
    R --> S["Facturation"]
    S --> T["Encaissement"]
    T --> U["Livraison"]
    U --> V["Cloture Sales Order"]
  end

  R1["Vente Distribution / AC1 / AC2 / AC3 / IA / portail B2B"] -. cree .-> A
  R2["Client"] -. decide et paie .-> G
  R3["DG / Admin"] -. confirme paiement .-> K
  R4["Stock"] -. verifie et prepare .-> N
  R5["Logistique"] -. livre .-> U
```

## P09 - Vente Installation

```mermaid
flowchart TD
  subgraph S1[Sprint 1 - Opportunite]
    A["Creation opportunite installation"] --> B["Qualification + fiche detaillee besoin"]
    B --> C["Visite preliminaire optionnelle"]
    C --> D{"Support BET besoin ?"}
    D -->|Oui| E["Support technique elaboration besoin"]
    D -->|Non| F["Devis"]
    E --> F
    F --> G["Negociation"]
    G --> H{"Support BET explication client ?"}
    H -->|Oui| I["Explication technique client"]
    H -->|Non| J["Decision client"]
    I --> J
    J -->|Perdue| K["Motif + cloture opportunite"]
    J -->|Gagnee| L["Contrat signe"]
    L --> M["Paiement avance"]
    M --> N["Creation Project"]
    N --> O["Notification responsable projet ERP"]
    O --> P["Cloture opportunite gagnee"]
  end

  subgraph S2[Sprint 2 - Projet]
    N --> Q["Affectation equipe"]
    Q --> R["Visite complementaire"]
    R --> S["Conception projet detaille"]
    S --> T["Verification stock"]
    T --> U{"Stock suffisant ?"}
    U -->|Non| V["Demande achat"]
    V --> W["Reception / disponibilite"]
    U -->|Oui| X["Livraison chantier partielle ou complete"]
    W --> X
    X --> Y["Installation partielle ou complete"]
    Y --> Z["Paiement echeance"]
    Z --> AA["Confirmation paiement"]
    AA --> AB{"Travaux termines ?"}
    AB -->|Non| X
    AB -->|Oui| AC["Mise en service"]
    AC --> AD["Facturation"]
    AD --> AE["Paiement final + confirmation"]
    AE --> AF["Affectation equipe SAV garantie"]
    AF --> AG["SAV periode garantie"]
    AG --> AH["Cloture projet"]
  end

  R1["Vente Installation / AC2 / AC1 / AC3 / IA / portail"] -. cree .-> A
  R2["BET"] -. support .-> E
  R3["DG / Imad si VIP"] -. appuie negociation .-> G
  R4["Resp Projet"] -. execute .-> Q
  R5["Admin / DG"] -. confirme paiements .-> AA
```

## P10 - Campagnes commerciales

```mermaid
flowchart TD
  A["Choix cible"] --> B["Creation et preparation campagne"]
  B --> C{"Campagne digitale ?"}
  C -->|Oui| D["Creation contenu"]
  C -->|Non| E["Preparation script / action terrain"]
  D --> F["Diffusion"]
  E --> F
  F --> G{"Leads crees ?"}
  G -->|Non| H["Suivi campagne"]
  G -->|Oui| I["Creation Leads"]
  I --> J["Affectation leads / opportunites"]
  J --> K["Vers P08 ou P09"]

  R1["Vente Distribution / Vente Installation / AC2"] -. cible .-> A
  R2["Marketing / IA"] -. contenu .-> D
```

## P11 - Support technique BET

```mermaid
flowchart TD
  A["Demande support technique"] --> B["Analyse BET"]
  B --> C["Etude technique"]
  C --> D["Transmission resultat"]
  D --> E{"Demande resolue ?"}
  E -->|Non| F["Complement information"]
  F --> B
  E -->|Oui| G["Retour au demandeur"]

  R1["Vente / Projet"] -. demande .-> A
  R2["BET"] -. analyse et transmet .-> B
```

## P12 - Creation contenu marketing

```mermaid
flowchart TD
  A["Notification periodique terrain ERP"] --> B["Demande specifique marketing optionnelle"]
  B --> C["Collecte photos / videos"]
  A --> C
  C --> D["Renseignement contexte operation"]
  D --> E["Creation contenu IA"]
  E --> F{"Validation marketing"}
  F -->|Non| G["Correction contenu"]
  G --> E
  F -->|Oui| H["Publication"]

  R1["Projet / Stock / Logistique"] -. collecte .-> C
  R2["Marketing"] -. valide et publie .-> F
  R3["IA"] -. cree .-> E
```

## P13 - SAV

```mermaid
flowchart TD
  A["Reclamation client"] --> B["Ticket SAV ERP"]
  B --> C["Affectation responsable / technicien"]
  C --> D["Intervention"]
  D --> E["Compte rendu intervention"]
  E --> F{"Probleme resolu ?"}
  F -->|Non| G["Nouvelle intervention / escalation"]
  G --> D
  F -->|Oui| H["Cloture SAV"]
  H --> I["Historique SAV client / projet"]

  R1["Client"] -. reclame .-> A
  R2["Responsable Projet"] -. affecte et cloture .-> C
  R3["Technicien"] -. intervient .-> D
```

## P14 - Developpement RH

```mermaid
flowchart TD
  A["Besoin formation"] --> B["Formation ou partage materiel en ligne"]
  B --> C["Quiz"]
  C --> D["Evaluation manager"]
  D --> E{"Niveau atteint ?"}
  E -->|Non| F["Renforcement / nouvelle formation"]
  F --> B
  E -->|Oui| G["Certification RH"]
  G --> H["Ressource qualifiee"]

  R1["RH / Concerne"] -. declenche .-> A
  R2["RH / Manager / Concerne"] -. forme .-> B
  R3["IA"] -. genere quiz .-> C
  R4["Manager"] -. evalue .-> D
```

## P15 - Administration / Finance / RH

```mermaid
flowchart TD
  A["Operations administratives"] --> B{"Nature operation"}
  B -->|Paiement fournisseur / achat| C["Validation paiements"]
  B -->|Comptabilite| D["Comptabilite"]
  B -->|Paie| E["Paie RH"]
  B -->|Commissions| F["Calcul / validation commissions"]
  B -->|Reporting| G["Reporting admin"]

  C --> H{"DG / Admin valide ?"}
  H -->|Non| I["Blocage / correction"]
  H -->|Oui| J["Paiement execute"]
  D --> K["Documents comptables ERP"]
  E --> L["Payroll / Salary Slip"]
  F --> M["Commission a payer / payee"]
  G --> N["Donnees pour pilotage P16"]
  J --> N
  K --> N
  L --> N
  M --> N

  R1["Admin"] -. pilote .-> C
  R2["RH"] -. gere paie .-> E
  R3["DG"] -. valide paiements sensibles .-> H
```

## P16 - Pilotage et tableaux de bord

```mermaid
flowchart TD
  A["Collecte donnees ERP"] --> B["Analyse KPI"]
  B --> C{"Ecart ou alerte ?"}
  C -->|Non| D["Suivi mensuel"]
  C -->|Oui| E["Actions correctives"]
  E --> F{"Besoin projet amelioration ?"}
  F -->|Non| G["Action operationnelle immediate"]
  F -->|Oui| H["Projet amelioration / innovation"]
  G --> I["Suivi execution"]
  H --> I
  I --> A

  R1["ERP"] -. collecte .-> A
  R2["DG"] -. analyse et decide .-> B
  R3["Concerne"] -. execute .-> G
```

## Ecarts importants avec la version V1 precedente

- Le fichier de demarrage contient 16 processus, pas 15.
- `Benchmark prix marche` est separe du `Pricing` en P03.
- `Administration / Finance / RH` et `Pilotage` sont deja inclus dans la version demarrage.
- Les procedures sont volontairement plus courtes: peu de validations, DG implique, execution rapide.
- Les flux Vente Distribution et Vente Installation sont decoupes en deux sprints: opportunite puis execution commande/projet.
- Les agents AC1, AC2 et AC3 sont centraux dans les ventes, campagnes et recrutement intermediaires.
