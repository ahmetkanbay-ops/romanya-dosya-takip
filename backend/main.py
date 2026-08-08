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
    headers = {'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36'}
    # 1. Direkt dene
    try:
        print(f"DIREKT DENENIYOR: {url}")
        r = scraper.get(url, timeout=20)
        if '.pdf' in r.text.lower() and len(r.text) > 5000:
            print(f"DIREKT OK len={len(r.text)}")
            return r.text
    except Exception as e:
        print(f"Direkt fail: {e}")

    # 2. 5 Farkli Proxy dene - KATMAN 1
    proxy_list = [
        f"https://corsproxy.io/?{url}",
        f"https://api.allorigins.win/raw?url={url}",
        f"https://thingproxy.freeboard.io/fetch/{url}",
        f"https://api.codetabs.com/v1/proxy/?quest={url}",
        f"https://cors-anywhere.herokuapp.com/{url}",
    ]
    for p in proxy_list:
        try:
            print(f"Proxy dene: {p[:80]}")
            rr = requests.get(p, timeout=20, headers=headers)
            if '.pdf' in rr.text.lower() and len(rr.text) > 8000:
                print(f"PROXY OK! len={len(rr.text)}")
                return rr.text
        except Exception as e:
            print(f"Proxy fail: {e}")
            continue
    print("TUM PROXYLER FAIL!")
    return ""

def get_all_pdfs():
    pdfs = set()
    html = fetch_html_with_proxy(STADIU_URL)
    if not html:
        return []

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
            pdfs.add(h.split('?')[0].split('"')[0])

    print(f"STADIU'da {len(pdfs)} PDF")

    html2 = fetch_html_with_proxy(ORDINE_URL)
    if html2:
        for m in re.findall(r'https?://cetatenie\.just\.ro[^\s"\'<>]+\.pdf', html2, re.I):
            pdfs.add(m.split('?')[0].split('"')[0])

    print(f"TOPLAM {len(pdfs)} PDF bulundu")
    for p in list(pdfs)[:5]: print(f" - {p}")
    return list(pdfs)

def get_pdf_text(url):
    try:
        import fitz
        print(f"PDF okunuyor: {url[:80]}")
        try:
            r = scraper.get(url, timeout=30)
            content = r.content
        except:
            r = requests.get(f"https://corsproxy.io/?{url}", timeout=30)
            content = r.content
        doc = fitz.open(stream=content, filetype="pdf")
        text = "".join([p.get_text() for p in doc])
        print(f"PDF {len(text)} karakter okundu")
        return text
    except Exception as e:
        print(f"PDF HATA {url}: {e}")
        return ""

def contains(txt, no):
    if not txt: return False
    return no in txt or no in re.findall(r'\d+', txt)

@app.route("/api/sorgula", methods=["POST"])
def sorgula():
    try:
        data = request.get_json()
        dosya_no = ''.join(filter(str.isdigit, str(data.get("dosya_no",""))))
        if not dosya_no:
            return jsonify({"eslesti":False,"mesaj":"Numara gir"})

        if time.time() - CACHE["time"] > 3600 or not CACHE["pdfs"]:
            CACHE["pdfs"] = get_all_pdfs()
            CACHE["time"] = time.time()

        if not CACHE["pdfs"]:
            return jsonify({"eslesti":False,"durum":"YOK","mesaj":"Site engelliyor! Proxy de aşamadı, 0 PDF. Lütfen 10dk sonra dene","pdf_url":STADIU_URL,"liste_url":STADIU_URL})

        print(f"ARANAN {dosya_no} - {len(CACHE['pdfs'])} PDF icinde")
        for pdf_url in CACHE["pdfs"][:30]:
            txt = get_pdf_text(pdf_url)
            if dosya_no in txt:
                print(f"BULUNDU {dosya_no}")
                return jsonify({"eslesti":True,"durum":"VAR","mesaj":f"{dosya_no} BULUNDU!","pdf_url":pdf_url,"liste_url":pdf_url})

        return jsonify({"eslesti":False,"durum":"YOK","mesaj":f"{dosya_no} {len(CACHE['pdfs'])} PDF icinde YOK","pdf_url":STADIU_URL,"liste_url":STADIU_URL})
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"eslesti":False,"mesaj":f"Hata: {e}","pdf_url":STADIU_URL}), 500

@app.errorhandler(Exception)
def all_err(e):
    return jsonify({"eslesti":False,"mesaj":f"Hata: {e}"}), 500

@app.route("/api/version", methods=["GET"])
def version():
    return jsonify({"latest_version":"1.0.0"})

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status":"ok","count":len(CACHE["pdfs"])})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))