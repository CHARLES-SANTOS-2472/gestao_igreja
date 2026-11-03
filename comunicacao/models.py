from django.db import models

from membros.models import Member


class MessageLog(models.Model):
    class Channel(models.TextChoices):
        EMAIL = "email", "E-mail"
        WHATSAPP = "whatsapp", "WhatsApp"

    class Kind(models.TextChoices):
        WELCOME = "welcome", "Boas-vindas"
        BIRTHDAY = "birthday", "Aniversário"
        OCCASION = "occasion", "Ocasião especial"
        DAILY = "daily", "Mensagem diária"

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        SENT = "sent", "Enviada"
        SIMULATED = "simulated", "Simulada"
        FAILED = "failed", "Falhou"

    member = models.ForeignKey(
        Member, verbose_name="pessoa", on_delete=models.CASCADE, related_name="message_logs"
    )
    channel = models.CharField("canal", max_length=10, choices=Channel.choices)
    kind = models.CharField("tipo", max_length=10, choices=Kind.choices)
    occasion_key = models.CharField("ocasião", max_length=100, blank=True)
    reference_date = models.DateField("data de referência")
    status = models.CharField(
        "situação", max_length=10, choices=Status.choices, default=Status.PENDING
    )
    text = models.TextField("texto", blank=True)
    verse = models.CharField("versículo", max_length=400, blank=True)
    banner = models.CharField("banner", max_length=255, blank=True)
    error = models.CharField("erro", max_length=300, blank=True)
    created_at = models.DateTimeField("criada em", auto_now_add=True)
    sent_at = models.DateTimeField("enviada em", null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "mensagem enviada"
        verbose_name_plural = "mensagens enviadas"
        constraints = [
            models.UniqueConstraint(
                fields=["member", "channel", "kind", "occasion_key", "reference_date"],
                name="unique_message_per_member_channel_day",
            ),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} · {self.member} · {self.get_channel_display()}"
