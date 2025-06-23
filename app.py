from flask import Flask, render_template, request, redirect
import json
import os
from datetime import datetime
from functools import wraps
from flask import request, Response
from flask import Flask, render_template, request, redirect, session, url_for
from utils import (
    fiyat_ve_stok_cek,
    fiyat_ve_stok_cek_xml,
    fiyat_ve_stok_cek_xml_by_barkod,
    barkod_xml_iceriyor_mu,
    telegram_bildirim_gonder,
    normalize_fiyat
)
from apscheduler.schedulers.background import BackgroundScheduler
import xml.etree.ElementTree as ET

app = Flask(__name__)
app.secret_key = "gizli-anahtar"

from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("giris_yapildi"):
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        kullanici = request.form["username"]
        sifre = request.form["password"]
        if kullanici == "admin" and sifre == "123456":
            session["giris_yapildi"] = True
            return redirect("/")
        else:
            return render_template("login.html", hata="Hatalı kullanıcı adı veya şifre")

    return render_template("login.html")


DATA_FILE = 'data.json'
XML_PATH = 'export.xml'
BOT_TOKEN = '8164774178:AAGF0nTcw-Qp04qe9WxK7rZzqTmhnojS1qQ'
CHAT_ID = '1534498228'

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump([], f)

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        barkod = request.form.get("barkod")
        satis_fiyati = request.form.get("satis_fiyati")
        kazanc = request.form.get("kazanc")

        if not barkod or not satis_fiyati or not kazanc:
            return redirect("/")

        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        fiyat, stok, url = fiyat_ve_stok_cek_xml_by_barkod(XML_PATH, barkod)
        if not url:
            return redirect("/")

        yeni_urun = {
            "barkod": barkod,
            "url": url,
            "last_price": fiyat,
            "last_stock": stok,
            "satis_fiyati": satis_fiyati,
            "kazanc": kazanc
        }

        data.insert(0, yeni_urun)

        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return redirect("/")

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        links = json.load(f)

    sayfa = int(request.args.get("sayfa", 1))
    sayfa_basi = 10
    toplam_sayfa = (len(links) + sayfa_basi - 1) // sayfa_basi
    basla = (sayfa - 1) * sayfa_basi
    bitir = basla + sayfa_basi
    gosterilecekler = links[basla:bitir]

    return render_template("index.html",
                           links=gosterilecekler,
                           sayfa=sayfa,
                           toplam_sayfa=toplam_sayfa)

@app.route("/satis-ekle", methods=["GET", "POST"])
@login_required
def satis_ekle():
    if request.method == "POST":
        urun_adi = request.form["urun_adi"]
        kazanc = float(request.form["kazanc"])

        with open("satilanlar.json", "r+", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except:
                data = []

            data.append({
                "urun_adi": urun_adi,
                "kazanc": kazanc,
                "tarih": datetime.now().strftime("%Y-%m-%d")
            })
            f.seek(0)
            json.dump(data, f, indent=4, ensure_ascii=False)

        return redirect("/gelirler")
    return render_template("satis-ekle.html")

@app.route("/gelirler")
@login_required
def gelirler():
    try:
        with open("satilanlar.json", "r", encoding="utf-8") as f:
            satislar = json.load(f)
    except:
        satislar = []

    grafik_verisi = {}
    for s in satislar:
        tarih = s["tarih"]
        grafik_verisi[tarih] = grafik_verisi.get(tarih, 0) + s["kazanc"]

    return render_template("gelirler.html", grafik=grafik_verisi)

@app.route('/urun-kontrol')
@login_required
def urun_kontrol():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    yeni_data = []

    for item in data:
        barkod = item.get('barkod')

        if not barkod_xml_iceriyor_mu(XML_PATH, barkod):
            telegram_bildirim_gonder(
                bot_token=BOT_TOKEN,
                chat_id=CHAT_ID,
                mesaj=f"❌ <b>Ürün XML'den Kaldırıldı</b>\n{item['url']}\nBarkod: {barkod}"
            )
            continue

        eski_fiyat = item.get('last_price')
        eski_stok = item.get('last_stock')
        fiyat, stok, _ = fiyat_ve_stok_cek_xml_by_barkod(XML_PATH, barkod)

        if fiyat and normalize_fiyat(fiyat) != normalize_fiyat(eski_fiyat):
            item['last_price'] = fiyat
            telegram_bildirim_gonder(
                bot_token=BOT_TOKEN,
                chat_id=CHAT_ID,
                mesaj=f"📢 <b>Fiyat Değişti</b>\n{item['url']}\nYeni Fiyat: {fiyat}"
            )

        if stok and stok.lower() != (eski_stok or "").lower():
            item['last_stock'] = stok
            telegram_bildirim_gonder(
                bot_token=BOT_TOKEN,
                chat_id=CHAT_ID,
                mesaj=f"📢 <b>Stok Değişti</b>\n{item['url']}\nYeni Stok: {stok}"
            )

        yeni_data.append(item)

    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(yeni_data, f, indent=2, ensure_ascii=False)

    return redirect('/')

@app.route('/yeni-urun-sorgu')
@login_required
def yeni_urun_sorgu():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    data_barkodlar = set(item['barkod'] for item in data)

    try:
        tree = ET.parse(XML_PATH)
        root = tree.getroot()
        yeni_sayac = 0

        for item in root.findall(".//item"):
            barkod_elem = item.find("barcode")
            if barkod_elem is None:
                continue

            barkod = barkod_elem.text.strip()
            if barkod in data_barkodlar:
                continue

            fiyat = item.find("price").text.strip() + " ₺"
            stok_raw = item.find("quantity").text.strip()
            stok = "Tükendi" if stok_raw == "0" else "Stokta"
            link = item.find("link").text.strip()

            data.append({
                'url': link,
                'barkod': barkod,
                'last_price': fiyat,
                'last_stock': stok
            })

            telegram_bildirim_gonder(
                bot_token=BOT_TOKEN,
                chat_id=CHAT_ID,
                mesaj=f"🆕 <b>Yeni Ürün Eklendi</b>\n{link}\nFiyat: {fiyat}\nStok: {stok}"
            )
            yeni_sayac += 1

        if yeni_sayac > 0:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

    except Exception as e:
        return f"XML Hatası: {e}", 500

    return redirect('/')

@app.route('/sil/<string:barkod>')
@login_required
def sil(barkod):
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    yeni_data = [item for item in data if item.get("barkod") != barkod]

    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(yeni_data, f, indent=2, ensure_ascii=False)

    return redirect('/')

# Zamanlı kontrol
def zamanli_kontrol():
    with app.app_context():
        urun_kontrol()

scheduler = BackgroundScheduler()
scheduler.add_job(zamanli_kontrol, 'interval', hours=1)
scheduler.start()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

