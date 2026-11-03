from django.conf import settings
from django.db import models


class SavedReport(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Rascunho"
        FINAL = "final", "Finalizado"

    key = models.CharField("relatório", max_length=40)
    department = models.ForeignKey(
        "ministerios.Department", verbose_name="ministério", null=True, blank=True,
        on_delete=models.CASCADE, related_name="saved_reports",
    )
    date_from = models.DateField("data inicial", null=True, blank=True)
    date_to = models.DateField("data final", null=True, blank=True)
    introduction = models.TextField("introdução", blank=True)
    development = models.TextField("desenvolvimento", blank=True)
    conclusion = models.TextField("conclusão e considerações", blank=True)
    recommendations = models.TextField("recomendações finais", blank=True)
    signer_name = models.CharField("nome de quem assina", max_length=160, blank=True)
    signer_role = models.CharField("cargo", max_length=160, blank=True)
    status = models.CharField("situação", max_length=10, choices=Status.choices, default=Status.DRAFT)
    finalized_on = models.DateField("finalizado em", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="criado por", on_delete=models.PROTECT, related_name="saved_reports",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "relatório salvo"
        verbose_name_plural = "relatórios salvos"

    @property
    def is_final(self):
        return self.status == self.Status.FINAL

    @property
    def notes(self):
        return {k: getattr(self, k) for k in ("introduction", "development", "conclusion", "recommendations")}
