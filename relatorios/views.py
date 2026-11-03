from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import TemplateView

from ministerios.models import Department

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
        self.report = BY_KEY.get(kwargs["key"])
        if self.report is None:
            return redirect("report-hub")
        if not request.user.has_perm(self.report.permission):
            raise PermissionDenied
        self.obj = None
        if self.report.scoped:
            self.obj = get_object_or_404(Department, pk=kwargs.get("pk"))
        elif kwargs.get("pk"):
            return redirect("report", key=self.report.key)
        return super().dispatch(request, *args, **kwargs)

    def _params(self, form):
        start, end = default_period(self.report.period or "ate_hoje")
        cleaned = form.cleaned_data if form.is_bound and form.is_valid() else {}
        return {"date_from": cleaned.get("date_from") or start, "date_to": cleaned.get("date_to") or end}

    def _data(self, params):
        if self.report.scoped:
            return self.report.build(params, self.obj)
        return self.report.build(params)

    def _render(self, form):
        params = self._params(form)
        if not form.is_bound:
            form.initial = {"date_from": params["date_from"], "date_to": params["date_to"]}
        title = self.report.title if not self.obj else f"{self.report.title}: {self.obj.name}"
        return self.render_to_response({
            "report": self.report, "title": title, "form": form, "data": self._data(params),
            "has_period": bool(self.report.period), "obj": self.obj, "note_names": NOTE_KEYS,
        })

    def get(self, request, *args, **kwargs):
        return self._render(ReportForm())

    def post(self, request, *args, **kwargs):
        form = ReportForm(request.POST)
        action = request.POST.get("acao", "preview")
        if action in ("pdf", "csv") and form.is_valid():
            params = self._params(form)
            data = self._data(params)
            notes = {k: form.cleaned_data[k] for k in NOTE_KEYS}
            key = self.report.key if not self.obj else f"{self.report.key}-{self.obj.pk}"
            if action == "csv":
                return csv_download(self.report, data, notes, key)
            author = request.user.get_full_name() or request.user.get_username()
            report = self.report
            if self.obj:
                from dataclasses import replace

                report = replace(report, title=f"{report.title}: {self.obj.name}")
            return pdf_download(build_pdf(report, data, notes, author), key)
        return self._render(form)
