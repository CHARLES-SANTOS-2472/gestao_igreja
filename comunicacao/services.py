"""Mensagens automáticas: texto (IA ou modelo próprio), banner, e-mail e WhatsApp.

Por padrão tudo roda em modo simulação (MESSAGING_LIVE=0): o texto e o banner são
gerados e registrados em MessageLog, mas nada é enviado a ninguém.
"""
import io
import json
import re
import urllib.request
from datetime import date, timedelta
from email.mime.image import MIMEImage
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from membros.models import MessageOccasion, Member

from .models import MessageLog

SLATE = (43, 53, 68)
RED = (215, 38, 46)
WHITE = (255, 255, 255)

VERSES = [
    ("O Senhor é o meu pastor; nada me faltará.", "Salmos 23:1"),
    ("Lancem sobre ele toda a sua ansiedade, porque ele tem cuidado de vocês.", "1 Pedro 5:7"),
    ("Tudo posso naquele que me fortalece.", "Filipenses 4:13"),
    ("O Senhor te abençoe e te guarde; o Senhor faça resplandecer o seu rosto sobre ti.", "Números 6:24-25"),
    ("Confia no Senhor de todo o teu coração e não te estribes no teu próprio entendimento.", "Provérbios 3:5"),
    ("As misericórdias do Senhor se renovam a cada manhã; grande é a tua fidelidade.", "Lamentações 3:22-23"),
    ("Não temas, porque eu sou contigo; não te assombres, porque eu sou o teu Deus.", "Isaías 41:10"),
    ("Alegrai-vos sempre no Senhor; outra vez digo: alegrai-vos.", "Filipenses 4:4"),
    ("Porque Deus amou o mundo de tal maneira que deu o seu Filho unigênito.", "João 3:16"),
    ("Esta é a confiança que temos nele: se pedirmos alguma coisa segundo a sua vontade, ele nos ouve.", "1 João 5:14"),
    ("O Senhor é a minha luz e a minha salvação; de quem terei medo?", "Salmos 27:1"),
    ("Entrega o teu caminho ao Senhor; confia nele, e ele o fará.", "Salmos 37:5"),
]

FALLBACK_TEXT = {
    MessageLog.Kind.WELCOME: (
        "Seja muito bem-vindo(a) à Comunidade Família da Fé! "
        "Temos alegria em ter você conosco, e esta casa é sua."
    ),
    MessageLog.Kind.BIRTHDAY: (
        "Que o Senhor abençoe a sua vida com saúde, paz e alegria "
        "neste novo ano que se inicia. Parabéns pelo seu aniversário!"
    ),
    MessageLog.Kind.OCCASION: (
        "Neste dia especial, queremos lembrar de você com carinho "
        "e pedir as bênçãos de Deus sobre a sua vida e a sua família."
    ),
    MessageLog.Kind.DAILY: "Que o seu dia seja guiado pela paz e pelo cuidado do Senhor.",
}
TITLES = {
    MessageLog.Kind.WELCOME: "Bem-vindo(a), {name}!",
    MessageLog.Kind.BIRTHDAY: "Feliz aniversário, {name}!",
    MessageLog.Kind.OCCASION: "{occasion}",
    MessageLog.Kind.DAILY: "Bom dia, {name}!",
}


def is_live():
    return bool(getattr(settings, "MESSAGING_LIVE", False))


def pick_verse(seed):
    return VERSES[seed % len(VERSES)]


def compose_text(first_name, kind, occasion_name="", guidance=""):
    """Texto curto (sem versículo). Usa a OpenAI quando há chave; senão, um modelo próprio."""
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if api_key:
        prompt = (
            "Escreva em português do Brasil uma mensagem pastoral curta (até 3 frases), "
            "calorosa e respeitosa, de uma igreja evangélica. Não inclua versículos, "
            "saudações de assinatura nem emojis. "
            f"Tipo: {kind}. Ocasião: {occasion_name or 'não se aplica'}. "
            f"Orientação: {guidance or 'nenhuma'}. Nome da pessoa: {first_name}."
        )
        body = json.dumps({
            "model": getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 200,
        }).encode()
        request = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions", data=body, method="POST",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                text = json.load(response)["choices"][0]["message"]["content"].strip()
            if text:
                return text[:600]
        except Exception:
            pass  # cai no modelo próprio
    return FALLBACK_TEXT[kind]


