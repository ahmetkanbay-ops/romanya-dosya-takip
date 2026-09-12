# -*- coding: utf-8 -*-
"""
Uygulamanın herkese açık tanıtım (landing) sayfası -- backend'in kök
adresinde ("/") sunulur. Önceden bu adres sadece boş bir sağlık kontrolü
JSON'u ("status: ok") döndürüyordu, hiçbir işe yaramıyordu (2026-08-20,
kullanıcı isteği: Instagram'da paylaşılabilecek, Play Console'un "web
sitesi" alanına girilebilecek gerçek bir sayfa).

Mobil uygulamanın kullandığı sağlık kontrolü ayrı bir adreste
(/api/durum), bu sayfaya HİÇ dokunmuyor -- ikisi birbirinden bağımsız.

2026-09-12 YENİDEN TASARIM (kullanıcı isteği): Bir Instagram kaynağından
gelen "Framer Motion + UI/UX Pro Max skill + 21st.dev" tarifi
değerlendirildi -- Framer Motion (React kütüphanesi) bu projede
KULLANILMADI çünkü bu sayfa düz Python/HTML/CSS ile üretiliyor, React
build sistemi kurmak "redesign" kapsamının çok ötesine geçip gerçek bir
mimari riski yaratırdı. Aynı görsel hedefe (scroll'da beliren, hover'da
hareket eden animasyonlar) düz CSS + /statik/landing/tanitim.js'teki
küçük bir vanilla JS dosyasıyla ulaşıldı -- CSP script-src 'self'
kısıtlaması yüzünden JS burada satır-içi OLAMAZ (main.py, root() üstü).
Önce ayrı bir Artifact önizlemesinde kullanıcıya gösterilip onay
alındıktan SONRA buraya taşındı.
"""
import html as _html_modul

# 2026-09-13 (kullanıcı fark etti -- redesign'daki JS düzeltmesi 24 saatlik
# /statik önbelleği (main.py _OnbellekliStatikDosyalar) yüzünden bazı
# ziyaretçilerde geç yansıyordu): tanitim.js'e her gerçek içerik
# değişikliğinde bu sürüm numarasını elle artır -- URL değiştiği için
# tarayıcı eski önbelleklenmiş kopyayı DEĞİL, her zaman güncel dosyayı ister.
_TANITIM_JS_SURUMU = 5

PLAY_STORE_URL = None  # Uygulama YAYINLANINCA (üretim onayı gelince) gerçek Play Store linki buraya girilecek.

# 2026-09-13: Google'a "Üretime başvur" gönderildi (inceleme genellikle
# ~7 gün sürüyor) -- ama henüz ONAYLANMADI, yani PLAY_STORE_URL hâlâ
# None olmalı (erken "şimdi Play Store'de" demek yanlış/erken olurdu).
# Bu bayrak SADECE metni "kapalı test" yerine "inceleme sürecinde" yapmak
# için -- Google onaylayıp PLAY_STORE_URL gerçek bir linkle doldurulunca
# bu bayrağın artık hiçbir etkisi kalmaz (üstteki if PLAY_STORE_URL dalı
# devreye girer). Onay geldiğinde: PLAY_STORE_URL'i gerçek linkle doldur.
_URETIME_BASVURULDU = True

_UYGULAMA_FIYATI = "₺750,00"  # Play Console'da (Türkiye) belirlenen gerçek fiyat.

# 2026-09-12: emoji ikonografi yerine tutarlı, tek-stil çizgi ikonlar
# (elle yazılmış, basit SVG -- harici bir ikon kütüphanesi/CDN'e gerek
# yok, CSP'ye de dokunmuyor). Anahtar, _OZELLIKLER listesindeki ilk
# eleman ile eşleşir.
_OZELLIK_IKONLARI = {
    "sorgulama": '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
    "bildirim": '<path d="M6 8a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6"/><path d="M10 20a2 2 0 0 0 4 0"/>',
    "favori": '<path d="M6 4h9l3 3v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1Z"/><path d="M9 15h6M9 11h6"/>',
    "sira": '<path d="M4 19V9M10 19V5M16 19v-7M22 19H2"/>',
    "belge": '<path d="M14 3v5h5"/><path d="M6 3h8l5 5v12a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z"/>',
    "dil": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
    "gizlilik": '<path d="M12 3 4 6.5v5c0 5 3.4 8.4 8 9.5 4.6-1.1 8-4.5 8-9.5v-5L12 3Z"/><path d="m9 12 2 2 4-4"/>',
    "tek-odeme": '<path d="M5 8h14l-1 11a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1L5 8Z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/>',
}

