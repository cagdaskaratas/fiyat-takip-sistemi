import requests

def telegram_bildirim_gonder(bot_token, chat_id, mesaj):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": mesaj,
        "parse_mode": "HTML"
    }
    try:
        r = requests.post(url, data=data)
        print(f"Durum: {r.status_code}")
        print(f"Cevap: {r.text}")
        return r.status_code == 200
    except Exception as e:
        print(f"Hata: {e}")
        return False

# Test bilgileri
bot_token = "8164774178:AAGF0nTcw-Qp04qe9WxK7rZzqTmhnojS1qQ"
chat_id = "1534498228"
mesaj = "🔔 <b>Bu bir test mesajıdır.</b>\nSistem başarılı şekilde Telegram'a bağlandı."

telegram_bildirim_gonder(bot_token, chat_id, mesaj)
