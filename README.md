# İlk Gerçek Bildirim Adaptörü

Sipariş durumu değişince müşteriye **gerçek** SMS/WhatsApp gönderir;
sağlayıcı çökse bile atölyenin işi durmaz.

## Neler var?
- `Notifier` protokolü (structural typing) → bağımlılık tersine çevrildi
- `ConsoleNotifier`, `SmsNotifier`, `WhatsAppNotifier`
- `httpx.MockTransport` ile **ağa çıkmadan** test
- API anahtarı **sadece `.env`'de**; `repr`, log ve exception mesajlarında yok
- Rıza yoksa `SKIPPED` (istek atılmaz)
- Sağlayıcı 5xx → `FAILED`, sipariş durumu yine değişir

## Kurulum
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # .env içine SMS_API_URL / SMS_API_KEY gir
```

## Çalıştırma
```bash
# Konsol modu (varsayılan)
python main.py

# SMS modu
NOTIFY_CHANNEL=sms \
SMS_API_URL="https://provider.example/send" \
SMS_API_KEY="sk-..." \
python main.py
```

## Testler
```bash
pytest -v
```

Beklenen: `9 passed` (gerçek ağ yok).

## Kanal ekleme
1. `_HttpNotifierBase` alt sınıfı yaz, `channel` ve `_build_body` override et.
2. `build_notifier`'a bir `if` ekle.
3. `Settings`'e `xxx_api_url` / `xxx_api_key` ekle.
4. `.env.example`'a boş bırak.