_OZELLIKLER = [
    ("sorgulama", "Anında Sorgulama", "Dosya numaranızı girin, Stadiu Dosar ve Ordine kategorilerinde saniyeler içinde güncel durumunuzu görün."),
    ("bildirim", "Otomatik Bildirim", "Favorilere eklemeseniz bile, sorguladığınız bir dosya numarası onaylandığında size otomatik bildirim gönderilir."),
    ("favori", "Favorilerim", "Takip etmek istediğiniz dosya numaralarını favorilere ekleyin, tek ekrandan hepsinin güncel durumunu görün."),
    ("sira", "Sıra Tahmini", "Aynı yılda ve maddede, dosyanızın tahmini kaçıncı sırada olduğunu ve size en yakın onaylanmış numaraları görün."),
    ("belge", "Resmi Belge Görüntüleme", "Sistemin sizin için bulduğu resmi PDF belgesini uygulamadan doğrudan açıp inceleyin."),
    ("dil", "3 Dil Desteği", "Türkçe, İngilizce ve Romence arasında anında geçiş yapın."),
    ("gizlilik", "Gizlilik Odaklı", "Ad, TC/CNP kimlik numarası, adres gibi hiçbir kişisel bilginiz istenmez ya da saklanmaz."),
    ("tek-odeme", "Tek Seferlik Satın Alma", "Aynı Google hesabıyla istediğiniz kadar cihaza ücretsiz olarak tekrar yükleyin -- telefon değiştirseniz bile tekrar ödeme yapmazsınız."),
]

# 2026-08-23 EKLENTİSİ (ASO/SEO): Bu sorular uydurma değil -- başvuru
# sahiplerinin Google'a gerçekten yazdığı terimler ("Stadiu Dosar nedir",
# "dosya numaram nerede" vb.). Amaç: bir kullanıcı kendi dosya numarasını
# ararken bu sayfayı organik olarak bulsun. Sayfanın geri kalanıyla aynı
# dürüst ton -- pazarlama abartısı değil, gerçek/kısa açıklamalar.
_SSS = [
    ("Stadiu Dosar nedir?",
     "Stadiu Dosar, Romanya Adalet Bakanlığı'nın (cetatenie.just.ro) yayınladığı, vatandaşlık başvurularının hangi aşamada olduğunu gösteren resmi listedir. Dosya numaranız bu listede geçiyorsa başvurunuz hâlâ inceleme sürecindedir."),
    ("Ordine listesi nedir, Stadiu Dosar'dan farkı ne?",
     "Ordine, başvurusu ONAYLANMIŞ dosyaların yayınlandığı resmi listedir (kanun maddesine göre ayrı ayrı, ör. \"Articolul 11\", \"Ordine minori\"). Yani Stadiu Dosar sürecin içinde olduğunuzu, Ordine ise vatandaşlığınızın onaylandığını gösterir."),
    ("Dosya numaramı nerede bulabilirim?",
     "Dosya numaranız, başvurunuzu yaptığınızda size verilen resmi belgede (başvuru makbuzu/dilekçe) yazılıdır. Numarayı ve başvuru yılınızı bildiğiniz sürece Romanya Dosya Takip'te sorgulayabilirsiniz."),
    ("Sıra tahmini nasıl hesaplanıyor?",
     "Aynı yıl ve maddede sizden önce onaylanmış en yakın dosya numaralarına bakılarak yaklaşık bir sıra tahmini gösterilir -- bu resmi bir taahhüt değildir, sadece mevcut onay hızına göre bir fikir vermek içindir."),
    # 2026-09-12 EKLENTİSİ (redesign sırasında tespit edilen eksik --
    # kullanıcının onayladığı zayıf nokta listesi): sorgu/dosya limiti
    # hiç belirtilmiyordu. Gerçek durum dürüstçe yazıldı -- teknik bir
    # kötüye-kullanım hız sınırı var (bkz. main.py slowapi) ama bu bir
    # ürün/paket limiti DEĞİL, normal kullanımda hiç hissedilmiyor.
    ("Sorgulama yaparken bir sınır var mı?",
     "Hayır, dilediğiniz kadar dosya numarası sorgulayabilirsiniz. Sistemi kötüye kullanıma karşı korumak için görünmez, teknik bir hız sınırı vardır -- normal kullanımda hiç fark etmezsiniz."),
]

_EKRAN_GORUNTULERI = [
    ("ekran-ana.png", "Sorgulama ekranı"),
    ("ekran-onay.png", "Onaylanmış başvuru sonucu"),
    ("ekran-sira.png", "Sıra tahmini"),
    ("ekran-istatistik.png", "Genel istatistikler"),
    ("ekran-grafik.png", "Yıllara göre dağılım"),
]

_CHECK_SVG = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>'
_PLUS_SVG = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>'


def _sayi_bicimle(deger):
    return f"{deger:,}".replace(",", ".")


