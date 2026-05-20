from rest_framework import serializers
from .models import Lead

class LeadSubmitSerializer(serializers.Serializer):
    name        = serializers.CharField(max_length=200)
    email       = serializers.EmailField()
    company     = serializers.CharField(max_length=200)
    website     = serializers.URLField(required=False, allow_blank=True, default="")
    industry    = serializers.CharField(max_length=100)
    role        = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    pain_points = serializers.CharField(required=False, allow_blank=True, default="")
    team_size   = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")

class LeadResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Lead
        fields = ["id", "company", "email", "status", "drive_url", "submitted_at"]