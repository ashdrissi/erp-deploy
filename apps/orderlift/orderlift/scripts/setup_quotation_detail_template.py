"""One-shot creation of the standard dynamic Quotation detail template.

This is intentionally not registered in ``after_migrate``. Run it explicitly when
the commercial proposal template should be created or refreshed.
"""

from __future__ import annotations

import frappe
from frappe.utils import cint


TEMPLATE_NAME = "Orderlift Proposal - Ascenseur"


def _block(label, block_type="Paragraph", **kwargs):
    return {"block_label": label, "block_type": block_type, **kwargs}


BLOCKS = (
    _block("Offre commerciale", "Heading", default_value="OFFRE D'ETUDE, FOURNITURE ET INSTALLATION D'UN ASCENSEUR"),
    _block("A l'attention de", "Quotation Field", source_field="customer_name", is_required=1),
    _block("Date", "Quotation Field", source_field="transaction_date"),
    _block("Projet", "Quotation Field", source_field="custom_deal_abbreviation"),
    _block(
        "Introduction",
        "Manual Area",
        default_value=(
            "Nous faisons suite a votre demande de cotation et vous prions de bien vouloir trouver ci-joint "
            "notre meilleure offre pour l'etude, la fourniture et l'installation de votre ascenseur."
        ),
    ),
    _block("Page 2", "Page Break"),
    _block("Description technique", "Heading", default_value="DESCRIPTION TECHNIQUE"),
    _block("Type d'ascenseur", "Annex Field", annex_template="Information du Projet", annex_field_key="type"),
    _block("Charge / personnes", "Annex Field", annex_template="Information du Projet", annex_field_key="personnes"),
    _block("Niveaux", "Annex Field", annex_template="Information du Projet", annex_field_key="niveaux"),
    _block("Acces", "Annex Field", annex_template="Information du Projet", annex_field_key="acces"),
    _block("Type de manutention", "Annex Field", annex_template="Information du Projet", annex_field_key="type_de_manutention"),
    _block("Marque", "Annex Field", annex_template="Information du Projet", annex_field_key="marque"),
    _block("Vitesse", "Annex Field", annex_template="Information du Projet", annex_field_key="vitesse"),
    _block("Caracteristiques generales", "Manual Area", default_value="Manoeuvre : Collective\nAlimentation : 380 Volts\nSysteme de securite : Parachute avec regulateur de vitesse"),
    _block("Caracteristiques de la structure", "Manual Area", default_value="Largeur x Profondeur : a confirmer par l'etude\nHabillage : panoramique ou au choix du client\nCouleur : au choix du client"),
    _block("Caracteristiques de la cabine", "Manual Area", default_value="Habillage : Inox\nAccessoires : main courante, eclairage, boite a boutons\nPanneau de commande : selon configuration retenue"),
    _block("Caracteristiques des portes", "Manual Area", default_value="Type : a definir\nPassage libre : a definir\nEquipements : indicateurs, boutons d'appel et protections"),
    _block("Page 3", "Page Break"),
    _block("Conditions generales", "Heading", default_value="CONDITIONS GENERALES"),
    _block("Entretien et service apres-vente", "Manual Area", default_value="Entretien trimestriel apres la premiere annee de garantie. Contrat separe."),
    _block("Garantie", "Manual Area", default_value="12 mois contre tous vices de matiere et de fabrication a partir de la date d'achevement du montage, sous reserve d'une utilisation normale et de la maintenance par le constructeur."),
    _block("Travaux a la charge du client", "Manual Area", default_value="Tous travaux necessaires au-dela de ce qui est presente dans l'offre, notamment arrivees electriques, disjoncteurs, prises, eclairage et preparation du site."),
)


def run(dry_run: int = 1, update_existing: int = 0) -> dict:
    dry_run = cint(dry_run)
    update_existing = cint(update_existing)
    existing = frappe.db.exists("Orderlift Quotation Detail Template", TEMPLATE_NAME)
    if dry_run:
        return {"created": [] if existing else [TEMPLATE_NAME], "updated": [TEMPLATE_NAME] if existing and update_existing else [], "skipped": [TEMPLATE_NAME] if existing and not update_existing else []}
    if existing and not update_existing:
        return {"created": [], "updated": [], "skipped": [TEMPLATE_NAME]}

    template = frappe.get_doc("Orderlift Quotation Detail Template", existing) if existing else frappe.new_doc("Orderlift Quotation Detail Template")
    template.template_name = TEMPLATE_NAME
    template.is_active = 1
    template.display_order = 100
    template.description = "Dynamic proposal pages inspired by the supplied Orderlift/Givas PDF references."
    template.set("blocks", [])
    for index, block in enumerate(BLOCKS, start=1):
        template.append(
            "blocks",
            {
                "block_label": block["block_label"],
                "block_type": block["block_type"],
                "source_field": block.get("source_field", ""),
                "annex_template": frappe.db.exists("Orderlift Document Template", block.get("annex_template", "")) or "",
                "annex_field_key": block.get("annex_field_key", ""),
                "default_value": block.get("default_value", ""),
                "options": block.get("options", ""),
                "is_required": block.get("is_required", 0),
                "allow_manual_override": 1,
                "display_order": index,
            },
        )
    template.save(ignore_permissions=True)
    frappe.db.commit()
    return {"created": [] if existing else [template.name], "updated": [template.name] if existing else [], "skipped": []}
