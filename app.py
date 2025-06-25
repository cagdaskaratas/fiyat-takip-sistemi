import os
from datetime import datetime
from utils import load_data, save_data
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
import matplotlib
matplotlib.use('Agg')  # Sunucuda arayüz açmadan dosyaya kaydetmek için
import matplotlib.pyplot as plt


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
        if kullanici == "admin" and sifre == "FtK2gQvsSjf@$":
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

import json
from flask import Flask, render_template, request, redirect


def load_finans():
    if not os.path.exists("finans.json"):
        return {"expenses": [], "incomes": []}
    with open("finans.json", "r", encoding="utf-8") as f:
        return json.load(f)

def save_finans(data):
    with open("finans.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

@app.route("/finans/gelir-gider", methods=["GET", "POST"])
@login_required
def finans_gelir_gider():
    data = load_finans()

    if request.method == "POST":
        if 'expense_submit' in request.form:
            new_expense = {
                "amount": float(request.form["expense_amount"]),
                "category": request.form["expense_category"],
                "description": request.form["expense_description"]
            }
            data["expenses"].append(new_expense)

        elif 'income_submit' in request.form:
            new_income = {
                "amount": float(request.form["income_amount"]),
                "category": request.form["income_category"],
                "description": request.form["income_description"]
            }
            data["incomes"].append(new_income)

        elif 'arsiv_al' in request.form:
            secilen_ay = request.form["arsiv_ayi"]
            arsave_path = "arsiv.json"

            if not os.path.exists(arsave_path):
                with open(arsave_path, "w", encoding="utf-8") as f:
                    json.dump({}, f)

            with open(arsave_path, "r", encoding="utf-8") as f:
                arsiv_data = json.load(f)

            if secilen_ay not in arsiv_data:
                arsiv_data[secilen_ay] = {
                    "expenses": data["expenses"],
                    "incomes": data["incomes"]
                }

                with open(arsave_path, "w", encoding="utf-8") as f:
                    json.dump(arsiv_data, f, indent=2, ensure_ascii=False)

                # Ay sonu sonrası verileri temizle
                data["expenses"] = []
                data["incomes"] = []
                flash(f"{secilen_ay} ayı başarıyla arşivlendi. Mevcut veriler sıfırlandı.", "success")
            else:
                flash(f"{secilen_ay} zaten daha önce arşivlenmiş.", "warning")

        save_finans(data)
        return redirect("/finans/gelir-gider")

    # GET metodunda burası çalışır
    total_expense = sum([e["amount"] for e in data["expenses"]])
    total_income = sum([i["amount"] for i in data["incomes"]])

    return render_template(
        "finans_gelir_gider.html",
        expenses=data["expenses"],
        incomes=data["incomes"],
        total_expense=total_expense,
        total_income=total_income
    )

@app.route("/finans/sil/gider/<int:index>", methods=["POST"])
def sil_gider(index):
    data = load_finans()
    if 0 <= index < len(data["expenses"]):
        del data["expenses"][index]
        save_finans(data)
    return redirect("/finans/gelir-gider")

@app.route("/finans/sil/gelir/<int:index>", methods=["POST"])
def sil_gelir(index):
    data = load_finans()
    if 0 <= index < len(data["incomes"]):
        del data["incomes"][index]
        save_finans(data)
    return redirect("/finans/gelir-gider")



@app.route("/finans/banka", methods=["GET", "POST"])
@login_required
def banka_bilgilerim():
    path = "banka_veri.json"
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"hesaplar": [], "borclar": []}, f)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if request.method == "POST":
        if "hesap_ekle" in request.form:
            yeni_id = max([h.get("id", 0) for h in data["hesaplar"]], default=0) + 1
            yeni_hesap = {
                "id": yeni_id,
                "banka_adi": request.form["banka_adi"],
                "sifre": request.form["sifre"]
            }
            data["hesaplar"].append(yeni_hesap)

        elif "borc_ekle" in request.form:
            yeni_id = max([b.get("id", 0) for b in data["borclar"]], default=0) + 1
            yeni_borc = {
                "id": yeni_id,
                "banka": request.form["borc_banka"],
                "faiz": float(request.form["faiz"]),
                "cekilen": float(request.form["cekilen"]),
                "taksit": float(request.form["taksit"]),
                "kalan": float(request.form["kalan"]),
                "tarih": request.form["taksit_tarihi"]
            }
            data["borclar"].append(yeni_borc)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        return redirect("/finans/banka")

    toplam_kalan = sum([b["kalan"] for b in data["borclar"]])
    return render_template("banka_bilgilerim.html", hesaplar=data["hesaplar"], borclar=data["borclar"], toplam_kalan=toplam_kalan)


