"""
ROMANYA DOSYA TAKIP - FINAL FIXED V2
Dosya: backend/main.py olarak yapıştır
"""
import os, time, random, re
import requests
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

# cloudscraper varsa kullan, yoksa requests ile devam
try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except:
    HAS_CLOUDSCRAPER = False

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
]

PROXY_CACHE = []
CACHE_TIME = 0

def get_proxies():
    global PROXY_CACHE, CACHE_TIME
    if PROXY_CACHE and time.time() - CACHE_TIME < 600:
        return PROXY_CACHE

    all_proxies = []
    urls = [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
    ]
    for url in urls:
        try:
            r = requests.get(url, timeout=8)
            if r.status_code == 200:
                for line in r.text.splitlines():
                    line=line.strip()
                    if ":" in line and len(line) < 25:
                        all_proxies.append(f"http://{line}")
                if len(all_proxies) > 15:
                    break
        except:
            continue
    
    # proxyscrape dene (senin eski)
    try:
        r = requests.get("https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all", timeout=10)
        for p in r.text.split("\r\n"):
            p=p.strip()
            if p:
                all_proxies.append(f"http://{p}")
    except:
        pass

    random.shuffle(all_proxies)
    PROXY_CACHE = list(dict.fromkeys(all_proxies))[:40] # uniq
    CACHE_TIME = time.time()
    print(f"Proxy listesi yenilendi: {len(PROXY_CACHE)} adet")
    return PROXY_CACHE

def fetch_with_smart_proxy(url: str, retries=8):
    proxies = get_proxies()
    
    headers_base = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ro-RO,ro;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://portal.just.ro/",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    # 1. Önce cloudscraper ile direkt dene (proxy'siz)
    if HAS_CLOUDSCRAPER:
        try:
            print("Cloudscraper ile direkt deneme...")
            scraper = cloudscraper.create_scraper(browser={'browser':'chrome','platform':'windows','mobile':False})
            resp = scraper.get(url, headers={**headers_base, "User-Agent": random.choice(USER_AGENTS)}, timeout=15)
            if resp.status_code == 200 and len(resp.text) > 1500:
                if "Just a moment" not in resp.text[:2000]:
                    return resp.text
        except Exception as e:
            print(f"Cloudscraper hata: {e}")

    # 2. Sonra normal requests + proxy rotation
    for attempt in range(retries):
        headers = {**headers_base, "User-Agent": random.choice(USER_AGENTS)}
        proxy = None
        proxy_url = None
        if proxies and attempt >= 1:
            proxy_url = random.choice(proxies)
            proxy = {"http": proxy_url, "https": proxy_url}

        try:
            print(f"Deneme {attempt+1}/{retries} | Proxy: {proxy_url if proxy_url else 'DIRECT'}")
            resp = requests.get(url, headers=headers, proxies=proxy, timeout=12, verify=False)
            if resp.status_code == 200 and len(resp.text) > 1000:
                lower = resp.text.lower()
                if "access denied" not in lower[:1000] and "forbidden" not in lower[:500]:
                    return resp.text
            time.sleep(random.uniform(0.5, 1.5))
        except Exception as e:
            print(f"Proxy hata {proxy_url}: {e}")
            if proxy_url in proxies:
                proxies.remove(proxy_url)
            time.sleep(0.5)
            continue
    
    raise Exception("Site engelliyor! Proxy de aşamadı")

@app.get("/")
def root():
    return {"count":0, "status":"ok", "message":"Backend canlı - proxy fix aktif V2"}

@app.get("/api/dosya")
def sorgula(nr: str = Query(..., description="Dosya numarası, örn 12544")):
    nr = nr.strip()
    search_url = f"https://portal.just.ro/SitePages/Dosare.aspx?k={nr}"

    try:
        html = fetch_with_smart_proxy(search_url)
        
        has_pdf = ".pdf" in html.lower() or "ordine" in html.lower() or "dosar" in html.lower()
        
        if has_pdf and len(html) > 2000:
            return {
                "nr": nr,
                "status": "VAR",
                "stadiu": "Dosar gasit - V2 ile çekildi",
                "ordine": "Ordin disponibil",
                "pdf_url": search_url,
                "count": 1,
                "html_preview": html[:2000]
            }
        else:
            # Site döndü ama sonuç yok - bu da başarı sayılır, proxy aştı
            if len(html) > 2000:
                return {
                    "nr": f"{nr}",
                    "status": "YOK",
                    "message": f"Dosya bulunamadı ama siteye erişildi (proxy aşıldı). HTML uzunluk: {len(html)}",
                    "count": 0
                }
            return {
                "nr": f"{nr} - YOK",
                "status": "YOK",
                "message": "Site engelliyor! Proxy de aşamadı, 0 PDF. Lütfen 10dk sonra dene",
                "count": 0
            }

    except Exception as e:
        return {
            "nr": f"{nr} - YOK",
            "status": "HATA",
            "message": f"Site engelliyor! Proxy de aşamadı, 0 PDF. Lütfen 10dk sonra dene ({str(e)[:120]})",
            "count": 0
        }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
