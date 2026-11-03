from datetime import date

from django.core.management.base import BaseCommand, CommandError

from comunicacao.services import is_live, run_daily


class Command(BaseCommand):
    help = (
        "Envia as mensagens do dia (aniversários, ocasiões e mensagem diária). "
        "Sem MESSAGING_LIVE=1 ou com --dry-run, apenas simula e registra."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Simula, sem enviar nada.")
        parser.add_argument("--date", help="Data de referência (AAAA-MM-DD). Padrão: hoje.")

    def handle(self, *args, **options):
        try:
            today = date.fromisoformat(options["date"]) if options["date"] else None
        except ValueError:
            raise CommandError("Use a data no formato AAAA-MM-DD.")
        live = False if options["dry_run"] else is_live()
        counts = run_daily(today, live=live)
        mode = "ENVIO REAL" if live else "SIMULAÇÃO"
        self.stdout.write(
            f"[{mode}] aniversários={counts['birthday']} ocasiões={counts['occasion']} "
            f"diárias={counts['daily']} falhas={counts['failed']}"
        )
