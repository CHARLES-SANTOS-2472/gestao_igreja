import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from membros.models import CboOccupation


class Command(BaseCommand):
    help = "Importa o catálogo oficial CBO 2002 de ocupações incluído no projeto."

    def handle(self, *args, **options):
        source = Path(__file__).resolve().parents[2] / "data" / "cbo2002-ocupacao.csv"
        if not source.is_file():
            raise CommandError(f"Arquivo oficial da CBO não encontrado: {source}")

        with source.open(encoding="cp1252", newline="") as csv_file:
            reader = csv.DictReader(csv_file, delimiter=";")
            if reader.fieldnames != ["CODIGO", "TITULO"]:
                raise CommandError("O arquivo CBO não tem as colunas CODIGO e TITULO esperadas.")

            occupations = []
            seen_codes = set()
            for line_number, row in enumerate(reader, start=2):
                code = (row.get("CODIGO") or "").strip()
                title = (row.get("TITULO") or "").strip()
                if not code or not title:
                    raise CommandError(
                        f"Linha {line_number} do arquivo CBO sem código ou título."
                    )
                if code in seen_codes:
                    raise CommandError(f"Código CBO duplicado na linha {line_number}: {code}")
                seen_codes.add(code)
                occupations.append(CboOccupation(code=code, title=title))

        if not occupations:
            raise CommandError("Nenhuma ocupação CBO foi encontrada para importar.")

        with transaction.atomic():
            CboOccupation.objects.bulk_create(
                occupations,
                batch_size=500,
                update_conflicts=True,
                unique_fields=["code"],
                update_fields=["title"],
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Catálogo CBO importado com sucesso: {len(occupations)} ocupações."
            )
        )
