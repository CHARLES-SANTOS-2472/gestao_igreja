from django.urls import path

from .views import ReportHubView, ReportView

urlpatterns = [
    path("", ReportHubView.as_view(), name="report-hub"),
    path("<slug:key>/", ReportView.as_view(), name="report"),
    path("<slug:key>/<int:pk>/", ReportView.as_view(), name="report-scoped"),
]
