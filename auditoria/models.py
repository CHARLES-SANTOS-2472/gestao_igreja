from django.conf import settings
from django.db import models


class ChangeLog(models.Model):
    CREATED, UPDATED, DELETED = "created", "updated", "deleted"
    ACTIONS = (
        (CREATED, "Cadastro"),
        (UPDATED, "Alteração"),
        (DELETED, "Exclusão"),
    )

    created_at = models.DateTimeField("Data e hora", auto_now_add=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Usuário",
    )
    username = models.CharField("Usuário (nome)", max_length=150, blank=True)
    action = models.CharField("Ação", max_length=10, choices=ACTIONS)
    app_label = models.CharField(max_length=60)
    model_name = models.CharField("Tipo de registro", max_length=120)
    object_id = models.CharField(max_length=64, blank=True)
    object_repr = models.CharField("Registro", max_length=200, blank=True)
    # Só os nomes dos campos alterados: os valores (CPF, dados financeiros, etc.) não são copiados.
    changed_fields = models.CharField("Campos alterados", max_length=500, blank=True)

    class Meta:
        ordering = ("-created_at", "-id")
        verbose_name = "Alteração registrada"
        verbose_name_plural = "Histórico de alterações"

    def __str__(self):
        return f"{self.get_action_display()} · {self.model_name} · {self.object_repr}"
