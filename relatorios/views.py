from dataclasses import replace

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import TemplateView

from ministerios.models import Department

from .models import SavedReport
from .pdf import NOTE_KEYS, build_pdf, csv_download, pdf_download
from .registry import BY_KEY, REPORTS, default_period


class ReportForm(forms.Form):
    date_from = forms.DateField(label="Data inicial", required=False, widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    date_to = forms.DateField(label="Data final", required=False, widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    introduction = forms.CharField(
        label="1. Introdução", required=False, max_length=5000,
        help_text="Apresente o objetivo do relatório, o período e o contexto.",
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Ex.: Este relatório apresenta as atividades do período..."}))
    development = forms.CharField(
        label="2. Desenvolvimento", required=False, max_length=5000,
        help_text="Descreva o que foi feito, resultados, fatos e observações. Os dados do sistema vêm logo depois.",
        widget=forms.Textarea(attrs={"rows": 6, "placeholder": "Ex.: Durante o período realizamos..."}))
    conclusion = forms.CharField(
        label="3. Conclusão e considerações", required=False, max_length=5000,
        help_text="Faça a análise geral: pontos positivos, dificuldades e o balanço do período.",
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Ex.: Concluímos que..."}))
    recommendations = forms.CharField(
        label="4. Recomendações finais", required=False, max_length=5000,
        help_text="Liste necessidades, sugestões e próximos passos.",
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Ex.: Recomendamos... Necessitamos de..."}))

    signer_name = forms.CharField(label="Nome de quem assina", required=False, max_length=160)
    signer_role = forms.CharField(label="Cargo", required=False, max_length=160,
                                  widget=forms.TextInput(attrs={"placeholder": "Ex.: Líder do Ministério de Louvor"}))

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("date_from"), cleaned.get("date_to")
        if start and end and start > end:
            raise forms.ValidationError("A data inicial não pode ser depois da data final.")
        return cleaned


class ReportHubView(LoginRequiredMixin, TemplateView):
    template_name = "relatorios/hub.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        modules = {}
        for report in REPORTS:
            if not user.has_perm(report.permission):
                continue
            if report.scoped:
                items = [
                    {"title": d.name, "description": "Relatório deste ministério.",
                     "url": reverse("report-scoped", args=[report.key, d.pk])}
                    for d in Department.objects.order_by("name")
                ]
            else:
                items = [{"title": report.title, "description": report.description,
                          "url": reverse("report", args=[report.key])}]
            modules.setdefault(report.module, []).extend(items)
        context["modules"] = modules.items()
        return context


class ReportView(LoginRequiredMixin, TemplateView):
    template_name = "relatorios/report.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.saved = None
        if kwargs.get("saved_pk"):
            self.saved = get_object_or_404(SavedReport.objects.select_related("department"), pk=kwargs["saved_pk"])
            if not (request.user.is_superuser or self.saved.created_by_id == request.user.pk):
                raise PermissionDenied
            self.report = BY_KEY.get(self.saved.key)
            if self.report is None:
                raise Http404
            self.obj = self.saved.department
        else:
            self.report = BY_KEY.get(kwargs["key"])
            if self.report is None:
                return redirect("report-hub")
            self.obj = None
            if self.report.scoped:
                self.obj = get_object_or_404(Department, pk=kwargs.get("pk"))
            elif kwargs.get("pk"):
                return redirect("report", key=self.report.key)
        if not request.user.has_perm(self.report.permission):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def _params(self, form):
        start, end = default_period(self.report.period or "ate_hoje")
        cleaned = form.cleaned_data if form.is_bound and form.is_valid() else {}
        return {"date_from": cleaned.get("date_from") or start, "date_to": cleaned.get("date_to") or end}

    def _data(self, params):
        if self.report.scoped:
            return self.report.build(params, self.obj)
        return self.report.build(params)

    def _title(self):
        return self.report.title if not self.obj else f"{self.report.title}: {self.obj.name}"

    def _default_role(self):
        user = self.request.user
        name = user.get_full_name()
        if self.obj and self.obj.leader and name and str(self.obj.leader) == name:
            return f"Líder do ministério {self.obj.name}"
        return ", ".join(user.groups.values_list("name", flat=True))

    def _initial(self):
        user = self.request.user
        start, end = default_period(self.report.period or "ate_hoje")
        if self.saved:
            initial = {k: getattr(self.saved, k) for k in (*NOTE_KEYS, "signer_name", "signer_role")}
            initial["date_from"] = self.saved.date_from or start
            initial["date_to"] = self.saved.date_to or end
            return initial
        return {"date_from": start, "date_to": end,
                "signer_name": user.get_full_name() or user.get_username(), "signer_role": self._default_role()}

    def _new_form(self):
        form = ReportForm(initial=self._initial())
        if self.saved and self.saved.is_final:
            for field in form.fields.values():
                field.disabled = True
        return form

    def _render(self, form):
        params = self._params(form)
        data = self._data(params)
        saved = self.saved
        return self.render_to_response({
            "report": self.report, "title": self._title(), "form": form, "data": data,
            "has_period": bool(self.report.period), "obj": self.obj, "note_names": NOTE_KEYS,
            "saved": saved, "locked": bool(saved and saved.is_final),
            "issued_on": saved.finalized_on if saved and saved.is_final else timezone.localdate(),
            "city": settings.CHURCH_CITY,
        })

    def get(self, request, *args, **kwargs):
        return self._render(self._new_form())

    def _persist(self, form, final):
        cleaned = form.cleaned_data
        values = {k: cleaned[k] for k in (*NOTE_KEYS, "signer_name", "signer_role")}
        values.update(date_from=cleaned.get("date_from"), date_to=cleaned.get("date_to"))
        if final and not (values["signer_name"].strip()):
            form.add_error("signer_name", "Informe o nome de quem assina para finalizar.")
            return None
        if self.saved is None:
            self.saved = SavedReport(key=self.report.key, department=self.obj, created_by=self.request.user)
        for field, value in values.items():
            setattr(self.saved, field, value)
        if final:
            self.saved.status = SavedReport.Status.FINAL
            self.saved.finalized_on = timezone.localdate()
        self.saved.save()
        return self.saved

    def _download(self, action, notes, signer_name, signer_role, issued_on, period_form=None):
        params = self._params(period_form) if period_form else {
            "date_from": self.saved.date_from or default_period(self.report.period or "ate_hoje")[0],
            "date_to": self.saved.date_to or default_period(self.report.period or "ate_hoje")[1],
        }
        data = self._data(params)
        key = self.report.key if not self.obj else f"{self.report.key}-{self.obj.pk}"
        if action == "csv":
            return csv_download(self.report, data, notes, key, signer_name, signer_role, issued_on)
        report = replace(self.report, title=self._title())
        return pdf_download(build_pdf(report, data, notes, signer_name, signer_role, issued_on), key)

    def post(self, request, *args, **kwargs):
        action = request.POST.get("acao", "preview")
        saved = self.saved
        if saved and saved.is_final:
            if action == "reopen":
                saved.status = SavedReport.Status.DRAFT
                saved.finalized_on = None
                saved.save()
                messages.success(request, "Relatório reaberto para edição.")
            elif action in ("pdf", "csv"):
                return self._download(action, saved.notes, saved.signer_name, saved.signer_role, saved.finalized_on)
            elif action == "delete":
                return self._delete()
            return redirect("report-saved", saved_pk=saved.pk)
        if action == "delete" and saved:
            return self._delete()
        form = ReportForm(request.POST)
        if action in ("save", "finalize") and form.is_valid():
            if self._persist(form, final=action == "finalize"):
                messages.success(request, "Relatório finalizado." if action == "finalize" else "Rascunho salvo.")
                return redirect("report-saved", saved_pk=self.saved.pk)
        elif action in ("pdf", "csv") and form.is_valid():
            cleaned = form.cleaned_data
            notes = {k: cleaned[k] for k in NOTE_KEYS}
            name = cleaned["signer_name"] or request.user.get_full_name() or request.user.get_username()
            return self._download(action, notes, name, cleaned["signer_role"], timezone.localdate(), form)
        return self._render(form)

    def _delete(self):
        self.saved.delete()
        messages.success(self.request, "Relatório excluído.")
        return redirect("report-saved-list")


class SavedReportListView(LoginRequiredMixin, TemplateView):
    template_name = "relatorios/saved_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        queryset = SavedReport.objects.select_related("department", "created_by")
        if not user.is_superuser:
            queryset = queryset.filter(created_by=user)
        items = []
        for saved in queryset:
            report = BY_KEY.get(saved.key)
            if report is None or not user.has_perm(report.permission):
                continue
            title = report.title if not saved.department else f"{report.title}: {saved.department.name}"
            items.append({"saved": saved, "title": title})
        context["items"] = items
        return context
