## Amaç
Sipariş durumu değişince müşteriye gerçek bildirim gönderen ilk adaptörü ekler.
Bağımlılık `Notifier` protokolü üzerinden tersine çevrildi; `main.py` somut
sınıfa bağlı değil.

## Değişiklikler
- `notifications/service.py`: `Notifier` protokolü, `ConsoleNotifier`,
  `SmsNotifier`, `WhatsAppNotifier`, `build_notifier`, `notify_status_change`,
  `change_order_status`
- `core/config.py`: `notify_channel`, `sms_*`, `whatsapp_*` alanları
- `main.py`: `notifier or build_notifier(settings)` (DI)
- `httpx` prod bağımlılığına taşındı, sürüm sabitlendi (`0.27.2`)
- `tests/test_notifier_sms.py`: MockTransport tabanlı 9 test

## Güvenlik
- API anahtarı **yalnızca** `.env`'de; kodda/testte/PR'da yok
- `SmsNotifier.__repr__` ve `Settings.__repr__` anahtarı `***` olarak maskeler
- `notify_status_change` hata logu **sadece istisna tipini** yazar, mesajı
  loglamaz → anahtar sızması imkânsız
- Testte `caplog` + `repr` üzerinden sızma kontrolü var

## Test matrisi
| Senaryo | Beklenen | Test |
|---|---|---|
| 200 yanıt | `SENT` | `test_sms_sent_when_provider_returns_200` |
| 500 yanıt | `FAILED` + sipariş `SHIPPED` | `test_sms_failed_but_order_status_changes` |
| `0532 111 22 33` | istekte `+905321112233` | `test_phone_normalized_to_e164_in_request` |
| Rıza yok | `SKIPPED`, **istek yok** | `test_no_consent_skips_and_makes_no_request` |
| API anahtarı | log/repr'de yok | `test_api_key_not_leaked_in_logs` |

## 📌 KVKK / İYS Notu
SMS/WhatsApp ticari ileti gönderimi **İYS (İleti Yönetim Sistemi)** kapsamına
girer. `Order.consent` alanı açık rıza yerine geçer; `consent=False` iken istek
atılmaz (`SKIPPED`). Prod'a çıkmadan önce:
- İYS'ye hizmet sağlayıcı kaydı yapılmalı
- Ticari ileti onayı (VATANDAŞ onayı) toplanmalı
- Sağlayıcının `BrandCode`/`msgheader` alanları eklenmeli

## Sonraki adım
`send()` şu an senkron; ileride **outbox + worker** kuyruğuna taşınacak.
`timeout=5` şimdilik yeterli.

## Ekran görüntüsü
`docs/screenshots/real_sms.png` — gerçek sağlayıcıyla elle gönderim.
⚠️ Ekran görüntüsünde API anahtarı **yok**.