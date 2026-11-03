from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView

from contas.access import can_manage_users

from .models import ChangeLog


class ChangeLogListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = ChangeLog
    template_name = "auditoria/changelog_list.html"
    context_object_name = "entries"
    paginate_by = 50

    def test_func(self):
        return can_manage_users(self.request.user)

    def get_queryset(self):
        queryset = ChangeLog.objects.all()
        get = self.request.GET
        if get.get("acao") in dict(ChangeLog.ACTIONS):
            queryset = queryset.filter(action=get["acao"])
        if get.get("usuario"):
            queryset = queryset.filter(username__icontains=get["usuario"].strip())
        if get.get("q"):
            term = get["q"].strip()
            queryset = queryset.filter(object_repr__icontains=term) | queryset.filter(
                model_name__icontains=term
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["actions"] = ChangeLog.ACTIONS
        context["filters"] = self.request.GET
        params = self.request.GET.copy()
        params.pop("page", None)
        context["query"] = params.urlencode()
        return context
