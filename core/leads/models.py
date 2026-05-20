from django.db import models

class Lead(models.Model):
    class Status(models.TextChoices):
        PENDING   = "pending",   "Pending"
        ENRICHED  = "enriched",  "Enriched"
        GENERATED = "generated", "Report Generated"
        SENT      = "sent",      "Email Sent"
        FAILED    = "failed",    "Failed"

    name        = models.CharField(max_length=200)
    email       = models.EmailField()
    company     = models.CharField(max_length=200)
    website     = models.URLField(blank=True)
    industry    = models.CharField(max_length=100)
    role        = models.CharField(max_length=100, blank=True)
    pain_points = models.TextField(blank=True)
    team_size   = models.CharField(max_length=50, blank=True)
    status      = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    report_path = models.CharField(max_length=500, blank=True)
    drive_url   = models.URLField(blank=True)
    error_log   = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.company} — {self.email} ({self.status})"