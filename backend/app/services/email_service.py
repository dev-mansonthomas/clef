"""Service for sending approval emails. Uses mock mode when USE_MOCKS=true."""
import logging
from typing import Optional, Dict, Any, List

from app.services.gmail_service import gmail_service

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending devis approval emails."""

    async def send_approval_email(
        self,
        dt_id: str,
        devis_data: Dict[str, Any],
        valideur_email: str,
        approval_url: str,
        sender_email: str,
        dossier_description: Optional[List[str]] = None,
        dossier_commentaire: Optional[str] = None,
        est_sinistre: bool = False,
        franchise_applicable: bool = False,
        montant_franchise: float = 0.0,
        total_devis: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Send an HTML email with devis details and approve/reject links.

        In mock mode (USE_MOCKS=true), logs and returns success without sending.
        """
        fournisseur = devis_data.get("fournisseur", {})
        fournisseur_nom = fournisseur.get("nom", "N/A") if isinstance(fournisseur, dict) else "N/A"
        description = devis_data.get("description", "N/A")
        montant = devis_data.get("montant", 0)
        date_devis = devis_data.get("date_devis", "N/A")
        fichier = devis_data.get("fichier")
        drive_link = ""
        if fichier and isinstance(fichier, dict):
            web_view_link = fichier.get("web_view_link", "")
            if web_view_link:
                drive_link = f'<p><a href="{web_view_link}" style="color: #1565c0;">📎 Voir le devis sur Google Drive</a></p>'

        # Build travaux list (use devis description_items if available, else dossier description)
        devis_description_items = devis_data.get("description_items")
        travaux_items = devis_description_items or dossier_description or []

        subject = f"📋 CLEF - Devis à approuver : {fournisseur_nom} — {montant:.2f} €"

        # Build plain text travaux section
        travaux_text = ""
        if travaux_items:
            travaux_lines = "\n".join(f"  - {item}" for item in travaux_items)
            travaux_text = f"\nTravaux prévus :\n{travaux_lines}\n"

        commentaire_text = ""
        if dossier_commentaire:
            commentaire_text = f"\nCommentaire : {dossier_commentaire}\n"

        body_text = f"""Bonjour,

Un devis nécessite votre approbation :

Fournisseur : {fournisseur_nom}
Description : {description}
Montant : {montant:.2f} €
Date du devis : {date_devis}
{travaux_text}{commentaire_text}
Pour approuver ou refuser ce devis, cliquez sur le lien suivant :
{approval_url}

Cordialement,
CLEF - Gestion de flotte Croix-Rouge"""

        # Build HTML travaux section
        travaux_html = ""
        if travaux_items:
            items_li = "".join(f"<li style=\"margin-bottom: 4px;\">{item}</li>" for item in travaux_items)
            travaux_html = f"""<h3 style="color: #333; margin: 20px 0 8px;">Travaux prévus</h3>
<ul style="margin: 0 0 16px; padding-left: 20px;">{items_li}</ul>"""

        commentaire_html = ""
        if dossier_commentaire:
            commentaire_html = f"""<div style="margin: 16px 0; padding: 12px; background: #f5f5f5; border-radius: 4px; border-left: 3px solid #1565c0;">
<strong>Commentaire :</strong> {dossier_commentaire}
</div>"""

        body_html = f"""<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
<h2 style="color: #d32f2f;">📋 Devis à approuver</h2>
<p>Bonjour,</p>
<p>Un devis nécessite votre approbation :</p>
<table style="border-collapse: collapse; margin: 20px 0; width: 100%;">
<tr><td style="padding: 10px; border: 1px solid #ddd; background: #f5f5f5;"><strong>Fournisseur</strong></td>
    <td style="padding: 10px; border: 1px solid #ddd;">{fournisseur_nom}</td></tr>
<tr><td style="padding: 10px; border: 1px solid #ddd; background: #f5f5f5;"><strong>Description</strong></td>
    <td style="padding: 10px; border: 1px solid #ddd;">{description}</td></tr>
<tr><td style="padding: 10px; border: 1px solid #ddd; background: #f5f5f5;"><strong>Montant</strong></td>
    <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold; color: #1565c0;">{montant:.2f} €</td></tr>
<tr><td style="padding: 10px; border: 1px solid #ddd; background: #f5f5f5;"><strong>Date du devis</strong></td>
    <td style="padding: 10px; border: 1px solid #ddd;">{date_devis}</td></tr>
</table>
{self._build_cost_html(est_sinistre, franchise_applicable, montant_franchise, total_devis)}
{travaux_html}
{commentaire_html}
{drive_link}
<p style="margin: 24px 0;">
  <a href="{approval_url}" style="display: inline-block; padding: 12px 24px; background: #1565c0; color: white; text-decoration: none; border-radius: 4px; font-weight: bold;">
    Voir et décider
  </a>
</p>
<p style="color: #666; font-size: 12px;">Ce lien est valable 7 jours.</p>
<p>Cordialement,<br><strong>CLEF</strong> - Gestion de flotte Croix-Rouge</p>
</body>
</html>"""

        result = await gmail_service.send_email(
            dt_id=dt_id,
            to=valideur_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            reply_to=sender_email,
        )

        logger.info(f"Approval email sent to {valideur_email} for devis")
        return result

    async def send_bulk_approval_email(
        self,
        dt_id: str,
        numero_dossier: str,
        devis_list: List[Dict[str, Any]],
        approval_url: str,
        valideur_email: str,
        sender_email: str,
        dossier_description: Optional[List[str]] = None,
        dossier_commentaire: Optional[str] = None,
        est_sinistre: bool = False,
        franchise_applicable: bool = False,
        montant_franchise: float = 0.0,
        total_devis: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Send ONE summary HTML email with all devis info and a single approval link.

        In mock mode (USE_MOCKS=true), logs and returns success without sending.
        """
        nb = len(devis_list)
        total = sum(d.get("montant", 0) for d in devis_list)

        subject = f"📋 CLEF - {nb} devis à approuver — Dossier {numero_dossier} — Total : {total:.2f} €"

        # Build travaux section
        travaux_items = dossier_description or []
        travaux_html = ""
        if travaux_items:
            items_li = "".join(f'<li style="margin-bottom: 4px;">{item}</li>' for item in travaux_items)
            travaux_html = f"""<h3 style="color: #333; margin: 20px 0 8px;">Travaux prévus</h3>
<ul style="margin: 0 0 16px; padding-left: 20px;">{items_li}</ul>"""

        commentaire_html = ""
        if dossier_commentaire:
            commentaire_html = f"""<div style="margin: 16px 0; padding: 12px; background: #f5f5f5; border-radius: 4px; border-left: 3px solid #1565c0;">
<strong>Commentaire :</strong> {dossier_commentaire}
</div>"""

        # Build devis table rows (no per-devis links — single link at bottom)
        rows_html = ""
        rows_text = ""
        for devis_data in devis_list:
            fournisseur = devis_data.get("fournisseur", {})
            fournisseur_nom = fournisseur.get("nom", "N/A") if isinstance(fournisseur, dict) else "N/A"
            description = devis_data.get("description", "N/A")
            description_items = devis_data.get("description_items") or []
            montant = devis_data.get("montant", 0)

            # Build description cell with items if available
            desc_html = description or ""
            if description_items:
                items_sub = "".join(f"<li>{item}</li>" for item in description_items)
                desc_html += f"<ul style='margin: 4px 0 0; padding-left: 16px; font-size: 12px;'>{items_sub}</ul>"

            rows_html += f"""<tr>
<td style="padding: 10px; border: 1px solid #ddd;">{fournisseur_nom}</td>
<td style="padding: 10px; border: 1px solid #ddd;">{desc_html}</td>
<td style="padding: 10px; border: 1px solid #ddd; font-weight: bold; color: #1565c0;">{montant:.2f} €</td>
</tr>"""
            rows_text += f"  - {fournisseur_nom} : {description} — {montant:.2f} €\n"

        # Total row
        rows_html += f"""<tr style="background: #f5f5f5;">
<td style="padding: 10px; border: 1px solid #ddd;" colspan="2"><strong>Total</strong></td>
<td style="padding: 10px; border: 1px solid #ddd; font-weight: bold; color: #d32f2f;">{total:.2f} €</td>
</tr>"""

        # Plain text
        travaux_text = ""
        if travaux_items:
            travaux_lines = "\n".join(f"  - {item}" for item in travaux_items)
            travaux_text = f"\nTravaux prévus :\n{travaux_lines}\n"

        commentaire_text = ""
        if dossier_commentaire:
            commentaire_text = f"\nCommentaire : {dossier_commentaire}\n"

        body_text = f"""Bonjour,

{nb} devis nécessitent votre approbation pour le dossier {numero_dossier} :

{rows_text}
Total : {total:.2f} €
{travaux_text}{commentaire_text}
Pour voir et décider, cliquez sur le lien suivant :
{approval_url}

Cordialement,
CLEF - Gestion de flotte Croix-Rouge"""

        body_html = f"""<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
<h2 style="color: #d32f2f;">📋 {nb} devis à approuver — Dossier {numero_dossier}</h2>
<p>Bonjour,</p>
<p>{nb} devis nécessitent votre approbation :</p>
<table style="border-collapse: collapse; margin: 20px 0; width: 100%;">
<tr style="background: #f5f5f5;">
<th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Fournisseur</th>
<th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Description</th>
<th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Montant</th>
</tr>
{rows_html}
</table>
{self._build_cost_html(est_sinistre, franchise_applicable, montant_franchise, total_devis)}
{travaux_html}
{commentaire_html}
<p style="margin: 24px 0;">
  <a href="{approval_url}" style="display: inline-block; padding: 12px 24px; background: #1565c0; color: white; text-decoration: none; border-radius: 4px; font-weight: bold;">
    Voir et décider
  </a>
</p>
<p style="color: #666; font-size: 12px;">Ce lien est valable 7 jours.</p>
<p>Cordialement,<br><strong>CLEF</strong> - Gestion de flotte Croix-Rouge</p>
</body>
</html>"""

        result = await gmail_service.send_email(
            dt_id=dt_id,
            to=valideur_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            reply_to=sender_email,
        )

        logger.info(f"Bulk approval email sent to {valideur_email} for {nb} devis in dossier {numero_dossier}")
        return result

    def _build_cost_html(
        self,
        est_sinistre: bool,
        franchise_applicable: bool,
        montant_franchise: float,
        total_devis: float,
    ) -> str:
        """Build HTML section showing cost info for approval emails."""
        if total_devis <= 0:
            return ""
        html = f"""<table style="border-collapse: collapse; margin: 10px 0; width: 100%;">
<tr><td style="padding: 10px; border: 1px solid #ddd; background: #f5f5f5;"><strong>Coût des travaux</strong></td>
    <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">{total_devis:.2f} €</td></tr>"""
        if est_sinistre:
            cout_crf = montant_franchise if franchise_applicable else 0
            html += f"""
<tr><td style="padding: 10px; border: 1px solid #ddd; background: #f5f5f5;"><strong>Coût pour la Croix-Rouge</strong></td>
    <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold; color: #d32f2f;">{cout_crf:.2f} €</td></tr>"""
        html += "\n</table>"
        return html


# Global instance
email_service = EmailService()

