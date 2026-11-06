"""Uygulama ayarları. API anahtarları SADECE burada, .env'den okunur.

Önemli: Bu sınıf hiçbir zaman api_key'i __repr__/__str__ üzerinden
dışarı sızdırmaz. Pydantic-settings .env dosyasını okur.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Kanal seçimi: console | sms | whatsapp
    notify_channel: str = "console"

    # SMS sağlayıcı
    sms_api_url: str = ""
    sms_api_key: str = ""

    # WhatsApp sağlayıcı
    whatsapp_api_url: str = ""
    whatsapp_api_key: str = ""

    def __repr__(self) -> str:  # anahtar sızmasın
        return (
            f"Settings(notify_channel={self.notify_channel!r}, "
            f"sms_api_key={'***' if self.sms_api_key else ''}, "
            f"whatsapp_api_key={'***' if self.whatsapp_api_key else ''})"
        )


def get_settings() -> Settings:
    """Ayarları .env üzerinden yükler. Her çağrıda okumaz (cache'lenebilir)."""
    return Settings()