"""Cria uma cópia de segurança (.zip) com os dados e as imagens.

  python manage.py backup                 grava em backups/backup-AAAAMMDD-HHMMSS.zip
  python manage.py backup --manter 14     mantém só as 14 cópias mais recentes
  python manage.py backup --restaurar backups/arquivo.zip   recarrega os dados e as imagens
"""
import io
import zipfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

DATA_NAME = "dados.json"
MEDIA_PREFIX = "media/"
EXCLUDES = ("contenttypes", "auth.permission", "sessions", "admin.logentry", "axes")


class Command(BaseCommand):
    help = "Cria ou restaura uma cópia de segurança dos dados e das imagens."

    def add_arguments(self, parser):
        parser.add_argument("--pasta", default=str(Path(settings.BASE_DIR) / "backups"))
        parser.add_argument("--manter", type=int, default=0, help="Quantidade de cópias a manter.")
        parser.add_argument("--restaurar", help="Caminho do .zip a restaurar.")

    def handle(self, *args, **options):
        if options["restaurar"]:
            return self.restore(Path(options["restaurar"]))
        self.create(Path(options["pasta"]), options["manter"])

    def create(self, folder, keep):
        folder.mkdir(parents=True, exist_ok=True)
        buffer = io.StringIO()
        call_command(
            "dumpdata", "--natural-foreign", "--natural-primary", "--indent", "1",
            exclude=list(EXCLUDES), stdout=buffer,
        )
        target = folder / f"backup-{datetime.now():%Y%m%d-%H%M%S}.zip"
        media = Path(settings.MEDIA_ROOT)
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(DATA_NAME, buffer.getvalue())
            if media.exists():
                for file in media.rglob("*"):
                    if file.is_file():
                        archive.write(file, MEDIA_PREFIX + file.relative_to(media).as_posix())
        if keep > 0:
            for old in sorted(folder.glob("backup-*.zip"))[:-keep]:
                old.unlink()
        self.stdout.write(self.style.SUCCESS(f"Cópia criada: {target}"))

    def restore(self, source):
        if not source.exists():
            raise CommandError(f"Arquivo não encontrado: {source}")
        media = Path(settings.MEDIA_ROOT).resolve()
        with zipfile.ZipFile(source) as archive:
            names = archive.namelist()
            if DATA_NAME not in names:
                raise CommandError("Arquivo inválido: falta dados.json.")
            for name in names:
                if not name.startswith(MEDIA_PREFIX) or name.endswith("/"):
                    continue
                destination = (media / name[len(MEDIA_PREFIX):]).resolve()
                if media not in destination.parents:
                    raise CommandError(f"Caminho inesperado no arquivo: {name}")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.read(name))
            data = Path(settings.BASE_DIR) / "_restaurar.json"
            data.write_bytes(archive.read(DATA_NAME))
        try:
            call_command("loaddata", str(data))
        finally:
            data.unlink(missing_ok=True)
        self.stdout.write(self.style.SUCCESS("Cópia restaurada."))
