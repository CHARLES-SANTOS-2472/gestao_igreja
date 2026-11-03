"""Carrega dados fictícios de demonstração (sem pessoas reais), com imagens geradas na hora.

Uso:  python manage.py carregar_demo            (cria ou completa; pode rodar de novo)
      python manage.py carregar_demo --limpar   (remove somente o que este comando criou)
"""
import io
from datetime import timedelta

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image, ImageDraw

from comunicacao.services import RED, SLATE, WHITE, _font, _wrap
from eventos.models import ChurchEvent
from membros.models import Member, MessageOccasion
from ministerios.models import Department
from patrimonio.models import Supplier

DEPARTMENTS = [
    ("Ministério de Louvor", "Música e adoração nos cultos e eventos.", "Louvor"),
    ("Ministério Infantil", "Cuidado e ensino bíblico para as crianças.", "Infantil"),
    ("Ministério de Jovens", "Encontros, discipulado e atividades para jovens.", "Jovens"),
    ("Ministério de Missões", "Apoio a missionários e ações evangelísticas.", "Missões"),
    ("Ministério de Intercessão", "Vida de oração e cobertura espiritual.", "Oração"),
    ("Ministério de Recepção", "Acolhimento de membros e visitantes.", "Recepção"),
]
EVENTS = [
    ("Culto de Celebração (demonstração)", "service", 3, "Templo principal", "Celebração"),
    ("Congresso de Jovens (demonstração)", "congress", 14, "Templo principal", "Congresso"),
    ("Vigília de Oração (demonstração)", "vigil", 21, "Salão de eventos", "Vigília"),
]
SUPPLIERS = [("Som e Luz Exemplo Ltda (demonstração)", "SL")]
OCCASION_IMAGES = {
    "Dia das Mães": "Mães",
    "Dia dos Pais": "Pais",
    "Dia do Pastor": "Pastor",
    "Dia das Crianças": "Crianças",
    "Natal": "Natal",
    "Ano Novo": "Ano Novo",
    "Dia da Bíblia": "Bíblia",
    "Dia da Mulher": "Mulher",
    "Dia dos Namorados": "Namorados",
}
FICTIONAL_MEMBERS = [
    ("Maria", "Exemplo (demonstração)"),
    ("João", "Exemplo (demonstração)"),
    ("Ana", "Modelo (demonstração)"),
]


def make_art(label, subtitle="", size=(900, 600)):
    """Arte simples nas cores da igreja: degradê ardósia→vermelho com um título centralizado."""
    width, height = size
    image = Image.new("RGB", size, SLATE)
    pixels = ImageDraw.Draw(image)
    for x in range(width):
        t = x / (width - 1)
        color = tuple(int(SLATE[i] + (RED[i] - SLATE[i]) * t * 0.85) for i in range(3))
        pixels.line([(x, 0), (x, height)], fill=color)
    draw = ImageDraw.Draw(image)
    draw.ellipse((width - 260, -120, width + 120, 260), outline=(243, 179, 182), width=4)
    font = _font(88 if len(label) < 14 else 64, bold=True)
    y = height // 2 - 60
    for line in _wrap(draw, label, font, width - 120):
        draw.text((width // 2, y), line, font=font, fill=WHITE, anchor="ma")
        y += 100
    if subtitle:
        draw.text((width // 2, height - 90), subtitle, font=_font(32), fill=(243, 179, 182), anchor="ma")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=88)
    return ContentFile(buffer.getvalue(), name="demo.jpg")


def ensure_photo(instance, label, subtitle=""):
    if not instance.photo:
        instance.photo.save("demo.jpg", make_art(label, subtitle), save=False)
        instance.save()
        return True
    return False


class Command(BaseCommand):
    help = "Carrega ministérios, eventos, fornecedor e imagens fictícias para demonstração."

    def add_arguments(self, parser):
        parser.add_argument("--limpar", action="store_true", help="Remove os dados criados por este comando.")

    def handle(self, *args, **options):
        if options["limpar"]:
            return self.clear()

        created = 0
        for name, description, label in DEPARTMENTS:
            department, was_created = Department.objects.get_or_create(
                name=name, defaults={"description": description}
            )
            created += was_created
            ensure_photo(department, label, "Comunidade Família da Fé")

        start_base = timezone.now().replace(hour=19, minute=30, second=0, microsecond=0)
        for title, kind, days, place, label in EVENTS:
            start = start_base + timedelta(days=days)
            event, was_created = ChurchEvent.objects.get_or_create(
                title=title,
                defaults={
                    "kind": kind, "status": ChurchEvent.Status.PUBLISHED, "starts_at": start,
                    "ends_at": start + timedelta(hours=2), "location": place,
                    "description": "Evento fictício criado para a demonstração do sistema.",
                    "registration_open": True,
                },
            )
            created += was_created
            ensure_photo(event, label, "Comunidade Família da Fé")

        for name, label in SUPPLIERS:
            supplier, was_created = Supplier.objects.get_or_create(name=name)
            created += was_created
            ensure_photo(supplier, label)

        for first, last in FICTIONAL_MEMBERS:
            _, was_created = Member.objects.get_or_create(
                first_name=first, last_name=last, defaults={"status": Member.Status.MEMBER}
            )
            created += was_created

        updated = 0
        for occasion_name, label in OCCASION_IMAGES.items():
            for occasion in MessageOccasion.objects.filter(name=occasion_name):
                updated += ensure_photo(occasion, label, occasion.date_label)

        self.stdout.write(self.style.SUCCESS(
            f"Demonstração pronta: {created} cadastros novos e {updated} ocasiões com imagem. "
            "Os cadastros fictícios têm “(demonstração)” no nome. Para remover: carregar_demo --limpar"
        ))

    def clear(self):
        removed = 0
        for model, field, names in (
            (Department, "name", [d[0] for d in DEPARTMENTS]),
            (ChurchEvent, "title", [e[0] for e in EVENTS]),
            (Supplier, "name", [s[0] for s in SUPPLIERS]),
        ):
            for instance in model.objects.filter(**{f"{field}__in": names}):
                instance.delete()
                removed += 1
        for first, last in FICTIONAL_MEMBERS:
            for member in Member.objects.filter(first_name=first, last_name=last):
                member.delete()
                removed += 1
        for occasion in MessageOccasion.objects.exclude(photo=""):
            occasion.photo.delete(save=False)
            occasion.photo = ""
            occasion.save()
        self.stdout.write(self.style.SUCCESS(f"Removidos {removed} cadastros de demonstração."))
