import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import time
from bs4 import BeautifulSoup
import cloudscraper

app = Flask(__name__)
CORS(app)

# Cloudflare'i aşmak için scraper
scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
)

STADIU_URL = "https://cetatenie.just.ro/stadiu-dosar/"
ORDINE_URL = "https://cetatenie.just.ro/ordine-2/"

CACHE = {"pdfs": [], "time": 0}

def get_pdf_text(url):
    try:
        import fitz
        r = scraper.get(url, timeout=60)
        r.raise_for_status()
        doc = fitz.open(stream=r.content, filetype="pdf")
        return "".join([p.get_text() for p in doc])
    except Exception as e:
        print(f"PDF OKUMA HATA {url}: {e}")
        return ""

def get_all_pdfs():
    all_pdfs = set()
    
    # 1. STADIU
    try:
        print(f"--> STADIU cekiliyor: {STADIU_URL}")
        r = scraper.get(STADIU_URL, timeout=30)
        soup = BeautifulSoup(r.text, 'html.parser')
        count = 0
        for a in soup.find_all('a', href=True):
            h = a['href']
            if h and h.lower().endswith('.pdf'):
                if not h.startswith('http'):
                    h = "https://cetatenie.just.ro" + h if h.startswith('/') else STADIU_URL + h
                all_pdfs.add(h)
                count += 1
        print(f"STADIU'da {count} PDF bulundu")
    except Exception as e:
        print(f"STADIU HATA: {e}")

    # 2. ORDINE-2 -> içindeki kategoriler -> PDF'ler
    try:
        print(f"--> ORDINE-2 cekiliyor: {ORDINE_URL}")
        r = scraper.get(ORDINE_URL, timeout=30)
        soup = BeautifulSoup(r.text, 'html.parser')
        cats = set()
        for a in soup.find_all('a', href=True):
            h = a['href']
            if h and ('ordine-articolul' in h or 'ordine-minori' in h):
                if not h.startswith('http'):
                    h = "https://cetatenie.just.ro" + h if h.startswith('/') else ORDINE_URL + h
                cats.add(h)
        
        print(f"ORDINE-2'de {len(cats)} kategori bulundu")
        
        for cat in cats:
            try:
                print(f"  Kategori taraniyor: {cat}")
                rr = scraper.get(cat, timeout=30)
                ss = BeautifulSoup(rr.text, 'html.parser')
                c = 0
                for aa in ss.find_all('a', href=True):
                    hh = aa['href']
                    if hh and hh.lower().endswith('.pdf'):
                        if not hh.startswith('http'):
                            hh = "https://cetatenie.just.ro" + hh if hh.startswith('/') else cat + hh
                        all_pdfs.add(hh)
                        c += 1
                print(f"    -> {c} PDF")
            except Exception as e:
                print(f"    Kategori hata {cat}: {e}")
                continue
                
    except Exception as e:
        print(f"ORDINE HATA: {e}")

    print(f"FINAL TOPLAM PDF SAYISI: {len(all_pdfs)}")
    return list(all_pdfs)

@app.route("/api/sorgula", methods=["POST"])
def sorgula():
    dosya_no = ''.join(filter(str.isdigit, str(request.get_json().get("dosya_no",""))))
    if not dosya_no:
        return jsonify({"eslesti": False, "mesaj": "Numara gir"}), 400

    if time.time() - CACHE["time"] > 3600 or not CACHE["pdfs"]:
        CACHE["pdfs"] = get_all_pdfs()
        CACHE["time"] = time.time()

    print(f"Aranan: {dosya_no} - Toplam {len(CACHE['pdfs'])} PDF'de bakilacak")

    for pdf_url in CACHE["pdfs"]:
        try:
            txt = get_pdf_text(pdf_url)
            if dosya_no in txt:
                print(f"BULUNDU! {dosya_no} -> {pdf_url}")
                return jsonify({
                    "eslesti": True,
                    "durum": "VAR",
                    "mesaj": f"{dosya_no} VAR",
                    "pdf_url": pdf_url,
                    "liste_url": pdf_url
                })
        except:
            continue

    print(f"BULUNAMADI: {dosya_no}")
    return jsonify({
        "eslesti": False,
        "durum": "YOK",
        "mesaj": f"{dosya_no} YOKTUR.",
        "pdf_url": STADIU_URL,
        "liste_url": STADIU_URL
    })

@app.route("/api/version", methods=["GET"])
def version():
    return jsonify({"latest_version": "1.0.0"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)