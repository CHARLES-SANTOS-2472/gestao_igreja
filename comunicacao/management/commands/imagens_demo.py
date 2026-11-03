"""Exporta e importa as imagens já carregadas, para levá-las ao GitHub/Codespace.

  python manage.py imagens_demo --exportar   copia as imagens do banco atual para demo_media/
  python manage.py imagens_demo              recria os cadastros e anexa as imagens (idempotente)
"""
import json
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from eventos.models import ChurchEvent
from membros.models import Member, MessageOccasion
from ministerios.models import Department
from patrimonio.models import ChurchAsset, Supplier

FOLDER = Path(settings.BASE_DIR) / "demo_media"
MANIFEST = FOLDER / "manifest.json"

# rótulo -> (modelo, campos que identificam o cadastro, campos extras usados ao criar)
KINDS = {
    "pessoa": (Member, ("first_name", "last_name"), ("status", "is_placeholder")),
    "ministerio": (Department, ("name",), ("description",)),
    "bem": (ChurchAsset, ("name",), ("category", "location", "description")),
    "evento": (ChurchEvent, ("title",), ()),
    "fornecedor": (Supplier, ("name",), ()),
    "ocasiao": (MessageOccasion, ("name", "month", "day", "nth_sunday"), ("ai_guidance",)),
}


class Command(BaseCommand):
    help = "Exporta (--exportar) ou importa as imagens de demonstração em demo_media/."

    def add_arguments(self, parser):
        parser.add_argument("--exportar", action="store_true")
        parser.add_argument("--forcar", action="store_true", help="Troca imagens já existentes.")

    def handle(self, *args, **options):
        if options["exportar"]:
            return self.export()
        self.load(options["forcar"])

    def export(self):
        FOLDER.mkdir(exist_ok=True)
        entries = []
        for kind, (model, lookup, extra) in KINDS.items():
            for obj in model.objects.exclude(photo=""):
                name = f"{kind}-{obj.pk}.jpg"
                with obj.photo.open("rb") as source:
                    (FOLDER / name).write_bytes(source.read())
                entries.append({
                    "kind": kind,
                    "lookup": {field: getattr(obj, field) for field in lookup},
                    "extra": {field: getattr(obj, field) for field in extra},
                    "file": name,
                })
        MANIFEST.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"{len(entries)} imagens exportadas para {FOLDER}"))

    def load(self, force):
        if not MANIFEST.exists():
            self.stderr.write("Não encontrei demo_media/manifest.json.")
            return
        attached = skipped = 0
        for entry in json.loads(MANIFEST.read_text(encoding="utf-8")):
            model, _, _ = KINDS[entry["kind"]]
            image = FOLDER / entry["file"]
            if not image.exists():
                self.stderr.write(f"Arquivo ausente: {entry['file']}")
                continue
            obj, _ = model.objects.get_or_create(**entry["lookup"], defaults=entry["extra"])
            if obj.photo and not force:
                skipped += 1
                continue
            obj.photo.save("demo.jpg", ContentFile(image.read_bytes()), save=False)
            obj.save()
            attached += 1
        self.stdout.write(self.style.SUCCESS(
            f"{attached} imagens anexadas, {skipped} já tinham imagem."
        ))
