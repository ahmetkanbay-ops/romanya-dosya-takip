import os
import re
from flask import Flask, request, jsonify
from flask_cors import CORS
import time
from bs4 import BeautifulSoup
import cloudscraper

app = Flask(__name__)
CORS(app)

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
        full_text = "".join([p.get_text() for p in doc])
        print(f"PDF okundu {url} - {len(full_text)} karakter")
        return full_text
    except Exception as e:
        print(f"PDF OKUMA HATA {url}: {e}")
        return ""

def get_all_pdfs():
    all_pdfs = set()
    try:
        print(f"--> STADIU cekiliyor: {STADIU_URL}")
        r = scraper.get(STADIU_URL, timeout=30)
        soup = BeautifulSoup(r.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            h = a['href']
            if h and h.lower().endswith('.pdf'):
                if not h.startswith('http'):
                    h = "https://cetatenie.just.ro" + h if h.startswith('/') else STADIU_URL + h
                all_pdfs.add(h)
        print(f"STADIU'da {len(all_pdfs)} PDF bulundu")
    except Exception as e:
        print(f"STADIU HATA: {e}")

    try:
        print(f"--> ORDINE-2 cekiliyor: {ORDINE_URL}")
        r = scraper.get(ORDINE_URL, timeout=30)
        soup = BeautifulSoup(r.text, 'html.parser')
        cats = set()
        for a in soup.find_all('a', href=True):
            h = a['href']
            if h and ('ordine-articolul' in h or 'ordine-minori' in h or 'ordine' in h.lower()):
                if not h.startswith('http'):
                    h = "https://cetatenie.just.ro" + h if h.startswith('/') else ORDINE_URL + h
                if h.startswith('https://cetatenie.just.ro/ordine'):
                    cats.add(h)
        print(f"ORDINE'de {len(cats)} kategori bulundu")
        for cat in cats:
            try:
                rr = scraper.get(cat, timeout=30)
                ss = BeautifulSoup(rr.text, 'html.parser')
                for aa in ss.find_all('a', href=True):
                    hh = aa['href']
                    if hh and hh.lower().endswith('.pdf'):
                        if not hh.startswith('http'):
                            hh = "https://cetatenie.just.ro" + hh if hh.startswith('/') else cat + '/' + hh
                        all_pdfs.add(hh)
            except Exception as e:
                print(f" Kategori hata {cat}: {e}")
                continue
    except Exception as e:
        print(f"ORDINE HATA: {e}")

    print(f"FINAL TOPLAM PDF: {len(all_pdfs)}")
    return list(all_pdfs)

def pdf_contains_number(pdf_text, dosya_no):
    if not pdf_text:
        return False
    # 1. Düz ara
    if dosya_no in pdf_text:
        return True
    # 2. Noktaları silip ara (12.544 -> 12544)
    text_no_dots = pdf_text.replace(".", "").replace(",", "").replace(" ", "")
    if dosya_no in text_no_dots:
        return True
    # 3. Regex ile / ile birlikte ara
    pattern = rf'{dosya_no}\s*[/\.]?\s*\d{{0,4}}'
    if re.search(pattern, pdf_text):
        return True
    # 4. Sadece sayıları token olarak bul
    tokens = re.findall(r'\d+', pdf_text)
    if dosya_no in tokens:
        return True
    return False

@app.route("/api/sorgula", methods=["POST"])
def sorgula():
    dosya_no = ''.join(filter(str.isdigit, str(request.get_json().get("dosya_no",""))))
    if not dosya_no:
        return jsonify({"eslesti": False, "mesaj": "Numara gir"}), 400

    if time.time() - CACHE["time"] > 3600 or not CACHE["pdfs"]:
        CACHE["pdfs"] = get_all_pdfs()
        CACHE["time"] = time.time()

    print(f"=== ARANAN: {dosya_no} - {len(CACHE['pdfs'])} PDF'de ===")

    for pdf_url in CACHE["pdfs"]:
        try:
            txt = get_pdf_text(pdf_url)
            if pdf_contains_number(txt, dosya_no):
                print(f"BULUNDU! {dosya_no} -> {pdf_url}")
                return jsonify({
                    "eslesti": True,
                    "durum": "VAR",
                    "mesaj": f"{dosya_no} BULUNDU!",
                    "pdf_url": pdf_url,
                    "liste_url": pdf_url
                })
        except Exception as e:
            print(f"Arama hatasi {pdf_url}: {e}")
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