def tanitim_sayfasi_html(toplam_stadiu=None, toplam_onay=None, toplam_bekleyen=None, toplam_ziyaretci=None):
    """
    toplam_* verilirse (main.py /api/istatistikler/genel'in önbelleğinden),
    sayfada gerçek/güncel rakamlar gösterilir -- verilmezse (önbellek henüz
    hesaplanmadıysa) o bölüm sessizce atlanır, sayfa yine de tam çalışır.
    toplam_ziyaretci main.py root()'un çerez tabanlı sayacından gelir --
    None ise (ör. DB'ye erişilemedi) şerit gösterilmez.
    """
    ozellik_html = "".join(
        f'<div class="feat"><div class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{_OZELLIK_IKONLARI[anahtar]}</svg></div>'
        f'<h3>{baslik}</h3><p>{aciklama}</p></div>'
        for anahtar, baslik, aciklama in _OZELLIKLER
    )

    sss_html = "".join(
        f'<div class="faq-item" data-open="{"true" if i == 0 else "false"}">'
        f'<button class="faq-q" type="button"><span>{soru}</span>{_PLUS_SVG}</button>'
        f'<div class="faq-a"><p>{cevap}</p></div></div>'
        for i, (soru, cevap) in enumerate(_SSS)
    )

    phone_frames_html = "".join(
        f'<div class="phone-frame"><img src="/statik/landing/{dosya}" alt="{aciklama}" loading="lazy"></div>'
        for dosya, aciklama in _EKRAN_GORUNTULERI
    )
    phone_captions_js = ",".join(f'"{aciklama}"' for _, aciklama in _EKRAN_GORUNTULERI)

    if PLAY_STORE_URL:
        eyebrow_html = '<span class="dot"></span>Play Store\'da yayında'
        magaza_html = (
            f'<a class="btn-primary" href="{PLAY_STORE_URL}">'
            f'<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="m5 3 14 9-14 9V3Z"/></svg>'
            f' Play Store\'dan İndir</a>'
        )
    elif _URETIME_BASVURULDU:
        eyebrow_html = '<span class="dot"></span>İnceleme sürecinde — çok yakında Play Store\'de'
        magaza_html = (
            '<span class="btn-primary btn-disabled" aria-disabled="true">'
            '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/></svg>'
            ' Çok Yakında Play Store\'de</span>'
        )
    else:
        eyebrow_html = '<span class="dot"></span>Kapalı test aşamasında — yakında herkese açık'
        magaza_html = (
            '<span class="btn-primary btn-disabled" aria-disabled="true">'
            '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/></svg>'
            ' Yakında Play Store\'da</span>'
        )

    fiyat_gosterim_html = (
        f'<div class="price-amount">{_html_modul.escape(_UYGULAMA_FIYATI)}</div>'
        if _UYGULAMA_FIYATI
        else '<div class="price-amount"><span class="ph">₺ — ,—</span></div>'
        '<div class="price-note">Fiyat Play Store\'da yayınlandığında burada görünecek</div>'
    )

    istatistik_html = ""
    if toplam_stadiu is not None and toplam_onay is not None and toplam_bekleyen is not None:
        istatistik_html = f"""
  <div class="stats reveal">
    <div class="stat"><b data-count="{toplam_stadiu}">0</b><span>Toplam kabul edilen başvuru</span></div>
    <div class="stat"><b data-count="{toplam_onay}">0</b><span>Onaylanan</span></div>
    <div class="stat"><b data-count="{toplam_bekleyen}">0</b><span>Hâlâ bekleyen</span></div>
  </div>"""

    ziyaretci_html = ""
    if toplam_ziyaretci is not None:
        ziyaretci_html = f"""
  <div class="visitor-strip reveal">
    <span class="v-dot"></span>
    <span>Bu sayfa şimdiye kadar <b data-count="{toplam_ziyaretci}">0</b> kişi tarafından ziyaret edildi</span>
  </div>"""

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Romanya Dosya Takip</title>
<meta name="description" content="Romanya vatandaşlık başvurunuzun Stadiu Dosar ve Ordine durumunu anında sorgulayın, onaylandığında otomatik bildirim alın.">
<!-- 2026-08-23: Google Search Console site sahipliği doğrulaması --
     kaldırmayın, doğrulanmış durumu bu etikete bağlı. -->