@app.route("/hesap-guncelle", methods=["POST"])
@login_required
def hesap_guncelle():
    data = load_data()
    hesaplar_guncel = []

    try:
        toplam = int(request.form.get("toplam", 0))
    except ValueError:
        toplam = 0

    for i in range(toplam):
        try:
            hesap_id = int(request.form.get(f"id_{i}", "0"))
        except ValueError:
            continue  # ID dönüştürülemezse o satırı atla

        banka_adi = request.form.get(f"banka_adi_{i}", "").strip()
        sifre = request.form.get(f"sifre_{i}", "").strip()

        if banka_adi:  # boş olanları at
            hesaplar_guncel.append({
                "id": hesap_id,
                "banka_adi": banka_adi,
                "sifre": sifre
            })

    data["hesaplar"] = hesaplar_guncel
    save_data(data)
    flash("Banka hesapları başarıyla güncellendi.", "success")
    return redirect("/finans/banka")

@app.route("/hesap-sil/<int:hesap_id>")
@login_required
def hesap_sil(hesap_id):
    data = load_data()
    data["hesaplar"] = [h for h in data["hesaplar"] if h.get("id") != hesap_id]
    save_data(data)
    flash("Banka hesabı silindi.", "success")  # ✅ uyarı eklendi
    return redirect("/finans/banka")

@app.route("/borc-guncelle", methods=["POST"])
def borc_guncelle():
    data = load_data()
    borclar_guncel = []

    toplam = int(request.form["toplam"])
    for i in range(toplam):
        borclar_guncel.append({
            "id": int(request.form[f"id_{i}"]),
            "banka": request.form[f"banka_{i}"],
            "faiz": float(request.form[f"faiz_{i}"]),
            "cekilen": float(request.form[f"cekilen_{i}"]),
            "taksit": float(request.form[f"taksit_{i}"]),
            "kalan": float(request.form[f"kalan_{i}"]),
            "tarih": request.form[f"tarih_{i}"]
        })

    data["borclar"] = borclar_guncel
    save_data(data)
    return redirect("/banka-bilgilerim")

from flask import flash

@app.route("/borc-sil/<int:borc_id>")
@login_required
def borc_sil(borc_id):
    data = load_data()
    data["borclar"] = [b for b in data["borclar"] if b.get("id") != borc_id]
    save_data(data)
    flash("Borç başarıyla silindi.", "success")
    return redirect("/finans/banka")


@app.route("/kisiler", methods=["GET", "POST"])
@login_required
def kisiler():
    path = "kisiler_veri.json"
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"verilecekler": [], "alacaklar": []}, f)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if request.method == "POST":
        if "verilecek_ekle" in request.form:
            yeni_id = max([v.get("id", 0) for v in data["verilecekler"]], default=0) + 1
            data["verilecekler"].append({
                "id": yeni_id,
                "kisi": request.form["ver_kisi"],
                "tutar": float(request.form["ver_tutar"])
            })

        elif "alacak_ekle" in request.form:
            yeni_id = max([a.get("id", 0) for a in data["alacaklar"]], default=0) + 1
            data["alacaklar"].append({
                "id": yeni_id,
                "kisi": request.form["al_kisi"],
                "tutar": float(request.form["al_tutar"])
            })

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        return redirect("/kisiler")

    toplam_verilecek = sum([v["tutar"] for v in data["verilecekler"]])
    toplam_alacak = sum([a["tutar"] for a in data["alacaklar"]])

    return render_template(
        "kisiler.html",
        verilecekler=data["verilecekler"],
        alacaklar=data["alacaklar"],
        toplam_verilecek=toplam_verilecek,
        toplam_alacak=toplam_alacak
    )
@app.route("/verilecek-sil/<int:id>")
@login_required
def verilecek_sil(id):
    path = "kisiler_veri.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["verilecekler"] = [v for v in data["verilecekler"] if v["id"] != id]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return redirect("/kisiler")

@app.route("/alacak-sil/<int:id>")
@login_required
def alacak_sil(id):
    path = "kisiler_veri.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["alacaklar"] = [a for a in data["alacaklar"] if a["id"] != id]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return redirect("/kisiler")


@app.route("/verilecek-guncelle", methods=["POST"])
@login_required
def verilecek_guncelle():
    path = "kisiler_veri.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    toplam = int(request.form["toplam"])
    for i in range(toplam):
        id_ = int(request.form[f"id_{i}"])
        for v in data["verilecekler"]:
            if v["id"] == id_:
                v["kisi"] = request.form[f"kisi_{i}"]
                v["tutar"] = float(request.form[f"tutar_{i}"])
                break

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    flash("Verilecekler başarıyla güncellendi.", "success")
    return redirect("/kisiler")

@app.route("/alacak-guncelle", methods=["POST"])
@login_required
def alacak_guncelle():
    path = "kisiler_veri.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    toplam = int(request.form["toplam"])
    for i in range(toplam):
        id_ = int(request.form[f"id_{i}"])
        for a in data["alacaklar"]:
            if a["id"] == id_:
                a["kisi"] = request.form[f"kisi_{i}"]
                a["tutar"] = float(request.form[f"tutar_{i}"])
                break

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    flash("Alacaklar başarıyla güncellendi.", "success")
    return redirect("/kisiler")

