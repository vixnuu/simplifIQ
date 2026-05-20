import traceback
import threading
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Lead
from .serializers import LeadSubmitSerializer, LeadResponseSerializer
from .services.enrichment import enrich_company
from .services.pdf_generator import generate_report
from .services.email_sender import send_report_email
from .services.sheets_logger import log_to_sheets
from .services.drive_archiver import archive_to_drive


def run_pipeline(lead_obj, lead):
    """Runs the full pipeline in a background thread."""
    try:
        # 1. Enrich
        print(f"[1/5] Enriching: {lead['company']}")
        enriched = enrich_company(lead)
        lead_obj.status = Lead.Status.ENRICHED
        lead_obj.save(update_fields=["status"])

        # 2. Generate PDF
        print(f"[2/5] Generating PDF")
        report_path = generate_report(lead, enriched)
        lead_obj.report_path = report_path
        lead_obj.status = Lead.Status.GENERATED
        lead_obj.save(update_fields=["report_path", "status"])

        # 3. Send email
        print(f"[3/5] Sending email to {lead['email']}")
        send_report_email(lead, report_path)
        lead_obj.status = Lead.Status.SENT
        lead_obj.save(update_fields=["status"])

        # 4. Archive to Drive
        try:
            print("[4/5] Archiving to Drive")
            drive_url = archive_to_drive(report_path, lead)
            lead_obj.drive_url = drive_url
            lead_obj.save(update_fields=["drive_url"])
        except Exception as e:
            print(f"  ⚠ Drive skipped: {e}")

        # 5. Log to Sheets
        try:
            print("[5/5] Logging to Sheets")
            log_to_sheets(lead, lead_obj.status, lead_obj.drive_url)
        except Exception as e:
            print(f"  ⚠ Sheets skipped: {e}")

    except Exception as exc:
        traceback.print_exc()
        lead_obj.status = Lead.Status.FAILED
        lead_obj.error_log = traceback.format_exc()
        lead_obj.save(update_fields=["status", "error_log"])
        try:
            log_to_sheets(lead, "failed", None)
        except Exception:
            pass


class HealthView(APIView):
    def get(self, request):
        return Response({"status": "ok"})


class LeadSubmitView(APIView):
    def post(self, request):
        serializer = LeadSubmitSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        validated = serializer.validated_data

        # Save lead immediately
        lead_obj = Lead.objects.create(
            name        = validated["name"],
            email       = validated["email"],
            company     = validated["company"],
            website     = validated.get("website", ""),
            industry    = validated["industry"],
            role        = validated.get("role", ""),
            pain_points = validated.get("pain_points", ""),
            team_size   = validated.get("team_size", ""),
            status      = Lead.Status.PENDING,
        )

        lead = {
            "name":        lead_obj.name,
            "email":       lead_obj.email,
            "company":     lead_obj.company,
            "website":     lead_obj.website,
            "industry":    lead_obj.industry,
            "role":        lead_obj.role,
            "pain_points": lead_obj.pain_points,
            "team_size":   lead_obj.team_size,
        }

        # Run pipeline in background thread
        thread = threading.Thread(target=run_pipeline, args=(lead_obj, lead))
        thread.daemon = True
        thread.start()

        # Return immediately — don't wait for pipeline
        return Response({
            "success":       True,
            "message":       "Report is being generated and will be sent to your email shortly!",
            "lead_id":       lead_obj.id,
            "company":       lead_obj.company,
            "report_status": lead_obj.status,
        }, status=status.HTTP_201_CREATED)


class LeadListView(APIView):
    def get(self, request):
        leads = Lead.objects.all()[:50]
        serializer = LeadResponseSerializer(leads, many=True)
        return Response(serializer.data)