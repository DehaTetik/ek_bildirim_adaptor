"""Bildirim adaptörleri.

Tasarım kararı: `Notifier` bir Protokol'dür (yapısal tipleme). `build_notifier`
fabrikası, ayarlara bakarak somut bir uygulama döndürür. `main.py` asla somut
sınıfa doğrudan bağlanmaz — böylece bağımlılık tersine çevrilir.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

import httpx

from core.config import Settings

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Domain
# --------------------------------------------------------------------------- #
class NotificationStatus(str, Enum):
    SENT = "SENT"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class Order:
    id: int
    recipient: str          # müşteri telefon numarası
    consent: bool           # açık rıza (İYS / KVKK)
    status: str = "CREATED"


# --------------------------------------------------------------------------- #
# Protokol (interface) — "Bağımlılığı tersine çevir"
# --------------------------------------------------------------------------- #
class Notifier(Protocol):
    channel: str

    def send(self, recipient: str, message: str) -> None:  # pragma: no cover
        ...


# --------------------------------------------------------------------------- #
# Console (varsayılan, geliştirme)
# --------------------------------------------------------------------------- #
class ConsoleNotifier:
    channel = "console"

    def __init__(self) -> None:
        pass

    def send(self, recipient: str, message: str) -> None:
        # Gerçek gönderim yok; sadece stdout'a yazar.
        print(f"[CONSOLE] -> {recipient}: {message}")

    def __repr__(self) -> str:
        return "ConsoleNotifier()"


# --------------------------------------------------------------------------- #
# HTTP tabanlı adaptörler (SMS / WhatsApp)
# --------------------------------------------------------------------------- #
def normalize_phone(raw: str) -> str:
    """Türk telefon numarasını E.164 biçimine çevirir (+90XXXXXXXXXX).

    0532 111 22 33  ->  +905321112233
    +90 532 111 22 33 -> +905321112233
    905321112233    ->  +905321112233
    """
    digits = "".join(ch for ch in raw if ch.isdigit())
    if digits.startswith("0"):
        digits = digits[1:]
    if not digits.startswith("90"):
        digits = "90" + digits
    return "+" + digits


class _HttpNotifierBase:
    """Ortak HTTP davranışı. `channel` alt sınıflarda tanımlanır."""

    channel: str = ""

    def __init__(
        self,
        api_url: str,
        api_key: str,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_url or not api_key:
            raise ValueError(f"{self.channel}: api_url ve api_key zorunludur")
        self._api_url = api_url
        self._api_key = api_key
        # Test enjeksiyonu için: client dışarıdan verilebilir.
        self._client = client or httpx.Client(timeout=5.0)

    # Anahtar hiçbir zaman repr/str üzerinden görünmesin.
    def __repr__(self) -> str:
        return f"{type(self).__name__}(api_url={self._api_url!r}, api_key='***')"

    # --- alt sınıflar özelleştirir ---
    def _build_body(self, phone_e164: str, message: str) -> dict:
        raise NotImplementedError

    def _build_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    # --- ortak gönderim ---
    def send(self, recipient: str, message: str) -> None:
        phone = normalize_phone(recipient)
        response = self._client.post(
            self._api_url,
            json=self._build_body(phone, message),
            headers=self._build_headers(),
            timeout=5,
        )
        if not (200 <= response.status_code < 300):
            # Anahtar burada YOK; sadece durum kodu.
            raise RuntimeError(
                f"{self.channel} sağlayıcı hatası: status={response.status_code}"
            )


class SmsNotifier(_HttpNotifierBase):
    channel = "sms"

    def _build_body(self, phone_e164: str, message: str) -> dict:
        return {"to": phone_e164, "message": message}


class WhatsAppNotifier(_HttpNotifierBase):
    channel = "whatsapp"

    def _build_body(self, phone_e164: str, message: str) -> dict:
        # Meta Cloud API örneği; sağlayıcıya göre güncellenebilir.
        return {
            "messaging_product": "whatsapp",
            "to": phone_e164.lstrip("+"),
            "type": "text",
            "text": {"body": message},
        }


# --------------------------------------------------------------------------- #
# Fabrika
# --------------------------------------------------------------------------- #
def build_notifier(settings: Settings) -> Notifier:
    """Ayarlara göre somut notifier döner. Bilinmeyen kanalda hata verir."""
    channel = (settings.notify_channel or "console").lower()
    if channel == "console":
        return ConsoleNotifier()
    if channel == "sms":
        return SmsNotifier(
            api_url=settings.sms_api_url,
            api_key=settings.sms_api_key,
        )
    if channel == "whatsapp":
        return WhatsAppNotifier(
            api_url=settings.whatsapp_api_url,
            api_key=settings.whatsapp_api_key,
        )
    raise ValueError(f"Bilinmeyen NOTIFY_CHANNEL: {channel!r}")


# --------------------------------------------------------------------------- #
# İş akışı — notify_status_change
# --------------------------------------------------------------------------- #
def notify_status_change(
    order: Order,
    new_status: str,
    notifier: Notifier,
) -> NotificationStatus:
    """Sadece bildirim gönderir; sipariş durumu caller tarafından güncellenir.

    - Rıza yoksa: SKIPPED (istek ATILMAZ).
    - Sağlayıcı patlarsa: FAILED (iş akışı bozulmaz).
    - Aksi halde: SENT.
    """
    if not order.consent:
        logger.info("Rıza yok, bildirim atlandı: order_id=%s", order.id)
        return NotificationStatus.SKIPPED

    message = f"Sipariş #{order.id} durumu: {new_status}"
    try:
        notifier.send(order.recipient, message)
        logger.info(
            "Bildirim gönderildi: order_id=%s kanal=%s",
            order.id,
            notifier.channel,
        )
        return NotificationStatus.SENT
    except Exception as exc:
        # DİKKAT: exception mesajı log'a basılmıyor (anahtar sızmasın diye).
        # Sadece tipi + kanal. Detay isteyen DEBUG açar.
        logger.warning(
            "Bildirim gönderilemedi: order_id=%s kanal=%s hata=%s",
            order.id,
            notifier.channel,
            type(exc).__name__,
        )
        logger.debug("Bildirim hata detayı", exc_info=True)
        return NotificationStatus.FAILED


def change_order_status(
    order: Order,
    new_status: str,
    notifier: Notifier,
) -> NotificationStatus:
    """Sipariş durumunu değiştirir, ardından bildirimi best-effort dener.

    Sipariş durumu HER ZAMAN değişir; sağlayıcı çökse de iş durmaz.
    """
    order.status = new_status
    return notify_status_change(order, new_status, notifier)