<meta name="google-site-verification" content="9ZHuCTWpd557SMeinm3TsH9kGUjD8y4T7uMBArv9iOk" />
<link rel="canonical" href="https://romanya-dosya-takip.onrender.com/">
<meta property="og:type" content="website">
<meta property="og:url" content="https://romanya-dosya-takip.onrender.com/">
<meta property="og:site_name" content="Romanya Dosya Takip">
<meta property="og:locale" content="tr_TR">
<meta property="og:title" content="Romanya Dosya Takip">
<meta property="og:description" content="Romanya vatandaşlık başvurunuzun Stadiu Dosar ve Ordine durumunu anında sorgulayın, onaylandığında otomatik bildirim alın.">
<meta property="og:image" content="https://romanya-dosya-takip.onrender.com/statik/landing/tanitim-video-poster.jpg">
<meta property="og:image:width" content="1920">
<meta property="og:image:height" content="1080">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Romanya Dosya Takip">
<meta name="twitter:description" content="Romanya vatandaşlık başvurunuzun Stadiu Dosar ve Ordine durumunu anında sorgulayın, onaylandığında otomatik bildirim alın.">
<meta name="twitter:image" content="https://romanya-dosya-takip.onrender.com/statik/landing/tanitim-video-poster.jpg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=Public+Sans:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
:root{{
  --ink-950:#0a1220; --ink-900:#0f1a2e; --ink-800:#1E2C4A; --ink-700:#27375A; --ink-600:#31416B;
  --line:#324268; --line-soft:#26355a;
  --gold-500:#E3A83B; --gold-400:#EFC46C; --gold-200:#F7DFA8;
  --mist:#94A1C2; --mist-dim:#6C7896; --paper:#F5F7FA; --good:#5FB894;
  --font-display:'Fraunces', ui-serif, Georgia, serif;
  --font-body:'Public Sans', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif;
  --font-mono:'IBM Plex Mono', ui-monospace, 'SFMono-Regular', Menlo, monospace;
}}
*{{box-sizing:border-box;}}
html{{scroll-behavior:smooth;}}
body{{
  margin:0; background:var(--ink-900); color:var(--paper);
  font-family:var(--font-body); line-height:1.6; -webkit-font-smoothing:antialiased;
  padding-inline:20px;
}}
img{{max-width:100%;}}
a{{color:var(--gold-400); text-decoration:none;}}
a:hover{{color:var(--gold-200);}}
:focus-visible{{outline:2px solid var(--gold-400); outline-offset:3px; border-radius:4px;}}
@media (prefers-reduced-motion: reduce){{
  *{{animation-duration:0.001ms!important; animation-iteration-count:1!important; transition-duration:0.001ms!important; scroll-behavior:auto!important;}}
}}
.wrap{{max-width:1120px; margin:0 auto;}}
.topbar{{display:flex; align-items:center; justify-content:space-between; gap:16px; padding-block:20px; max-width:1120px; margin:0 auto;}}
.brand{{display:flex; align-items:center; gap:10px; font-family:var(--font-display); font-weight:600; font-size:17px;}}
.brand-seal{{
  width:30px; height:30px; border-radius:50%; border:1.5px solid var(--gold-500);
  display:flex; align-items:center; justify-content:center; flex-shrink:0;
  background:radial-gradient(circle at 35% 30%, var(--ink-700), var(--ink-800));
}}
.brand-seal svg{{width:15px; height:15px; stroke:var(--gold-400);}}
.hero{{display:grid; grid-template-columns:1.05fr 0.95fr; gap:56px; align-items:center; padding-block:28px 44px; max-width:1120px; margin:0 auto;}}
@media (max-width:860px){{ .hero{{grid-template-columns:1fr; padding-block:8px 32px; text-align:center;}} }}
.eyebrow{{
  display:inline-flex; align-items:center; gap:8px; font-family:var(--font-mono); font-size:12px; letter-spacing:0.5px; color:var(--gold-400);
  border:1px solid rgba(227,168,59,0.35); background:rgba(227,168,59,0.08); padding:7px 14px 7px 10px; border-radius:99px; margin-bottom:22px;
}}
.eyebrow .dot{{width:6px; height:6px; border-radius:50%; background:var(--good); box-shadow:0 0 0 3px rgba(95,184,148,0.2);}}
h1{{font-family:var(--font-display); font-weight:600; font-size:clamp(30px,4.6vw,50px); line-height:1.1; margin:0 0 20px; text-wrap:balance; letter-spacing:-0.5px;}}
h1 em{{font-style:normal; color:var(--gold-400);}}
.sub{{font-size:16.5px; color:var(--mist); max-width:480px; margin:0 0 30px;}}
@media (max-width:860px){{ .sub{{margin-inline:auto;}} }}
.cta-row{{display:flex; gap:14px; flex-wrap:wrap; margin-bottom:26px;}}
@media (max-width:860px){{ .cta-row{{justify-content:center;}} }}
.btn-primary{{
  display:inline-flex; align-items:center; gap:9px; background:var(--gold-500); color:var(--ink-950); font-weight:700; font-size:14.5px;
  padding:14px 26px; border-radius:12px; border:none; cursor:pointer;
  box-shadow:0 10px 24px -8px rgba(227,168,59,0.5); transition:transform .15s ease, box-shadow .15s ease, background .15s ease;
}}
.btn-primary:hover{{background:var(--gold-400); transform:translateY(-1px); color:var(--ink-950);}}
.btn-disabled{{opacity:0.85; cursor:default;}}
.btn-disabled:hover{{background:var(--gold-500); transform:none;}}
.btn-ghost{{
  display:inline-flex; align-items:center; gap:9px; background:transparent; color:var(--paper); font-weight:600; font-size:14.5px;
  padding:14px 22px; border-radius:12px; border:1px solid var(--line); transition:border-color .15s ease, background .15s ease;
}}
.btn-ghost:hover{{border-color:var(--gold-500); background:rgba(227,168,59,0.06); color:var(--paper);}}
.trustline{{display:flex; align-items:center; gap:8px; color:var(--mist-dim); font-size:12.5px;}}
@media (max-width:860px){{ .trustline{{justify-content:center;}} }}
.trustline svg{{flex-shrink:0; stroke:var(--mist-dim);}}
.hero-visual{{position:relative;}}
.query-card{{
  background:linear-gradient(165deg, var(--ink-700), var(--ink-800)); border:1px solid var(--line); border-radius:22px; padding:26px;
  box-shadow:0 30px 60px -20px rgba(0,0,0,0.55); max-width:400px; margin:0 auto;
}}
.query-card-head{{display:flex; align-items:center; justify-content:space-between; margin-bottom:18px;}}
.query-card-head .app{{display:flex; align-items:center; gap:8px; font-size:12.5px; color:var(--mist); font-family:var(--font-mono);}}
.query-card-head .dots{{display:flex; gap:5px;}}
.query-card-head .dots span{{width:7px; height:7px; border-radius:50%; background:var(--line);}}
.field-label{{font-size:11px; letter-spacing:0.6px; text-transform:uppercase; color:var(--mist-dim); font-family:var(--font-mono); margin-bottom:7px;}}
.field{{
  background:var(--ink-900); border:1px solid var(--line); border-radius:11px; padding:13px 15px; font-family:var(--font-mono); font-size:15px; color:var(--paper);
  margin-bottom:14px; display:flex; align-items:center; justify-content:space-between;
}}
.field small{{color:var(--mist-dim); font-size:12px;}}
.query-btn{{width:100%; background:var(--gold-500); color:var(--ink-950); font-weight:700; font-size:14.5px; border:none; border-radius:11px; padding:13px; margin-top:4px;}}
.result-pop{{
  position:absolute; right:-14px; bottom:-22px; width:230px; background:var(--ink-800); border:1px solid rgba(95,184,148,0.4); border-radius:16px;
  padding:16px 18px; box-shadow:0 20px 40px -14px rgba(0,0,0,0.6);
}}
@media (max-width:860px){{ .result-pop{{position:static; margin:18px auto 0; width:100%; max-width:400px;}} }}
.result-pop .tag{{
  display:inline-flex; align-items:center; gap:6px; background:rgba(95,184,148,0.15); color:var(--good); font-size:11px; font-weight:700;
  padding:4px 10px; border-radius:99px; margin-bottom:10px;
}}
.result-pop b{{display:block; font-family:var(--font-mono); font-size:14px; margin-bottom:3px;}}
.result-pop span{{color:var(--mist); font-size:12px;}}
.demo{{background:var(--ink-800); border:1px solid var(--line-soft); border-radius:24px; padding:36px; display:grid; grid-template-columns:1fr 1fr; gap:36px; align-items:center; margin-bottom:40px;}}
@media (max-width:820px){{ .demo{{grid-template-columns:1fr; padding:24px; text-align:center;}} }}
.demo video{{width:100%; border-radius:16px; border:1px solid var(--line); display:block; box-shadow:0 20px 40px -16px rgba(0,0,0,0.5);}}
.demo video::cue{{font-size:3.2vw; line-height:1.35;}}
@media (min-width:500px){{ .demo video::cue{{font-size:14px;}} }}
.demo h2{{font-family:var(--font-display); font-weight:600; font-size:24px; margin:0 0 12px;}}
.demo p{{color:var(--mist); margin:0 0 18px; font-size:14px;}}
.demo ul{{list-style:none; padding:0; margin:0; display:grid; gap:10px;}}
.demo li{{display:flex; gap:10px; align-items:flex-start; font-size:13px; color:var(--paper); justify-content:flex-start;}}
@media (max-width:820px){{ .demo li{{justify-content:center;}} }}
.demo li svg{{flex-shrink:0; margin-top:2px; stroke:var(--good);}}
.visitor-strip{{
  display:flex; align-items:center; justify-content:center; gap:9px; max-width:fit-content; margin:0 auto 40px; padding:9px 18px;
  border:1px solid var(--line-soft); border-radius:99px; background:var(--ink-800); font-family:var(--font-mono); font-size:12.5px; color:var(--mist);
}}
.visitor-strip .v-dot{{width:6px; height:6px; border-radius:50%; background:var(--good); box-shadow:0 0 0 3px rgba(95,184,148,0.2); flex-shrink:0;}}
.visitor-strip b{{color:var(--paper); font-weight:600; font-variant-numeric:tabular-nums;}}
@media (max-width:520px){{ .visitor-strip{{font-size:11.5px; text-align:center; white-space:normal; padding:9px 16px;}} }}
.stats{{display:grid; grid-template-columns:repeat(3,1fr); gap:1px; background:var(--line-soft); border:1px solid var(--line-soft); border-radius:18px; overflow:hidden; margin-bottom:80px;}}
.stat{{background:var(--ink-800); padding:28px 22px; text-align:center;}}
.stat b{{display:block; font-family:var(--font-mono); font-weight:600; font-size:clamp(24px,3.2vw,34px); color:var(--gold-400); font-variant-numeric:tabular-nums; letter-spacing:-0.5px;}}
.stat span{{color:var(--mist); font-size:12.5px;}}
@media (max-width:640px){{ .stats{{grid-template-columns:1fr;}} .stat{{padding:20px;}} }}
section{{margin-bottom:88px;}}
.section-head{{max-width:560px; margin:0 auto 40px; text-align:center;}}
.section-head .kicker{{font-family:var(--font-mono); font-size:12px; letter-spacing:1px; text-transform:uppercase; color:var(--gold-400); margin-bottom:10px; display:block;}}
.section-head h2{{font-family:var(--font-display); font-weight:600; font-size:clamp(22px,3vw,30px); margin:0 0 10px; text-wrap:balance;}}
.section-head p{{color:var(--mist); margin:0; font-size:14.5px;}}
.reveal{{opacity:0; transform:translateY(22px); transition:opacity .6s ease, transform .6s ease;}}
.reveal.in{{opacity:1; transform:translateY(0);}}
.showcase{{display:grid; grid-template-columns:auto 1fr; gap:60px; align-items:center;}}
@media (max-width:900px){{ .showcase{{grid-template-columns:1fr; gap:36px; justify-items:center; text-align:center;}} }}
.phone-rail{{position:relative; width:240px;}}
.phone-scroll{{display:flex; gap:16px; overflow-x:auto; scroll-snap-type:x mandatory; padding:6px; margin:0 -6px; scrollbar-width:none;}}
.phone-scroll::-webkit-scrollbar{{display:none;}}
.phone-frame{{
  flex:0 0 228px; scroll-snap-align:center; position:relative; border-radius:26px; border:2px solid var(--line); background:var(--ink-950);
  padding:8px; box-shadow:0 26px 50px -18px rgba(0,0,0,0.6);
}}
.phone-frame::before{{content:''; position:absolute; top:16px; left:50%; transform:translateX(-50%); width:44px; height:4px; border-radius:3px; background:var(--line); z-index:2;}}
.phone-frame img{{display:block; width:100%; border-radius:18px;}}
.phone-caption{{text-align:center; margin-top:16px; font-size:13px; color:var(--mist); font-family:var(--font-mono);}}
.phone-dots{{display:flex; justify-content:center; gap:6px; margin-top:12px;}}
.phone-dots span{{width:6px; height:6px; border-radius:50%; background:var(--line); transition:background .2s, width .2s;}}
.phone-dots span.on{{background:var(--gold-500); width:18px; border-radius:4px;}}
.feat-grid{{display:grid; grid-template-columns:repeat(2,1fr); gap:14px;}}
@media (max-width:520px){{ .feat-grid{{grid-template-columns:1fr;}} }}
.feat{{background:var(--ink-800); border:1px solid var(--line-soft); border-radius:14px; padding:20px; text-align:left; transition:border-color .2s ease, transform .2s ease;}}
.feat:hover{{border-color:var(--gold-500); transform:translateY(-2px);}}
.feat .ic{{width:36px; height:36px; border-radius:9px; background:var(--ink-700); display:flex; align-items:center; justify-content:center; margin-bottom:12px;}}
.feat .ic svg{{width:18px; height:18px; stroke:var(--gold-400);}}
.feat h3{{margin:0 0 5px; font-size:14.5px; font-weight:700;}}
.feat p{{margin:0; color:var(--mist); font-size:12.8px; line-height:1.55;}}
.price-card{{
  max-width:420px; margin:0 auto; background:linear-gradient(165deg, var(--ink-700), var(--ink-800)); border:1px solid var(--gold-500); border-radius:22px;
  padding:36px; text-align:center; box-shadow:0 24px 50px -20px rgba(227,168,59,0.18);
}}
.price-card .badge{{
  font-family:var(--font-mono); font-size:11px; letter-spacing:0.5px; text-transform:uppercase; color:var(--gold-400); background:rgba(227,168,59,0.1);
  border:1px solid rgba(227,168,59,0.3); display:inline-block; padding:5px 12px; border-radius:99px; margin-bottom:18px;
}}
.price-amount{{font-family:var(--font-display); font-weight:600; font-size:48px; margin:0 0 4px; letter-spacing:-1px;}}
.price-amount .ph{{color:var(--mist-dim); border-bottom:2px dashed var(--mist-dim);}}
.price-note{{color:var(--mist); font-size:12.5px; margin-bottom:24px;}}
.price-list{{list-style:none; padding:0; margin:0 0 28px; display:grid; gap:12px; text-align:left;}}
.price-list li{{display:flex; gap:10px; align-items:flex-start; font-size:13.5px;}}
.price-list li svg{{flex-shrink:0; margin-top:2px; stroke:var(--gold-400);}}
.price-card .btn-primary, .price-card .btn-disabled{{width:100%; justify-content:center;}}
.spec-row{{display:flex; justify-content:center; gap:20px; margin-top:22px; padding-top:22px; border-top:1px solid var(--line-soft); flex-wrap:wrap;}}
.spec{{text-align:left; font-size:11.5px; color:var(--mist-dim);}}
.spec b{{display:block; color:var(--paper); font-family:var(--font-mono); font-size:13px; font-weight:600;}}
.faq-list{{max-width:760px; margin:0 auto; display:grid; gap:1px; background:var(--line-soft); border:1px solid var(--line-soft); border-radius:16px; overflow:hidden;}}
.faq-item{{background:var(--ink-800);}}
.faq-q{{
  width:100%; display:flex; align-items:center; justify-content:space-between; gap:16px; background:none; border:none; color:var(--paper); text-align:left;
  cursor:pointer; padding:19px 22px; font-family:var(--font-body); font-size:14.5px; font-weight:600;
}}
.faq-q svg{{flex-shrink:0; stroke:var(--gold-400); transition:transform .25s ease;}}
.faq-item[data-open="true"] .faq-q svg{{transform:rotate(45deg);}}
.faq-a{{max-height:0; overflow:hidden; transition:max-height .3s ease;}}
.faq-item[data-open="true"] .faq-a{{max-height:220px;}}
.faq-a p{{margin:0; padding:0 22px 20px; color:var(--mist); font-size:13.5px; line-height:1.65;}}
.support{{display:grid; grid-template-columns:repeat(3,1fr); gap:16px;}}
@media (max-width:760px){{ .support{{grid-template-columns:1fr;}} }}
.support-card{{background:var(--ink-800); border:1px solid var(--line-soft); border-radius:16px; padding:24px;}}
.support-card .ic{{width:38px; height:38px; border-radius:10px; background:var(--ink-700); display:flex; align-items:center; justify-content:center; margin-bottom:14px;}}
.support-card .ic svg{{width:19px; height:19px; stroke:var(--gold-400);}}
.support-card h3{{margin:0 0 6px; font-size:14.5px;}}
.support-card p{{margin:0 0 12px; color:var(--mist); font-size:13px;}}
.support-card a{{font-size:13px; font-weight:700; display:inline-flex; align-items:center; gap:5px;}}
.disclaimer{{
  display:flex; gap:12px; background:rgba(227,168,59,0.06); border:1px solid rgba(227,168,59,0.25); border-radius:14px; padding:16px 20px;
  font-size:12.5px; color:var(--mist); max-width:900px; margin:0 auto 56px;
}}
.disclaimer svg{{flex-shrink:0; stroke:var(--gold-400); margin-top:1px;}}
footer{{border-top:1px solid var(--line-soft); padding:28px 0 46px; text-align:center;}}
.foot-links{{margin-bottom:10px;}}
.foot-links a{{color:var(--mist); margin:0 10px; font-size:13px;}}
.foot-links a:hover{{color:var(--gold-400);}}
.foot-sig{{color:var(--mist-dim); font-size:12px;}}
</style>
</head>
<body>

