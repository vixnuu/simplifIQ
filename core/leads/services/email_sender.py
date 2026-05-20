"""
email_sender.py
Sends the generated PDF report to the prospect via Django's email backend.
"""
import os
from django.core.mail import EmailMessage
from django.conf import settings


EMAIL_SUBJECT = "Your Personalised Business Audit Report — SimplifIQ"

EMAIL_BODY_TEMPLATE = """\
Hi {name},

Thank you for your interest in SimplifIQ.

I'm delighted to share your personalised Business Audit Report for {company}.
We've researched your business and outlined specific opportunities where AI-powered
automation can make an immediate, measurable impact.

What's inside:
  • Company intelligence & market positioning
  • AI opportunity areas tailored to {industry}
  • Recommended solutions with ROI projections
  • A clear next-steps roadmap

Please find the full report attached as a PDF.

We'd love to walk you through the findings on a quick 30-minute call — just reply
to this email and we'll find a time that works for you.

Warm regards,
The SimplifIQ Team
hello@simplifiq.ai

---
This report was generated automatically based on your submitted information and
publicly available sources. All findings are personalised to {company}.
"""


def send_report_email(lead: dict, report_path: str) -> None:
    try:
        body = EMAIL_BODY_TEMPLATE.format(
            name=lead["name"],
            company=lead["company"],
            industry=lead["industry"],
        )

        msg = EmailMessage(
            subject=EMAIL_SUBJECT,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[lead["email"]],
            reply_to=[settings.DEFAULT_FROM_EMAIL],
        )

        filename = os.path.basename(report_path)
        with open(report_path, "rb") as f:
            msg.attach(filename, f.read(), "application/pdf")

        msg.send(fail_silently=False)
        print(f"  ✓ Email sent to {lead['email']}")
    except Exception as e:
        print(f"  ✗ Email failed: {str(e)}")
        raise