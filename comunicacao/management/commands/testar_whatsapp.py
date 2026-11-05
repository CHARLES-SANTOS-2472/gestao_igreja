import json
import urllib.error
import urllib.request

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from comunicacao.services import normalize_phone


class Command(BaseCommand):
    help = (
        "Testa o WhatsApp (Meta Cloud API) enviando para UM número, sem tocar nos membros. "
        "Sem opções envia o modelo 'hello_world' do número de teste da Meta."
    )

    def add_arguments(self, parser):
        parser.add_argument("--para", required=True, help="Celular com DDD, ex.: 21999998888.")
        parser.add_argument("--modelo", default="hello_world", help="Nome do modelo aprovado (padrão: hello_world).")
        parser.add_argument("--idioma", default="en_US", help="Idioma do modelo (hello_world usa en_US).")
        parser.add_argument("--nome", help="Preenche {{1}} do modelo; use com --texto para preencher {{2}}.")
        parser.add_argument("--texto", help="Preenche {{2}} do modelo.")
        parser.add_argument(
            "--livre", help="Em vez de modelo, envia este texto livre (só funciona se você escreveu "
                            "para o número da Meta nas últimas 24 horas).",
        )

    def handle(self, *args, **options):
        token = getattr(settings, "WHATSAPP_TOKEN", "")
        phone_id = getattr(settings, "WHATSAPP_PHONE_ID", "")
        if not (token and phone_id):
            raise CommandError("Defina WHATSAPP_TOKEN e WHATSAPP_PHONE_ID no .env (ou nos segredos do Codespace).")
        phone = normalize_phone(options["para"])
        if not phone:
            raise CommandError("Celular inválido. Use DDD + número, ex.: 21999998888.")

        payload = {"messaging_product": "whatsapp", "to": phone}
        if options["livre"]:
            payload.update(type="text", text={"body": options["livre"]})
        else:
            template = {"name": options["modelo"], "language": {"code": options["idioma"]}}
            values = [v for v in (options["nome"], options["texto"]) if v is not None]
            if values:
                template["components"] = [{
                    "type": "body", "parameters": [{"type": "text", "text": v} for v in values],
                }]
            payload.update(type="template", template=template)

        version = getattr(settings, "WHATSAPP_API_VERSION", "v20.0")
        request = urllib.request.Request(
            f"https://graph.facebook.com/{version}/{phone_id}/messages",
            data=json.dumps(payload).encode(), method="POST",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = json.loads(response.read().decode() or "{}")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:600]
            raise CommandError(f"A Meta recusou o envio (HTTP {exc.code}): {detail}")
        except urllib.error.URLError as exc:
            raise CommandError(f"Não foi possível falar com a Meta: {exc.reason}")
        message_id = (body.get("messages") or [{}])[0].get("id", "?")
        self.stdout.write(self.style.SUCCESS(f"Aceito pela Meta para {phone}. id={message_id}"))
