import json
import re
import urllib.error
import urllib.request

API_URL = "https://brasilapi.com.br/api/cnpj/v1/{}"


def _title(value):
    particles = {"da", "de", "do", "das", "dos", "e"}
    return " ".join(
        w.lower() if w.lower() in particles else w.capitalize() for w in value.split()
    )


def lookup_cnpj(cnpj, timeout=6):
    """Consulta dados públicos do CNPJ. Retorna None se indisponível."""
    cnpj = re.sub(r"\D", "", cnpj or "")
    if len(cnpj) != 14:
        return None
    request = urllib.request.Request(
        API_URL.format(cnpj), headers={"User-Agent": "gestao-igreja"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None
    legal_name = (data.get("razao_social") or "").strip()
    president = next(
        (
            partner.get("nome_socio", "")
            for partner in data.get("qsa") or []
            if "president" in (partner.get("qualificacao_socio") or "").lower()
        ),
        "",
    )
    return {
        "legal_name": _title(legal_name),
        "trade_name": _title((data.get("nome_fantasia") or "").strip()),
        "city": _title((data.get("municipio") or "").strip()),
        "representative": _title(president),
        "situation": data.get("descricao_situacao_cadastral") or "",
    }
