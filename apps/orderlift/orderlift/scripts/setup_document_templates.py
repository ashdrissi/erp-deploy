"""Seed the standard project document templates from the supplied field forms."""

from __future__ import annotations

import frappe
from frappe.utils import cint


def _field(label, fieldtype="Data", source_field="", **kwargs):
    return {
        "field_label": label,
        "fieldtype": fieldtype,
        "source_field": source_field,
        **kwargs,
    }


TEMPLATES = (
    {
        "template_name": "Prise des mesures",
        "print_title": "Fiche de prise de mesure",
        "print_header": "<p>Releve de mesure du site d'installation.</p>",
        "fields": (
            _field("Information du projet", "Section Break"),
            _field("Responsable du projet", source_field="custom_project_owner"),
            _field("Date", "Date", "expected_start_date"),
            _field("Projet N°", source_field="name"),
            _field("Réf. Fichier", source_field="custom_deal_abbreviation"),
            _field("Client", source_field="customer.customer_name"),
            _field("Adresse", "Small Text", "custom_site_address"),
            _field("Interlocuteur", source_field="contact_person"),
            _field("Information d'ascenseur", "Section Break"),
            _field("Type d'ascenseur"),
            _field("Personnes", "Int"),
            _field("Niveaux", "Int"),
            _field("Gaine disponible", "Check"),
            _field("Description", "Text"),
            _field("Prérequis du site", "Section Break"),
            _field("Fosse et plancher de fosse", "Check"),
            _field("Voile de gaine en béton", "Check"),
            _field("Hauteur libre sous plafond", "Check"),
            _field("Nettoyage de la cage d'ascenseur", "Check"),
            _field("Nettoyage et étanchéité de la fosse", "Check"),
            _field("Trappe salle des machines / contrôle", "Check"),
            _field("Alimentation électrique de chantier", "Check"),
            _field("Alimentation électrique triphasée", "Check"),
            _field("Barrières de sécurité à tous les étages", "Check"),
            _field("Espace de stockage couvert", "Check"),
            _field("Accès au site", "Check"),
            _field("Commentaires sur les prérequis", "Text"),
            _field("Mesures de la gaine", "Section Break"),
            _field("Largeur nette (cm)", "Float"),
            _field("Profondeur nette (cm)", "Float"),
            _field("Diagonale (cm)", "Float"),
            _field("Hauteur totale (m)", "Float"),
            _field("Hauteur niveau supérieur (cm)", "Float"),
            _field("Hauteur de fosse (cm)", "Float"),
            _field("Hauteur du local technique (m)", "Float"),
            _field("Schéma", "Attach Image"),
            _field("Commentaires", "Text"),
            _field("Signatures", "Section Break"),
            _field("Signature chargé de projet", "Signature"),
            _field("Signature responsable installation", "Signature"),
            _field("Signature client", "Signature"),
        ),
    },
    {
        "template_name": "Information du Projet",
        "print_title": "Information du Projet",
        "print_header": "<p>Informations techniques de l'ascenseur et du site.</p>",
        "fields": (
            _field("Information du projet", "Section Break"),
            _field("Responsable du projet", source_field="custom_project_owner"),
            _field("Date", "Date", "expected_start_date"),
            _field("Projet N°", source_field="name"),
            _field("Réf. Fichier", source_field="custom_deal_abbreviation"),
            _field("Client", source_field="customer.customer_name"),
            _field("Adresse", "Small Text", "custom_site_address"),
            _field("Interlocuteur", source_field="contact_person"),
            _field("Information d'ascenseur", "Section Break"),
            _field("Type"),
            _field("Niveaux", "Int"),
            _field("Personnes", "Int"),
            _field("Détails de cabine", "Section Break"),
            _field("Design", "Select", options="Standard\nPanoramique\nPersonnalisé"),
            _field("Référence cabine"),
            _field("Dimensions cabine (cm)", "Data"),
            _field("Description cabine", "Text"),
            _field("Boutons cabine", "Select", options="Poussoire\nTactile"),
            _field("Numérotation des boutons"),
            _field("Boutons palières", "Select", options="Poussoire\nTactile\nAvec afficheur\nSans afficheur"),
            _field("Accès", "Select", options="Un\nDeux en Face\nÀ droite\nÀ gauche\nBus"),
            _field("Porte", "Select", options="Automatique\nBattante\nPanoramique\nX + 1"),
            _field("Dimension porte (cm)", "Data"),
            _field("Matériau", "Select", options="Inox\nEpoxy"),
            _field("Coupe feu", "Check"),
            _field("Ouverture", "Select", options="Droite\nGauche\nCentrale"),
            _field("Géométrie", "Section Break"),
            _field("Gaine", "Check"),
            _field("Largeur gaine (cm)", "Float"),
            _field("Profondeur gaine (cm)", "Float"),
            _field("Hauteur totale (m)", "Float"),
            _field("Local technique", "Check"),
            _field("Hauteur local technique (m)", "Float"),
            _field("Fosse", "Check"),
            _field("Hauteur fosse (cm)", "Float"),
            _field("Structure", "Check"),
            _field("Largeur structure (cm)", "Float"),
            _field("Profondeur structure (cm)", "Float"),
            _field("Hauteur structure (m)", "Float"),
            _field("Couleur structure"),
            _field("Habillage", "Select", options="Verre\nAlucobond"),
            _field("Couleur habillage"),
            _field("Détails d'ascenseur", "Section Break"),
            _field("Type de manutention", "Select", options="Électrique\nHydraulique"),
            _field("Marque", "Select", options="GMV\nAkış\nGem\nPrimo\nMontanari\nAutre"),
            _field("Vitesse", "Data"),
            _field("Variateur de vitesse", "Select", options="VVF\n2V"),
            _field("Armoire", "Select", options="Hedefsan\nArkel\nAutre"),
            _field("Autres détails", "Text"),
            _field("Note", "Small Text", default_value="Si l'information n'est pas disponible, ne remplissez pas."),
            _field("Signatures", "Section Break"),
            _field("Signature responsable du projet", "Signature"),
            _field("Signature client", "Signature"),
        ),
    },
)


