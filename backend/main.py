import os
import re
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
from bs4 import BeautifulSoup
import cloudscraper

app = Flask(__name__)
CORS(app)

# Cloudflare'i aşmak için güçlü scraper
scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False},
    delay=10
)

STADIU_URL = "https://cetatenie.just.ro/stadiu-dosar/"
ORDINE_URL = "https://cetatenie.just.ro/ordine-2/"
CACHE = {"pdfs": [], "time": 0}

def get_pdf_text(url):
    try:
        import fitz
        print(f"PDF indiriliyor: {url}")
        r = scraper.get(url, timeout=90)
        r.raise_for_status()
        doc = fitz.open(stream=r.content, filetype="pdf")
        text = "".join([p.get_text() for p in doc])
        print(f"PDF okundu: {len(text)} karakter - {url}")
        return text
    except Exception as e:
        print(f"PDF OKUMA HATA {url}: {e}")
        return ""

def extract_pdfs_from_html(html, base_url):
    pdfs = set()
    # Yöntem 1: a[href]
    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.find_all('a', href=True):
        h = a['href']
        if h and '.pdf' in h.lower():
            if not h.startswith('http'):
                if h.startswith('/'):
                    h = "https://cetatenie.just.ro" + h
                else:
                    h = base_url + h if base_url.endswith('/') else base_url + '/' + h
            # temizle? sonrası vs
            h = h.split('?')[0]
            if h.lower().endswith('.pdf'):
                pdfs.add(h)
    # Yöntem 2: Regex ile sayfada geçen tüm pdf linkleri
    for match in re.findall(r'https?://[^\s"\'<>]+\.pdf', html, re.IGNORECASE):
        pdfs.add(match.split('?')[0])

    return pdfs

def get_all_pdfs():
    all_pdfs = set()

    # 1. STADIU
    try:
        print(f"--> STADIU cekiliyor: {STADIU_URL}")
        r = scraper.get(STADIU_URL, timeout=60)
        print(f"STADIU status: {r.status_code}, uzunluk: {len(r.text)}")
        if len(r.text) < 5000:
            print(f"STADIU HTML ilk 1000: {r.text[:1000]}")

        found = extract_pdfs_from_html(r.text, STADIU_URL)
        print(f"STADIU'da {len(found)} PDF bulundu")
        for f in found:
            print(f" - {f}")
        all_pdfs.update(found)
    except Exception as e:
        print(f"STADIU HATA: {e}")

    # 2. ORDINE-2
    try:
        print(f"--> ORDINE-2 cekiliyor: {ORDINE_URL}")
        r = scraper.get(ORDINE_URL, timeout=60)
        print(f"ORDINE-2 status: {r.status_code}, uzunluk: {len(r.text)}")
        soup = BeautifulSoup(r.text, 'html.parser')
        cats = set()
        for a in soup.find_all('a', href=True):
            h = a['href']
            if h and 'ordine' in h.lower():
                if not h.startswith('http'):
                    if h.startswith('/'):
                        h = "https://cetatenie.just.ro" + h
                    else:
                        h = ORDINE_URL + h
                # kategori linkleri genelde /ordine-articolul-10/ gibi
                if h.startswith('https://cetatenie.just.ro/ordine'):
                    cats.add(h)

        # Regex ile de kategori bul
        for m in re.findall(r'https://cetatenie\.just\.ro/ordine[^"\'\s<>]+', r.text):
            cats.add(m.split('?')[0])

        print(f"ORDINE-2'de {len(cats)} kategori bulundu")

        for cat in list(cats)[:30]: # ilk 30 kategori yeterli
            try:
                print(f" Kategori: {cat}")
                rr = scraper.get(cat, timeout=60)
                found = extract_pdfs_from_html(rr.text, cat)
                print(f" -> {len(found)} PDF")
                all_pdfs.update(found)
                time.sleep(1) # Cloudflare kızmasın
            except Exception as e:
                print(f" Kategori hata {cat}: {e}")
                continue

    except Exception as e:
        print(f"ORDINE HATA: {e}")

    print(f"FINAL TOPLAM PDF SAYISI: {len(all_pdfs)}")