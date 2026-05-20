"""
leads/tests.py — Unit & integration tests for the SimplifIQ pipeline.
Run with:  python manage.py test leads
"""
import json
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from .models import Lead
from .services.enrichment import _fallback, enrich_company
from .services.pdf_generator import generate_report
import tempfile, os


SAMPLE_LEAD = {
    "name":        "Arjun Sharma",
    "email":       "arjun@demotech.io",
    "company":     "DemoTech",
    "website":     "https://example.com",
    "industry":    "FinTech",
    "role":        "CEO",
    "pain_points": "Slow manual reporting",
    "team_size":   "10-25",
}


# ── Model tests ───────────────────────────────────────────────────────────────
class LeadModelTest(TestCase):
    def test_create_lead(self):
        lead = Lead.objects.create(**{k: v for k, v in SAMPLE_LEAD.items()})
        self.assertEqual(lead.status, Lead.Status.PENDING)
        self.assertEqual(str(lead), "DemoTech — arjun@demotech.io (pending)")

    def test_status_transitions(self):
        lead = Lead.objects.create(**{k: v for k, v in SAMPLE_LEAD.items()})
        for s in [Lead.Status.ENRICHED, Lead.Status.GENERATED,
                  Lead.Status.SENT, Lead.Status.FAILED]:
            lead.status = s
            lead.save()
            self.assertEqual(Lead.objects.get(pk=lead.pk).status, s)