<div class="topbar">
  <div class="brand">
    <span class="brand-seal">
      <svg viewBox="0 0 24 24" fill="none" stroke-width="1.6"><path d="M12 3 4 6.5v5c0 5 3.4 8.4 8 9.5 4.6-1.1 8-4.5 8-9.5v-5L12 3Z"/><path d="m9 12 2 2 4-4" stroke-linecap="round" stroke-linejoin="round"/></svg>
    </span>
    Romanya Dosya Takip
  </div>
</div>

<div class="hero">
  <div>
    <div class="eyebrow">{eyebrow_html}</div>
    <h1>Dosyanızın durumunu <em>tahmin etmeyin</em>, anında öğrenin.</h1>
    <p class="sub">Romanya vatandaşlığı başvurunuzun Stadiu Dosar ve Ordine durumunu saniyeler içinde sorgulayın. Onaylandığında, siz sormadan, otomatik bildirim alırsınız.</p>
    <div class="cta-row">
      {magaza_html}
      <a class="btn-ghost" href="#nasil-calisir">
        Nasıl çalışır
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
      </a>
    </div>
    <div class="trustline">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke-width="1.8"><path d="M12 3 4 6.5v5c0 5 3.4 8.4 8 9.5 4.6-1.1 8-4.5 8-9.5v-5L12 3Z"/></svg>
      cetatenie.just.ro'nun resmi listelerini temel alır — kişisel veri istemez
    </div>
  </div>

  <div class="hero-visual">
    <div class="query-card">
      <div class="query-card-head">
        <span class="app">◆ Stadiu Dosar</span>
        <span class="dots"><span></span><span></span><span></span></span>
      </div>
      <div class="field-label">Dosya Numarası</div>
      <div class="field">102/RD <small>ARTICOLUL 11</small></div>
      <div class="field-label">Yıl</div>
      <div class="field">2026 <small>Stadiu → Ordine</small></div>
      <button class="query-btn" type="button" tabindex="-1">Sorgula</button>
    </div>
    <div class="result-pop">
      <span class="tag">{_CHECK_SVG} ONAYLANDI</span>
      <b>102/RD/2026</b>
      <span>Ordine articolul 11 · bugün eklendi</span>
    </div>
  </div>
