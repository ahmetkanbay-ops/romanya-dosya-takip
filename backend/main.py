import os, re, time, traceback, requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from bs4 import BeautifulSoup
import cloudscraper

app = Flask(__name__)
CORS(app)

scraper = cloudscraper.create_scraper(browser={'browser':'chrome','platform':'windows'}, delay=3)
STADIU_URL = "https://cetatenie.just.ro/stadiu-dosar/"
ORDINE_URL = "https://cetatenie.just.ro/ordine-2/"
CACHE = {"pdfs": [], "time": 0}

def fetch_html_with_proxy(url):
    # YÖNTEM 1: Direkt dene
    try:
        print(f"Direkt deneniyor: {url}")
        r = scraper.get(url, timeout=20)
        if '.pdf' in r.text.lower():
            print(f"Direkt BAŞARILI len={len(r.text)}")
            return r.text
    except Exception as e:
        print(f"Direkt hata: {e}")

    # YÖNTEM 2: Proxy ile dene - BU RENDER ENGELİNİ AŞIYOR
    proxies_to_try = [
        f"https://api.allorigins.win/raw?url={url}",
        f"https://api.codetabs.com/v1/proxy/?quest={url}",
    ]
    for purl in proxies_to_try:
        try:
            print(f"Proxy deneniyor: {purl[:80]}")
            rr = requests.get(purl, timeout=20, headers={'User-Agent':'Mozilla/5.0'})
            if '.pdf' in rr.text.lower() and len(rr.text) > 5000:
                print(f"PROXY BAŞARILI! len={len(rr.text)}")
                return rr.text
        except Exception as e:
            print(f"Proxy hata {purl}: {e}")
            continue
    return ""

def get_all_pdfs():
    html = fetch_html_with_proxy(STADIU_URL)
    pdfs = set()
    if not html:
        print("HTML HİÇ ALINAMADI!")
        return []

    # PDF leri ayıkla
    for m in re.findall(r'https?://cetatenie\.just\.ro[^\s"\'<>]+\.pdf', html, re.I):
        pdfs.add(m.split('?')[0].split('"')[0])
    for m in re.findall(r'/wp-content/uploads/[^\s"\'<>]+\.pdf', html, re.I):
        pdfs.add("https://cetatenie.just.ro" + m.split('?')[0])

    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.find_all('a', href=True):
        h = a['href']
        if h and '.pdf' in h.lower():
            if not h.startswith('http'):
                h = "https://cetatenie.just.ro" + h if h.startswith('/') else STADIU_URL + h
            pdfs.add(h.split('?')[0])

    print(f"TOPLAM {len(pdfs)} PDF bulundu:")
    for p in list(pdfs)[:10]: print(f" - {p}")

    # ORDINE-2 yi de proxy ile al
    html2 = fetch_html_with_proxy(ORDINE_URL)
    if html2:
        for m in re.findall(r'https?://cetatenie\.just\.ro[^\s"\'<>]+\.pdf', html2, re.I):
            pdfs.add(m.split('?')[0])

    return list(pdfs)

def get_pdf_text(url):
    try:
        import fitz
        print(f"PDF okunuyor: {url}")
        # PDF yi de proxy ile indir dene
        try:
            r = scraper.get(url, timeout=30)
        except:
            r = requests.get(f"https://api.allorigins.win/raw?url={url}", timeout=30)
        doc = fitz.open(stream=r.content, filetype="pdf")
        text = "".join([p.get_text() for p in doc])
        print(f"PDF {len(text)} karakter")
        return text
    except Exception as e:
        print(f"PDF hata: {e}")
        return ""

@app.route("/api/sorgula", methods=["POST"])
def sorgula():
    try:
        dosya_no = ''.join(filter(str.isdigit, str(request.get_json().get("dosya_no",""))))
        if not dosya_no: return jsonify({"eslesti":False,"mesaj":"Numara gir"})

        if time.time() - CACHE["time"] > 3600 or not CACHE["pdfs"]:
            CACHE["pdfs"] = get_all_pdfs()
            CACHE["time"] = time.time()

        if not CACHE["pdfs"]:
            return jsonify({"eslesti":False,"mesaj":"Site engelliyor! Proxy de aşamadı, 0 PDF. Lütfen 10dk sonra dene","pdf_url":STADIU_URL})

        print(f"ARANAN {dosya_no} - {len(CACHE['pdfs'])} PDF içinde")
        for pdf_url in CACHE["pdfs"][:30]:
            txt = get_pdf_text(pdf_url)
            if dosya_no in txt or dosya_no in re.findall(r'\d+', txt):
                print(f"BULUNDU {dosya_no}")
                return jsonify({"eslesti":True,"durum":"VAR","mesaj":f"{dosya_no} BULUNDU!","pdf_url":pdf_url,"liste_url":pdf_url})

        return jsonify({"eslesti":False,"durum":"YOK","mesaj":f"{dosya_no} {len(CACHE['pdfs'])} PDF içinde YOK","pdf_url":STADIU_URL})
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"eslesti":False,"mesaj":f"Hata: {e}"}), 500

@app.route("/api/version", methods=["GET"])
def version(): return jsonify({"latest_version":"1.0.0"})
@app.route("/", methods=["GET"])
def home(): return jsonify({"status":"ok","count":len(CACHE["pdfs"])})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))