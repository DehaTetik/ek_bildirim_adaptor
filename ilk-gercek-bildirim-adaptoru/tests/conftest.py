"""Test ortamı: gerçek ağa çıkılmaz, .env okunmaz."""
import os

# Testlerde .env etkisini kapat; Settings boş default'lara düşsün.
os.environ.setdefault("NOTIFY_CHANNEL", "console")