def run(dry_run: int = 1) -> dict:
    """Create or update the two standard Project document templates."""
    dry_run = cint(dry_run)
    summary = {"created": [], "updated": [], "skipped": []}
    for definition in TEMPLATES:
        name = definition["template_name"]
        exists = frappe.db.exists("Orderlift Document Template", name)
        if dry_run:
            summary["updated" if exists else "created"].append(name)
            continue

        template = frappe.get_doc("Orderlift Document Template", name) if exists else frappe.new_doc(
            "Orderlift Document Template"
        )
        template.template_name = name
        template.is_active = 1
        template.display_order = 100 if name == "Prise des mesures" else 110
        template.print_title = definition["print_title"]
        template.print_header = definition["print_header"]
        template.show_signature_block = 0
        template.set("targets", [{"target_doctype": "Project"}])
        template.set("fields", [])
        for index, field in enumerate(definition["fields"], start=1):
            template.append(
                "fields",
                {
                    "field_key": field.get("field_key") or "",
                    "field_label": field["field_label"],
                    "fieldtype": field["fieldtype"],
                    "options": field.get("options", ""),
                    "source_field": field.get("source_field", ""),
                    "is_required": field.get("is_required", 0),
                    "default_value": field.get("default_value", ""),
                    "display_order": index,
                },
            )
        template.set("statuses", [{"status_label": "Draft", "color": "Gray", "is_default": 1, "display_order": 1}])
        template.save(ignore_permissions=True)
        summary["updated" if exists else "created"].append(template.name)

    if not dry_run:
        frappe.db.commit()
    return summary
