"""SMS adaptörü testleri — gerçek ağ YOK, httpx.MockTransport kullanılır."""
from __future__ import annotations

import json
import logging

import httpx
import pytest

from core.config import Settings
from notifications.service import (
    ConsoleNotifier,
    NotificationStatus,
    Order,
    SmsNotifier,
    build_notifier,
    change_order_status,
    normalize_phone,
    notify_status_change,
)


# --------------------------------------------------------------------------- #
# Yardımcılar
# --------------------------------------------------------------------------- #
def make_mock_client(status: int, capture: dict | None = None) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if capture is not None:
            capture["request"] = request
            capture["json"] = json.loads(request.content or b"{}")
            capture["headers"] = dict(request.headers)
        return httpx.Response(status)

    return httpx.Client(transport=httpx.MockTransport(handler))


def _sms_notifier(client: httpx.Client, api_key: str = "test-key") -> SmsNotifier:
    return SmsNotifier(
        api_url="https://fake.local/send",
        api_key=api_key,
        client=client,
    )


# --------------------------------------------------------------------------- #
# Mutlu yol
# --------------------------------------------------------------------------- #
def test_sms_sent_when_provider_returns_200():
    client = make_mock_client(200)
    notifier = _sms_notifier(client)
    order = Order(id=42, recipient="0532 111 22 33", consent=True)

    result = notify_status_change(order, "SHIPPED", notifier)

    assert result == NotificationStatus.SENT


# --------------------------------------------------------------------------- #
# Sağlayıcı 500 -> FAILED + sipariş durumu yine değişmiş olmalı
# --------------------------------------------------------------------------- #
def test_sms_failed_but_order_status_changes():
    client = make_mock_client(500)
    notifier = _sms_notifier(client)
    order = Order(id=42, recipient="0532 111 22 33", consent=True, status="CREATED")

    result = change_order_status(order, "SHIPPED", notifier)

    assert result == NotificationStatus.FAILED
    assert order.status == "SHIPPED"  # iş durmadı


# --------------------------------------------------------------------------- #
# Telefon normalizasyonu
# --------------------------------------------------------------------------- #
def test_phone_normalized_to_e164_in_request():
    capture: dict = {}
    client = make_mock_client(200, capture)
    notifier = _sms_notifier(client)
    order = Order(id=1, recipient="0532 111 22 33", consent=True)

    notify_status_change(order, "SHIPPED", notifier)

    assert capture["json"]["to"] == "+905321112233"


def test_normalize_phone_variants():
    assert normalize_phone("0532 111 22 33") == "+905321112233"
    assert normalize_phone("+90 532 111 22 33") == "+905321112233"
    assert normalize_phone("905321112233") == "+905321112233"
    assert normalize_phone("532 111 22 33") == "+905321112233"


# --------------------------------------------------------------------------- #
# Rıza yoksa istek atılmaz
# --------------------------------------------------------------------------- #
def test_no_consent_skips_and_makes_no_request():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    notifier = _sms_notifier(client)
    order = Order(id=1, recipient="0532 111 22 33", consent=False)

    result = notify_status_change(order, "SHIPPED", notifier)

    assert result == NotificationStatus.SKIPPED
    assert calls == [], "Rıza yokken istek atılmamalı"


# --------------------------------------------------------------------------- #
# API anahtarı log'da görünmemeli
# --------------------------------------------------------------------------- #
def test_api_key_not_leaked_in_logs(caplog: pytest.LogCaptureFixture):
    caplog.set_level(logging.DEBUG)
    secret = "super-secret-api-key-12345"
    client = make_mock_client(500)  # hata üret ki log tetiklensin
    notifier = _sms_notifier(client, api_key=secret)
    order = Order(id=1, recipient="0532 111 22 33", consent=True)

    notify_status_change(order, "SHIPPED", notifier)

    # 1) Formatlanmış tüm log çıktısı
    assert secret not in caplog.text, "API anahtarı log'da sızdı!"
    # 2) Tek tek kayıtların mesajı
    for record in caplog.records:
        assert secret not in record.getMessage()
    # 3) Notifier repr
    assert secret not in repr(notifier)
    # 4) Settings repr
    settings = Settings(
        notify_channel="sms",
        sms_api_url="https://x",
        sms_api_key=secret,
    )
    assert secret not in repr(settings)


# --------------------------------------------------------------------------- #
# Fabrika testleri
# --------------------------------------------------------------------------- #
def test_build_notifier_console():
    s = Settings(notify_channel="console")
    assert isinstance(build_notifier(s), ConsoleNotifier)


def test_build_notifier_sms_requires_credentials():
    s = Settings(notify_channel="sms", sms_api_url="", sms_api_key="")
    with pytest.raises(ValueError, match="api_url ve api_key"):
        build_notifier(s)


def test_build_notifier_unknown_channel():
    s = Settings(notify_channel="pigeon")
    with pytest.raises(ValueError, match="Bilinmeyen"):
        build_notifier(s)