@app.route("/birikimler", methods=["GET", "POST"])
@login_required
def birikimler():
    path = "birikimler.json"
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"birikimler": []}, f)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if request.method == "POST":
        if "birikim_ekle" in request.form:
            yeni_id = max([b.get("id", 0) for b in data["birikimler"]], default=0) + 1
            yeni_birikim = {
                "id": yeni_id,
                "ad": request.form["birikim_ad"],
                "miktar": float(request.form["miktar"]),
                "deger": float(request.form["deger"]),
                "alis": float(request.form["alis"]),
                "tarih": request.form["tarih"]
            }
            data["birikimler"].append(yeni_birikim)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            flash("Birikim başarıyla eklendi.", "success")
            return redirect("/birikimler")

    toplam_deger = sum([b.get("deger", 0) for b in data["birikimler"]])
    return render_template("birikimler.html", birikimler=data["birikimler"], toplam_deger=toplam_deger)

@app.route("/birikim-guncelle", methods=["POST"])
@login_required
def birikim_guncelle():
    path = "birikimler.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    toplam = int(request.form["toplam"])
    for i in range(toplam):
        bid = int(request.form.get(f"id_{i}", 0))
        for b in data["birikimler"]:
            if b["id"] == bid:
                b["ad"] = request.form.get(f"ad_{i}")
                b["miktar"] = float(request.form.get(f"miktar_{i}", 0))
                b["deger"] = float(request.form.get(f"deger_{i}", 0))
                b["alis"] = float(request.form.get(f"alis_{i}", 0))
                b["tarih"] = request.form.get(f"tarih_{i}")
                break

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    flash("Birikimler başarıyla güncellendi.", "success")
    return redirect("/birikimler")
@app.route("/birikim-sil/<int:bid>")
@login_required
def birikim_sil(bid):
    path = "birikimler.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    data["birikimler"] = [b for b in data["birikimler"] if b["id"] != bid]

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    flash("Birikim silindi.", "warning")
    return redirect("/birikimler")


@app.route("/finans/grafikler")
@login_required
def grafikler():
    with open("finans.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    giderler = data.get("expenses", [])
    gelirler = data.get("incomes", [])

    # Gider kategorilerini hesapla
    gider_kategoriler = {}
    for g in giderler:
        kategori = g.get("category", "Bilinmeyen")
        tutar = float(g.get("amount", 0))
        gider_kategoriler[kategori] = gider_kategoriler.get(kategori, 0) + tutar

    # Gelir kategorilerini hesapla
    gelir_kategoriler = {}
    for g in gelirler:
        kategori = g.get("category", "Bilinmeyen")
        tutar = float(g.get("amount", 0))
        gelir_kategoriler[kategori] = gelir_kategoriler.get(kategori, 0) + tutar

    return render_template("grafikler.html",
                           gider_labels=list(gider_kategoriler.keys()),
                           gider_values=list(gider_kategoriler.values()),
                           gelir_labels=list(gelir_kategoriler.keys()),
                           gelir_values=list(gelir_kategoriler.values()))



@app.route("/finans/arsiv")
@login_required
def finans_arsiv():
    arsivler = {}
    if os.path.exists("arsiv.json"):
        with open("arsiv.json", "r", encoding="utf-8") as f:
            arsivler = json.load(f)

        # Convert amount values to float and hesapla
        for ay in arsivler:
            toplam_gider = 0.0
            toplam_gelir = 0.0

            for entry in arsivler[ay]["expenses"]:
                try:
                    entry["amount"] = float(str(entry["amount"]).replace("₺", "").strip())
                except:
                    entry["amount"] = 0.0
                toplam_gider += entry["amount"]

            for entry in arsivler[ay]["incomes"]:
                try:
                    entry["amount"] = float(str(entry["amount"]).replace("₺", "").strip())
                except:
                    entry["amount"] = 0.0
                toplam_gelir += entry["amount"]

            # ekle
            arsivler[ay]["toplam_gider"] = toplam_gider
            arsivler[ay]["toplam_gelir"] = toplam_gelir

    return render_template("arsiv.html", arsivler=arsivler)

@app.route("/finans/arsiv-sil", methods=["POST"])
@login_required
def arsiv_sil():
    silinecek_ay = request.form.get("ay")
    arsiv_yolu = "arsiv.json"

    if os.path.exists(arsiv_yolu):
        with open(arsiv_yolu, "r", encoding="utf-8") as f:
            arsiv_data = json.load(f)

        if silinecek_ay in arsiv_data:
            del arsiv_data[silinecek_ay]

            with open(arsiv_yolu, "w", encoding="utf-8") as f:
                json.dump(arsiv_data, f, indent=2, ensure_ascii=False)

            flash(f"{silinecek_ay} ayı başarıyla silindi.", "success")
        else:
            flash(f"{silinecek_ay} ayı bulunamadı.", "warning")

    return redirect(url_for("finans_arsiv"))

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

