from django.urls import path
from .views import HealthView, LeadSubmitView, LeadListView

urlpatterns = [
    path("health/",       HealthView.as_view(),    name="health"),
    path("leads/",        LeadListView.as_view(),  name="leads-list"),
    path("leads/submit/", LeadSubmitView.as_view(), name="leads-submit"),
]