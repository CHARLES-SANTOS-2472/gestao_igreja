from django.urls import path

from .views import ChangeLogListView

urlpatterns = [
    path("", ChangeLogListView.as_view(), name="changelog-list"),
]
