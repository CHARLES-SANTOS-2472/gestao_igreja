from django.urls import path

from .views import ReportHubView, ReportView, SavedReportListView

urlpatterns = [
    path("", ReportHubView.as_view(), name="report-hub"),
    path("salvos/", SavedReportListView.as_view(), name="report-saved-list"),
    path("salvo/<int:saved_pk>/", ReportView.as_view(), name="report-saved"),
    path("<slug:key>/", ReportView.as_view(), name="report"),
    path("<slug:key>/<int:pk>/", ReportView.as_view(), name="report-scoped"),
]