def _font(size, bold=False, italic=False):
    names = {
        (False, False): ("arial.ttf", "DejaVuSans.ttf"),
        (True, False): ("arialbd.ttf", "DejaVuSans-Bold.ttf"),
        (False, True): ("ariali.ttf", "DejaVuSans-Oblique.ttf"),
        (True, True): ("arialbi.ttf", "DejaVuSans-BoldOblique.ttf"),
    }[(bold, italic)]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(draw, text, font, width):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def build_banner(title, text, verse, reference):
    """Banner quadrado (1080 px) com a logo, a mensagem e o versículo. Retorna bytes PNG."""
    size = 1080
    image = Image.new("RGB", (size, size), SLATE)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, size, 250), fill=WHITE)
    draw.rectangle((0, 250, size, 262), fill=RED)

    logo_path = Path(settings.BASE_DIR) / "static" / "img" / "logo.jpg"
    if logo_path.exists():
        with Image.open(logo_path) as logo:
            logo = logo.convert("RGB")
            logo.thumbnail((900, 210))
            image.paste(logo, ((size - logo.width) // 2, (250 - logo.height) // 2))

    y = 320
    title_font = _font(66, bold=True)
    for line in _wrap(draw, title, title_font, size - 140):
        draw.text((size // 2, y), line, font=title_font, fill=WHITE, anchor="ma")
        y += 80
    y += 20
    body_font = _font(40)
    for line in _wrap(draw, text, body_font, size - 180):
        draw.text((size // 2, y), line, font=body_font, fill=(230, 233, 238), anchor="ma")
        y += 54
    y += 30
    verse_font = _font(36, italic=True)
    for line in _wrap(draw, f"“{verse}”", verse_font, size - 200):
        draw.text((size // 2, y), line, font=verse_font, fill=(243, 179, 182), anchor="ma")
        y += 48
    draw.text((size // 2, y + 6), reference, font=_font(34, bold=True), fill=WHITE, anchor="ma")

    signature = Path(settings.BASE_DIR) / "static" / "img" / "assinatura.png"
    foot_y = size - 120
    if signature.exists():
        with Image.open(signature) as sig:
            sig = sig.convert("RGBA")
            sig.thumbnail((360, 90))
            image.paste(sig, ((size - sig.width) // 2, foot_y - 10), sig)
    draw.text(
        (size // 2, size - 56), getattr(settings, "CHURCH_SIGNATURE", "Pastores"),
        font=_font(30, bold=True), fill=WHITE, anchor="ma",
    )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def normalize_phone(raw):
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) in (10, 11):
        digits = "55" + digits
    return digits if 12 <= len(digits) <= 13 else ""


def _send_email(member, subject, text, verse_line, png):
    html = (
        f"<p>{text}</p><p><em>{verse_line}</em></p>"
        '<p><img src="cid:banner" alt="" style="max-width:100%"></p>'
    )
    message = EmailMultiAlternatives(subject, f"{text}\n\n{verse_line}", to=[member.email])
    message.attach_alternative(html, "text/html")
    message.mixed_subtype = "related"
    image = MIMEImage(png, _subtype="png")
    image.add_header("Content-ID", "<banner>")
    image.add_header("Content-Disposition", "inline", filename="banner.png")
    message.attach(image)
    message.send()


def _send_whatsapp(member, template, text, verse_line):
    token = getattr(settings, "WHATSAPP_TOKEN", "")
    phone_id = getattr(settings, "WHATSAPP_PHONE_ID", "")
    phone = normalize_phone(member.mobile)
    if not (token and phone_id and template and phone):
        raise RuntimeError("WhatsApp não configurado (token, número, modelo aprovado ou celular).")
    version = getattr(settings, "WHATSAPP_API_VERSION", "v20.0")
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "template",
        "template": {
            "name": template,
            "language": {"code": "pt_BR"},
            "components": [{
                "type": "body",
                "parameters": [
                    {"type": "text", "text": member.first_name},
                    {"type": "text", "text": f"{text} {verse_line}"[:900]},
                ],
            }],
        },
    }
    request = urllib.request.Request(
        f"https://graph.facebook.com/{version}/{phone_id}/messages",
        data=json.dumps(payload).encode(), method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20):
        pass


def eligible_members():
    return Member.objects.filter(is_deceased=False, is_placeholder=False).exclude(
        status=Member.Status.INACTIVE
    )


def can_receive(member, channel, kind):
    if channel == MessageLog.Channel.EMAIL:
        return bool(member.email and member.email_consent)
    if not (member.mobile and member.whatsapp_consent):
        return False
    return member.whatsapp_daily_consent if kind == MessageLog.Kind.DAILY else True


def deliver(member, channel, kind, reference_date, occasion=None, live=None):
    """Gera, registra e envia (ou simula) uma mensagem. É idempotente por pessoa/canal/dia."""
    live = is_live() if live is None else live
    if not can_receive(member, channel, kind):
        return None
    key = str(occasion.pk) if occasion else ""
    log, created = MessageLog.objects.get_or_create(
        member=member, channel=channel, kind=kind, occasion_key=key,
        reference_date=reference_date,
    )
    if not created and log.status in (MessageLog.Status.SENT, MessageLog.Status.SIMULATED):
        return None

    try:
        text = compose_text(
            member.first_name, kind,
            occasion.name if occasion else "", occasion.ai_guidance if occasion else "",
        )
        verse, reference = pick_verse(reference_date.toordinal() + member.pk)
        title = TITLES[kind].format(
            name=member.first_name, occasion=occasion.name if occasion else ""
        )
        png = build_banner(title, text, verse, reference)
        verse_line = f"“{verse}” — {reference}"
        folder = Path(settings.MEDIA_ROOT) / "mensagens" / reference_date.isoformat()
        folder.mkdir(parents=True, exist_ok=True)
        banner_path = folder / f"{log.pk}.png"
        banner_path.write_bytes(png)
        log.text, log.verse, log.banner = text, verse_line, f"mensagens/{reference_date.isoformat()}/{log.pk}.png"
        if live:
            if channel == MessageLog.Channel.EMAIL:
                _send_email(member, title, text, verse_line, png)
            else:
                template = (occasion.whatsapp_template_name if occasion else "") or \
                    getattr(settings, "WHATSAPP_TEMPLATES", {}).get(kind, "")
                _send_whatsapp(member, template, text, verse_line)
            log.status, log.sent_at = MessageLog.Status.SENT, timezone.now()
        else:
            log.status = MessageLog.Status.SIMULATED
        log.error = ""
    except Exception as exc:
        log.status, log.error = MessageLog.Status.FAILED, str(exc)[:300]
    log.save()
    return log


def welcome_member(member_id, live=None):
    member = Member.objects.filter(pk=member_id).first()
    if member is None or member.is_placeholder:
        return []
    today = timezone.localdate()
    logs = []
    for channel in MessageLog.Channel.values:
        already = MessageLog.objects.filter(
            member=member, channel=channel, kind=MessageLog.Kind.WELCOME
        ).exists()
        if not already:
            log = deliver(member, channel, MessageLog.Kind.WELCOME, today, live=live)
            if log:
                logs.append(log)
    return logs


def birthday_members(today):
    queryset = eligible_members().filter(birth_date__month=today.month, birth_date__day=today.day)
    ids = list(queryset.values_list("pk", flat=True))
    # Quem nasceu em 29/02 recebe em 28/02 nos anos não bissextos.
    if today.month == 2 and today.day == 28 and (today + timedelta(days=1)).month == 3:
        ids += list(
            eligible_members().filter(birth_date__month=2, birth_date__day=29)
            .values_list("pk", flat=True)
        )
    return Member.objects.filter(pk__in=ids)


def run_daily(today=None, live=None):
    """Rotina diária (7h): aniversários, ocasiões cadastradas e mensagem diária."""
    today = today or timezone.localdate()
    counts = {"birthday": 0, "occasion": 0, "daily": 0, "failed": 0}
    channels = MessageLog.Channel.values

    def tally(log, kind):
        if log is None:
            return
        counts["failed" if log.status == MessageLog.Status.FAILED else kind] += 1

    birthday_ids = set()
    for member in birthday_members(today):
        birthday_ids.add(member.pk)
        for channel in channels:
            tally(deliver(member, channel, MessageLog.Kind.BIRTHDAY, today, live=live), "birthday")

    occasions = [
        occasion
        for occasion in MessageOccasion.objects.filter(active=True, month=today.month)
        if occasion.occurs_on(today)
    ]
    for occasion in occasions:
        for member in eligible_members():
            for channel in channels:
                tally(
                    deliver(member, channel, MessageLog.Kind.OCCASION, today, occasion, live=live),
                    "occasion",
                )

    if not occasions:
        for member in eligible_members().filter(whatsapp_daily_consent=True):
            if member.pk in birthday_ids:
                continue
            tally(
                deliver(member, MessageLog.Channel.WHATSAPP, MessageLog.Kind.DAILY, today, live=live),
                "daily",
            )
    return counts
