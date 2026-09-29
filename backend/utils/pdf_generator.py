"""Evidence report, without unsupported certification or immutability claims."""

from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer


def render_audit_pdf(data):
    stream = BytesIO()
    styles = getSampleStyleSheet()
    story = []

    def p(text, style="BodyText"):
        story.append(Paragraph(escape(str(text)), styles[style]))
        story.append(Spacer(1, 6))

    p("BidLens AI | Bid review report", "Title")
    p(
        "Decision support only. Registry checks can be unavailable; this report is not a government-issued certificate."
    )
    p(
        f"Mode: {data['mode']} | Tender: {data['tender']['tender_id']} | Version: {data['tender']['version_id']}"
    )
    p(f"Audit: {data['audit_id']} | Created: {data['created_at']}")
    p(data["executive_summary"])
    p(
        f"Risk level: {data['rejection_risk_analysis']['risk_tier']} (rule-based assessment, not a probability)"
    )
    p("Evidence attachments", "Heading2")
    for document in data["documents"]:
        p(f"{document['filename']} | SHA-256: {document['sha256']}")
    p("Tender checks", "Heading2")
    for clause in data["clause_level_decisions"]:
        p(f"{clause['clause_name']}: {clause['status']}", "Heading3")
        p(clause["evidence"])
        for source in clause.get("source_evidence", []):
            p(
                f"{source['filename']} | page/sheet {source['page'] or 'not available'} | {source['text']}"
            )
        if clause.get("officer_override_note"):
            p("Officer override: " + clause["officer_override_note"])
    p("Registry verification", "Heading2")
    for check in data["government_verification"]["gateways"]:
        p(f"{check['name']}: {check['status']} | {check['details']['reason']}")
        p(
            f"Source: {check['details'].get('source', 'None')} | Checked: {check['details'].get('checked_at', 'Not contacted')}"
        )
    p("Unresolved evidence", "Heading2")
    for item in data["contradictions_detected"]:
        p(item["title"] + ": " + item["description"])
    for item in data["branch_a_extracted_data"].get("unread_pages", []):
        p(item)
    p("Officer decisions and event history", "Heading2")
    for event in data.get("history", []):
        p(f"{event['timestamp']} | {event['actor']} | {event['type']}")
        p(event["data"])
    p(
        "Events are hash-linked in local storage. Independent anchoring and protected backups are required for stronger tamper resistance."
    )
    SimpleDocTemplate(
        stream,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    ).build(story)
    return stream.getvalue()
