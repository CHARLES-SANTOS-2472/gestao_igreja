from django.urls import path

from .views import (
    OwnPasswordChangeView,
    OwnProfileView,
    UserCreateView,
    UserListView,
    UserPasswordResetView,
    UserToggleActiveView,
    UserUpdateView,
)

urlpatterns = [
    path("", UserListView.as_view(), name="user-list"),
    path("novo/", UserCreateView.as_view(), name="user-create"),
    path("<int:pk>/editar/", UserUpdateView.as_view(), name="user-update"),
    path("<int:pk>/senha/", UserPasswordResetView.as_view(), name="user-password-reset"),
    path("<int:pk>/situacao/", UserToggleActiveView.as_view(), name="user-toggle-active"),
    path("minha-senha/", OwnPasswordChangeView.as_view(), name="password-change"),
    path("minha-conta/", OwnProfileView.as_view(), name="profile"),
]
