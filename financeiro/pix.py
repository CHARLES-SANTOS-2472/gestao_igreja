import io
import re
import unicodedata
from decimal import Decimal

import qrcode
import qrcode.image.svg


def _field(tag, value):
    return f"{tag}{len(value):02d}{value}"


def _ascii(value, limit):
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9 ]", "", text).strip()[:limit]


def crc16(payload):
    crc = 0xFFFF
    for byte in payload.encode("ascii"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return f"{crc:04X}"


def build_pix_payload(key, name, city, amount=None, reference="***"):
    """Monta o BR Code estático do Pix (copia e cola)."""
    account = _field("00", "br.gov.bcb.pix") + _field("01", key)
    reference = _ascii(reference, 25) or "***"
    payload = (
        _field("00", "01")
        + _field("26", account)
        + _field("52", "0000")
        + _field("53", "986")
    )
    if amount:
        payload += _field("54", f"{Decimal(amount):.2f}")
    payload += (
        _field("58", "BR")
        + _field("59", _ascii(name, 25) or "IGREJA")
        + _field("60", _ascii(city, 15) or "BRASIL")
        + _field("62", _field("05", reference))
        + "6304"
    )
    return payload + crc16(payload)


def qr_svg(payload):
    image = qrcode.make(
        payload,
        image_factory=qrcode.image.svg.SvgPathImage,
        box_size=10,
        border=2,
    )
    buffer = io.BytesIO()
    image.save(buffer)
    return buffer.getvalue().decode("utf-8")
