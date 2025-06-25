import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

# Web sitesinden manuel fiyat & stok çekme (yedek olarak duruyor)
def fiyat_ve_stok_cek(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')

        fiyat = None
        for span in soup.find_all("span"):
            if "₺" in span.text:
                fiyat = span.text.strip()
                break

        stok = "Stokta"
        if any(kelime in r.text.lower() for kelime in ["tükendi", "stokta yok", "kalmadı"]):
            stok = "Tükendi"

        return fiyat, stok

    except Exception as e:
        print(f"Hata: {e}")
        return None, None

# Telegram bot ile bildirim gönderme
def telegram_bildirim_gonder(bot_token, chat_id, mesaj):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": mesaj,
        "parse_mode": "HTML"
    }
    try:
        r = requests.post(url, data=data)
        print(f"Telegram yanıt kodu: {r.status_code}")
        print(f"Telegram yanıt içeriği: {r.text}")
        return r.status_code == 200
    except Exception as e:
        print(f"Telegram hatası: {e}")
        return False

# XML URL'den ürün linkine göre fiyat/stok çekme
def fiyat_ve_stok_cek_xml(xml_url, hedef_url):
    try:
        r = requests.get(xml_url, timeout=30)
        tree = ET.fromstring(r.content)

        for item in tree.findall(".//item"):
            link = item.find("link").text.strip()
            if link == hedef_url:
                fiyat = item.find("price").text.strip()
                stok_raw = item.find("quantity").text.strip()
                stok = "Tükendi" if stok_raw == "0" else "Stokta"
                return fiyat + " ₺", stok

        return "Ürün bulunamadı", "Bilinmiyor"

    except Exception as e:
        print(f"XML Hatası: {e}")
        return None, None

# Web sayfasından barkod çekme (yedek)
def barkod_cek(url):
    try:
        headers = { "User-Agent": "Mozilla/5.0" }
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')

        barkod_elem = soup.find("div", class_="product-detail")
        if barkod_elem:
            text = barkod_elem.get_text()
            for kelime in text.split():
                if kelime.isdigit() and len(kelime) >= 10:
                    return kelime

        return None
    except Exception as e:
        print(f"Barkod çekme hatası: {e}")
        return None

# Yerel XML dosyasından barkoda göre fiyat/stok/link çekme
def fiyat_ve_stok_cek_xml_by_barkod(xml_path, barkod):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        for item in root.findall(".//item"):
            barcode_elem = item.find("barcode")
            if barcode_elem is not None and barcode_elem.text.strip() == barkod:
                fiyat = item.find("price").text.strip() + " ₺"
                stok_raw = item.find("quantity").text.strip()
                stok = "Tükendi" if stok_raw == "0" else "Stokta"
                link = item.find("link").text.strip()
                return fiyat, stok, link

        return "Fiyat yok", "Stok bilinmiyor", None

    except Exception as e:
        print(f"Yerel XML okuma hatası: {e}")
        return None, None, None

# Fiyatları karşılaştırmak için normalize et
def normalize_fiyat(fiyat):
    if not fiyat:
        return ""
    return fiyat.replace("₺", "").replace(",", "").replace(".", "").strip()

# XML içinde bir barkod var mı kontrol et
def barkod_xml_iceriyor_mu(xml_path, barkod):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        for item in root.findall(".//item"):
            barcode_elem = item.find("barcode")
            if barcode_elem is not None and barcode_elem.text.strip() == barkod:
                return True

        return False
    except Exception as e:
        print(f"XML kontrol hatası: {e}")
        return False
import json

def load_data():
    with open("banka_veri.json", "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open("banka_veri.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