</div>

<div class="wrap">

  <section class="demo reveal">
    <video controls preload="metadata" poster="/statik/landing/tanitim-video-poster.jpg" playsinline>
      <source src="/statik/landing/tanitim-video.mp4" type="video/mp4">
      <track kind="subtitles" srclang="en" label="English" src="/statik/landing/tanitim-video-en.vtt" default>
    </video>
    <div>
      <h2>60 saniyede görün</h2>
      <p>Uygulamayı kurmadan önce gerçek arayüzünde bir sorgulamanın baştan sona nasıl işlediğini izleyin.</p>
      <ul>
        <li>{_CHECK_SVG} Gerçek dosya numarasıyla canlı sorgulama</li>
        <li>{_CHECK_SVG} Onay bildirimi ekranı</li>
        <li>{_CHECK_SVG} Türkçe ve İngilizce altyazı</li>
      </ul>
    </div>
  </section>
{ziyaretci_html}
{istatistik_html}

  <section id="nasil-calisir" class="showcase reveal">
    <div class="phone-rail">
      <div class="phone-scroll" id="phoneScroll">
        {phone_frames_html}
      </div>
      <div class="phone-caption" id="phoneCaption">{_EKRAN_GORUNTULERI[0][1]}</div>
      <div class="phone-dots" id="phoneDots"></div>
    </div>
    <div>
      <div class="feat-grid">
        {ozellik_html}
      </div>
    </div>
  </section>

  <section class="reveal">
    <div class="section-head">
      <span class="kicker">Fiyatlandırma</span>
      <h2>Tek seferlik, sürpriz yok</h2>
      <p>Abonelik değil — bir kez ödersiniz, hesabınıza bağlı her cihazda ücretsiz kullanırsınız.</p>
    </div>
    <div class="price-card">
      <span class="badge">Yaşam Boyu Erişim</span>
      {fiyat_gosterim_html}
      <ul class="price-list">
        <li>{_CHECK_SVG} Sınırsız sorgulama</li>
        <li>{_CHECK_SVG} Otomatik onay bildirimi</li>
        <li>{_CHECK_SVG} Telefon değişince tekrar ödeme yok</li>
      </ul>
      {magaza_html}
      <div class="spec-row">
        <div class="spec"><b>Android 7.0+</b>API seviyesi 24</div>
        <div class="spec"><b>TR · EN · RO</b>dil desteği</div>
      </div>
    </div>
  </section>

  <section class="reveal">
    <div class="section-head">
      <span class="kicker">SSS</span>
      <h2>Sıkça Sorulan Sorular</h2>
      <p>Stadiu Dosar, Ordine ve dosya sorgulama hakkında</p>
    </div>
    <div class="faq-list" id="faqList">
      {sss_html}
    </div>
  </section>

  <section class="reveal">
    <div class="section-head">
      <span class="kicker">Destek</span>
      <h2>Yardıma mı ihtiyacınız var?</h2>
      <p>Sorularınız için birden fazla yoldan ulaşabilirsiniz</p>
    </div>
    <div class="support">
      <div class="support-card">
        <div class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg></div>
        <h3>E-posta</h3>
        <p>Genellikle 1-2 iş günü içinde yanıt veriyoruz.</p>
        <a href="mailto:ahmet.knby.25@gmail.com">ahmet.knby.25@gmail.com →</a>
      </div>
      <div class="support-card">
        <div class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16v12H7l-3 3V4Z"/></svg></div>
        <h3>Sık Sorulanlar</h3>
        <p>En yaygın sorular için önce buraya göz atın.</p>
        <a href="#faqList">SSS'ye git →</a>
      </div>
      <div class="support-card">
        <div class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3 4 6.5v5c0 5 3.4 8.4 8 9.5 4.6-1.1 8-4.5 8-9.5v-5L12 3Z"/></svg></div>
        <h3>Resmi Kaynak</h3>
        <p>Tüm veriler cetatenie.just.ro'dan alınır.</p>
        <a href="https://cetatenie.just.ro" target="_blank" rel="noopener">cetatenie.just.ro →</a>
      </div>
    </div>
  </section>

  <div class="disclaimer">
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16h.01"/></svg>
    <span>Bu uygulama resmi bir devlet uygulaması değildir — başvuru sürecini yürütmez, yalnızca cetatenie.just.ro sitesinde yayınlanan resmi PDF listelerini takip etmenizi kolaylaştırır.</span>
  </div>

</div>

<footer>
  <div class="foot-links">
    <a href="/gizlilik-politikasi">Gizlilik Politikası</a>·
    <a href="/kullanim-sartlari">Kullanım Şartları</a>·
    <a href="mailto:ahmet.knby.25@gmail.com">İletişim</a>
  </div>
  <div class="foot-sig">🔒 Secured &amp; Encrypted System · By @knby · © 2026</div>
</footer>

<script src="/statik/landing/tanitim.js?v={_TANITIM_JS_SURUMU}" defer data-captions='[{phone_captions_js}]'></script>
</body>
</html>"""
