from __future__ import annotations

import frappe


LANGUAGE = "tr"

TURKISH_PRINT_TRANSLATIONS = {
    "Sales Quotation": "SATIŞ TEKLİFİ",
    "Sales Order": "SATIŞ SİPARİŞİ",
    "Delivery Note": "TESLİMAT İRSALİYESİ",
    "Sales Invoice": "SATIŞ FATURASI",
    "Purchase Order": "SATIN ALMA SİPARİŞİ",
    "Purchase Invoice": "ALIŞ FATURASI",
    "Purchase Receipt": "MAL KABULÜ",
    "Supplier Quotation": "TEDARİKÇİ TEKLİFİ",
    "Recipient": "Alıcı",
    "Information": "Bilgiler",
    "Phone": "Telefon",
    "Quotation No.": "Teklif No",
    "No.": "No",
    "Sales Representative": "Satış Temsilcisi",
    "Description": "Açıklama",
    "Qty": "Miktar",
    "Unit Price": "Birim Fiyat",
    "Unit Price Excl. Tax": "KDV Hariç Birim Fiyat",
    "Unit Price Incl. Tax": "KDV Dahil Birim Fiyat",
    "Amount Excl. Tax": "KDV Hariç Tutar",
    "Amount Incl. Tax": "KDV Dahil Tutar",
    "Tax": "KDV",
    "Discount": "İndirim",
    "Total Excl. Tax": "KDV Hariç Toplam",
    "Grand Total Incl. Tax": "KDV Dahil Genel Toplam",
    "Payment Terms": "Ödeme Şartları",
    "Terms and Conditions": "Genel Şartlar",
    "Seller (Signature and Stamp)": "Satıcı (İmza ve Kaşe)",
    "Customer (Signature and Stamp)": "Müşteri (İmza ve Kaşe)",
    "Buyer (Signature and Stamp)": "Alıcı (İmza ve Kaşe)",
    "Supplier (Signature and Stamp)": "Tedarikçi (İmza ve Kaşe)",
    "Approved for agreement": "Onay için uygundur",
    "Elevators and Equipment": "Asansörler ve Ekipmanlar",
    "Commercial Proposal": "Ticari Teklif",
    "Prepared For": "Hazırlanan",
    "Document No.": "Belge No",
    "Expected Delivery": "Planlanan Teslimat",
    "Due Date": "Vade Tarihi",
    "Shipment Date": "Sevkiyat Tarihi",
    "Created By": "Oluşturan",
    "Supplier": "Tedarikçi",
    "Received On": "Teslim Alınma Tarihi",
    "Incoterms": "Incoterms",
    "DEVIS DE VENTE": "SATIŞ TEKLİFİ",
    "DEVIS FOURNISSEUR": "TEDARİKÇİ TEKLİFİ",
    "BON DE COMMANDE": "SİPARİŞ FORMU",
    "BON DE LIVRAISON": "TESLİMAT İRSALİYESİ",
    "FACTURE DE VENTE": "SATIŞ FATURASI",
    "BON DE COMMANDE FOURNISSEUR": "TEDARİKÇİ SİPARİŞİ",
    "FACTURE D'ACHAT": "ALIŞ FATURASI",
    "RECEPTION DE MARCHANDISE": "MAL KABULÜ",
    "N° Devis": "Teklif No",
    "N° Document": "Belge No",
    "Document": "Belge",
    "Date": "Tarih",
    "Client": "Müşteri",
    "Informations": "Bilgiler",
    "Téléphone": "Telefon",
    "Telephone": "Telefon",
    "Désignation": "Açıklama",
    "Quantité": "Miktar",
    "Prix Unitaire": "Birim Fiyat",
    "Prix Unit. HT": "Birim Fiyat KDV Hariç",
    "Prix Unit. TTC": "Birim Fiyat KDV Dahil",
    "Montant HT": "Tutar KDV Hariç",
    "Montant TTC": "Tutar KDV Dahil",
    "Total": "Toplam",
    "Total HT": "Toplam KDV Hariç",
    "TOTAL TTC": "Genel Toplam KDV Dahil",
    "TVA": "KDV",
    "Remise": "İndirim",
    "Mode de paiement": "Ödeme şekli",
    "Selon conditions convenues": "Mutabık kalınan şartlara göre",
    "Conditions Générales": "Genel Şartlar",
    "Conditions Generales": "Genel Şartlar",
    "Vendeur (Signature et Cachet)": "Satıcı (İmza ve Kaşe)",
    "Client (Signature et Cachet)": "Müşteri (İmza ve Kaşe)",
    "Acheteur (Signature et Cachet)": "Alıcı (İmza ve Kaşe)",
    "Fournisseur (Signature et Cachet)": "Tedarikçi (İmza ve Kaşe)",
    "Bon pour accord": "Onay için uygundur",
    "Adresse": "Adres",
    "Email": "E-posta",
    "ICE": "Vergi No",
    "PROPOSITION COMMERCIALE": "TİCARİ TEKLİF",
    "Ascenseurs & Équipements": "Asansörler ve Ekipmanlar",
    "Ascenseurs & Equipements": "Asansörler ve Ekipmanlar",
    "Préparé pour": "Hazırlanan",
    "Prepare pour": "Hazırlanan",
    "Livraison prevue": "Planlanan teslimat",
    "Echeance": "Vade",
    "Condition de paiement": "Ödeme şartı",
}


def run(language: str = LANGUAGE) -> dict:
    if not frappe.db.table_exists("Translation"):
        return {"skipped": True, "reason": "missing Translation table"}

    created = 0
    updated = 0
    unchanged = 0
    for source_text, translated_text in TURKISH_PRINT_TRANSLATIONS.items():
        existing_name = frappe.db.get_value(
            "Translation",
            {"language": language, "source_text": source_text},
            "name",
        )
        if existing_name:
            current = frappe.db.get_value("Translation", existing_name, "translated_text")
            if current == translated_text:
                unchanged += 1
                continue
            frappe.db.set_value("Translation", existing_name, "translated_text", translated_text)
            updated += 1
            continue

        doc = frappe.new_doc("Translation")
        doc.language = language
        doc.source_text = source_text
        doc.translated_text = translated_text
        doc.context = ""
        doc.insert(ignore_permissions=True)
        created += 1

    frappe.clear_cache()
    frappe.db.commit()
    return {
        "language": language,
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "total": len(TURKISH_PRINT_TRANSLATIONS),
    }


def after_migrate():
    return run()
