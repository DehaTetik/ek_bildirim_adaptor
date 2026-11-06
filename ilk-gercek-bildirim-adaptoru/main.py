"""Uygulama giriş noktası.

KURAL: notifier or build_notifier(settings) — main.py somut sınıfa bağlanmaz.
"""
from __future__ import annotations

import logging

from core.config import Settings, get_settings
from notifications.service import (
    Notifier,
    Order,
    build_notifier,
    change_order_status,
)


def get_notifier(
    settings: Settings | None = None,
    notifier: Notifier | None = None,
) -> Notifier:
    """Dışarıdan notifier verilmediyse settings'ten üretir (DI)."""
    if notifier is not None:
        return notifier
    settings = settings or get_settings()
    return build_notifier(settings)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    settings = get_settings()
    notifier = get_notifier(settings)
    print(f"Aktif notifier: {notifier!r} (channel={notifier.channel})")

    order = Order(id=42, recipient="0532 111 22 33", consent=True, status="CREATED")
    result = change_order_status(order, "SHIPPED", notifier)
    print(f"Sonuç: {result.value} | sipariş durumu: {order.status}")


if __name__ == "__main__":
    main()