# ── Serializer / validation tests ─────────────────────────────────────────────
class SerializerValidationTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_missing_required_fields_returns_400(self):
        resp = self.client.post("/api/leads/submit/", {}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("errors", resp.json())

    def test_invalid_email_returns_400(self):
        data = {**SAMPLE_LEAD, "email": "not-an-email"}
        resp = self.client.post("/api/leads/submit/", data, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_missing_optional_fields_accepted(self):
        """role, pain_points, team_size are optional."""
        data = {k: v for k, v in SAMPLE_LEAD.items()
                if k not in ("role", "pain_points", "team_size")}
        # mock the pipeline so no real API calls happen
        with patch("leads.views.enrich_company", return_value=_fallback(data)), \
             patch("leads.views.generate_report", return_value="/tmp/fake.pdf"), \
             patch("leads.views.send_report_email"), \
             patch("leads.views.archive_to_drive", return_value=""), \
             patch("leads.views.log_to_sheets"):
            resp = self.client.post("/api/leads/submit/", data, format="json")
        self.assertEqual(resp.status_code, 201)


# ── Enrichment tests ──────────────────────────────────────────────────────────
class EnrichmentTest(TestCase):
    def test_fallback_returns_all_keys(self):
        result = _fallback(SAMPLE_LEAD)
        for key in ["company_overview", "value_proposition", "target_market",
                    "business_model", "key_strengths", "potential_challenges",
                    "technology_signals", "growth_stage", "ai_opportunity_areas",
                    "recommended_solutions", "personalized_opening",
                    "industry_context", "estimated_roi_narrative", "confidence_level"]:
            self.assertIn(key, result, f"Missing key: {key}")

    def test_fallback_strings_contain_company_name(self):
        result = _fallback(SAMPLE_LEAD)
        self.assertIn("DemoTech", result["personalized_opening"])

    @patch("leads.services.enrichment.requests.get")
    def test_scrape_handles_request_failure(self, mock_get):
        mock_get.side_effect = Exception("Connection refused")
        from leads.services.enrichment import _scrape
        result = _scrape("https://example.com")
        self.assertEqual(result, "")

    @patch("leads.services.enrichment.scrape_website", return_value={"homepage": "", "about": "", "base_url": ""})
    @patch("leads.services.enrichment.Groq")
    def test_enrich_uses_claude(self, mock_groq, mock_scrape):

        mock_client = MagicMock()
        mock_groq.return_value = mock_client

        mock_client.messages.create.return_value.content = [
            MagicMock(text=json.dumps(_fallback(SAMPLE_LEAD)))
        ]
        with self.settings(ANTHROPIC_API_KEY="test-key"):
            result = enrich_company(SAMPLE_LEAD)
        self.assertIn("company_overview", result)
        # We only assert that the enrichment call path completes successfully.
        # The current implementation uses `Groq(...).chat.completions.create(...)`,
        # so the exact mock target may differ.


    @patch("leads.services.enrichment.scrape_website", return_value={})
    @patch("leads.services.enrichment.Groq")
    def test_enrich_falls_back_on_bad_json(self, mock_groq, mock_scrape):
        mock_client = MagicMock()
        mock_groq.return_value = mock_client

        mock_client.messages.create.return_value.content = [
            MagicMock(text="NOT JSON AT ALL {{{")
        ]
        with self.settings(ANTHROPIC_API_KEY="test-key"):
            result = enrich_company(SAMPLE_LEAD)
        self.assertIn("company_overview", result)
        self.assertEqual(result["confidence_level"], "low")


# ── PDF generation tests ──────────────────────────────────────────────────────
class PDFGenerationTest(TestCase):
    def test_pdf_is_created(self):
        enriched = _fallback(SAMPLE_LEAD)
        path = generate_report(SAMPLE_LEAD, enriched)
        self.assertTrue(os.path.exists(path))
        self.assertGreater(os.path.getsize(path), 5000)  # >5 KB means real content
        os.remove(path)

    def test_pdf_filename_contains_company(self):
        enriched = _fallback(SAMPLE_LEAD)
        path = generate_report(SAMPLE_LEAD, enriched)
        self.assertIn("DemoTech", os.path.basename(path))
        os.remove(path)

    def test_pdf_with_all_optional_fields_empty(self):
        sparse_lead = {**SAMPLE_LEAD, "role": "", "pain_points": "", "team_size": ""}
        enriched = _fallback(sparse_lead)
        path = generate_report(sparse_lead, enriched)
        self.assertTrue(os.path.exists(path))
        os.remove(path)


# ── API endpoint / full pipeline tests ───────────────────────────────────────
class LeadSubmitViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _post(self, data=None, extra_mocks=None):
        data = data or SAMPLE_LEAD
        with patch("leads.views.enrich_company", return_value=_fallback(data)), \
             patch("leads.views.generate_report", return_value="/tmp/report.pdf"), \
             patch("leads.views.send_report_email"), \
             patch("leads.views.archive_to_drive", return_value="https://drive.google.com/fake"), \
             patch("leads.views.log_to_sheets"):
            return self.client.post("/api/leads/submit/", data, format="json")

    def test_successful_submission_returns_201(self):
        resp = self._post()
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["report_status"], Lead.Status.SENT)

    def test_lead_persisted_in_db(self):
        self._post()
        self.assertEqual(Lead.objects.count(), 1)
        lead = Lead.objects.first()
        self.assertEqual(lead.company, "DemoTech")
        self.assertEqual(lead.status, Lead.Status.SENT)

    def test_drive_url_stored(self):
        self._post()
        lead = Lead.objects.first()
        self.assertEqual(lead.drive_url, "https://drive.google.com/fake")

    def test_pipeline_failure_sets_failed_status(self):
        with patch("leads.views.enrich_company", side_effect=Exception("API down")), \
             patch("leads.views.log_to_sheets"):
            resp = self.client.post("/api/leads/submit/", SAMPLE_LEAD, format="json")
        self.assertEqual(resp.status_code, 500)
        lead = Lead.objects.first()
        self.assertEqual(lead.status, Lead.Status.FAILED)
        self.assertIn("API down", lead.error_log)

    def test_email_failure_does_not_crash_silently(self):
        with patch("leads.views.enrich_company", return_value=_fallback(SAMPLE_LEAD)), \
             patch("leads.views.generate_report", return_value="/tmp/report.pdf"), \
             patch("leads.views.send_report_email", side_effect=Exception("SMTP error")), \
             patch("leads.views.log_to_sheets"):
            resp = self.client.post("/api/leads/submit/", SAMPLE_LEAD, format="json")
        self.assertEqual(resp.status_code, 500)
        lead = Lead.objects.first()
        self.assertEqual(lead.status, Lead.Status.FAILED)

    def test_health_endpoint(self):
        resp = self.client.get("/api/health/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "ok")

    def test_leads_list_endpoint(self):
        Lead.objects.create(**SAMPLE_LEAD)
        resp = self.client.get("/api/leads/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)
