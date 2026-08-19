# -*- coding: utf-8 -*-
"""
/admin istatistik paneli -- SADECE proje sahibinin kullanması için,
şifreyle korunan (bkz. main.py'deki HTTPBasic kontrolü), salt-okunur bir
"arka ofis" görünümü. Kapsam 2026-08-19'da netleştirildi:

  1) Kullanıcı sayıları  -- toplam/yeni cihaz, favori sayıları
  2) Sistem/bot sağlığı  -- son tarama, veri dağılımı, disk kullanımı,
                            son kritik uyarılar
  3) Bildirim etkinliği  -- gönderilen push bildirimleri, favori→onay
                            dönüşüm oranı

BİLİNÇLİ OLARAK YOK: tekil arama/sorgu geçmişi. Kullanıcı, hangi dosya
numarasının arandığını kaydetmenin (kişisel veri + Gizlilik Politikası
güncellemesi gerektireceği için) İSTEMEDİĞİNE karar verdi (2026-08-19).
"""
import html
import os
import time
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_KOK_KLASOR = os.path.join(BASE_DIR, "pdfs")

LACIVERT_KOYU = "#0f1a2e"
LACIVERT = "#16233d"
ALTIN = "#e3a83b"

# 2026-08-19: PDF klasörünün toplam boyutunu hesaplamak (os.walk ile
# binlerce dosyayı tek tek ölçmek) birkaç saniye sürebiliyor -- admin
# panelini her açışta bunu tekrar hesaplamamak için 10 dakikalık basit bir
# önbellek (main.py'deki _genel_istatistik_onbellek ile aynı desen).
_disk_boyutu_onbellek = {"veri": None, "zaman": 0.0}
_ONBELLEK_SURESI_SN = 600


def _boyutu_okunabilir_yap(byte_sayisi):
    for birim in ["B", "KB", "MB", "GB", "TB"]:
        if byte_sayisi < 1024:
            return f"{byte_sayisi:.1f} {birim}"
        byte_sayisi /= 1024
    return f"{byte_sayisi:.1f} PB"


def _klasor_boyutu(yol):
    toplam = 0
    for kok, _, dosyalar in os.walk(yol):
        for ad in dosyalar:
            try:
                toplam += os.path.getsize(os.path.join(kok, ad))
            except OSError:
                pass
    return toplam


def _disk_kullanimini_hesapla(db_dosyasi):
    onbellek = _disk_boyutu_onbellek
    if onbellek["veri"] is not None and (time.time() - onbellek["zaman"]) < _ONBELLEK_SURESI_SN:
        return onbellek["veri"]

    db_boyutu = os.path.getsize(db_dosyasi) if os.path.exists(db_dosyasi) else 0
    pdf_boyutu = _klasor_boyutu(PDF_KOK_KLASOR) if os.path.isdir(PDF_KOK_KLASOR) else 0

    sonuc = {
        "db_boyutu": _boyutu_okunabilir_yap(db_boyutu),
        "pdf_boyutu": _boyutu_okunabilir_yap(pdf_boyutu),
        "toplam_boyutu": _boyutu_okunabilir_yap(db_boyutu + pdf_boyutu),
    }
    onbellek["veri"] = sonuc
    onbellek["zaman"] = time.time()
    return sonuc


def metrikleri_hesapla(conn, db_dosyasi, son_basarili_tarama):
    """Tüm admin paneli metriklerini tek bir sözlükte toplar. `conn`,
    main.py'nin zaten kullandığı row_factory=sqlite3.Row bağlantısıdır."""
    c = conn.cursor()
    simdi = datetime.now()

    # --- 1) Kullanıcı sayıları -------------------------------------------
    c.execute("SELECT COUNT(*) FROM push_tokenlari")
    toplam_cihaz = c.fetchone()[0]

    yeni_cihaz = {}
    for etiket, gun in [("bugun", 1), ("hafta", 7), ("ay", 30)]:
        esik = (simdi - timedelta(days=gun)).isoformat()
        c.execute("SELECT COUNT(*) FROM push_tokenlari WHERE olusturma_tarihi >= ?", (esik,))
        yeni_cihaz[etiket] = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM favoriler WHERE otomatik_mi = 0")
    toplam_favori = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM favoriler WHERE otomatik_mi = 1")
    toplam_otomatik_takip = c.fetchone()[0]

    # --- 2) Sistem / bot sağlığı ------------------------------------------
    c.execute(
        "SELECT detay, zaman FROM sistem_olaylari WHERE olay_tipi='tarama_tamamlandi' "
        "ORDER BY zaman DESC LIMIT 1"
    )
    son_tarama_satiri = c.fetchone()
    son_tarama_detay = son_tarama_satiri[0] if son_tarama_satiri else None

    c.execute("SELECT COUNT(*) FROM dosyalar")
    toplam_kayit = c.fetchone()[0]

    c.execute("SELECT ana_kategori, COUNT(*) FROM dosyalar GROUP BY ana_kategori")
    kategori_dagilimi = dict(c.fetchall())

    c.execute("SELECT durum, COUNT(*) FROM dosyalar GROUP BY durum")
    durum_dagilimi = dict(c.fetchall())

    esik_7gun = (simdi - timedelta(days=7)).isoformat()
    c.execute(
        "SELECT COUNT(*) FROM sistem_olaylari WHERE olay_tipi='kritik_uyari' AND zaman >= ?",
        (esik_7gun,),
    )
    kritik_uyari_7gun = c.fetchone()[0]

    c.execute(
        "SELECT detay, zaman FROM sistem_olaylari WHERE olay_tipi='kritik_uyari' "
        "ORDER BY zaman DESC LIMIT 5"
    )
    son_kritik_uyarilar = c.fetchall()

    disk = _disk_kullanimini_hesapla(db_dosyasi)

    # --- 3) Bildirim etkinliği ---------------------------------------------
    c.execute(
        "SELECT COUNT(*) FROM sistem_olaylari WHERE olay_tipi='push_gonderildi' AND zaman >= ?",
        (esik_7gun,),
    )
    push_gonderim_7gun = c.fetchone()[0]

    c.execute(
        "SELECT detay, zaman FROM sistem_olaylari WHERE olay_tipi='push_gonderildi' "
        "ORDER BY zaman DESC LIMIT 5"
    )
    son_push_gonderimler = c.fetchall()

    # Favori -> onay dönüşüm oranı: kullanıcının elle favorilediği (dosya_no_norm,
    # yil) çiftlerinden kaçının 'ordine' tarafında durum='ONAYLANDI' olarak
    # göründüğü.
    c.execute("""
        SELECT
            COUNT(DISTINCT f.dosya_no_norm || '|' || f.yil) AS toplam,
            COUNT(DISTINCT CASE WHEN d.durum = 'ONAYLANDI'
                                 THEN f.dosya_no_norm || '|' || f.yil END) AS onaylanan
        FROM favoriler f
        LEFT JOIN dosyalar d
            ON d.dosya_no_norm = f.dosya_no_norm
           AND d.yil = f.yil
           AND d.ana_kategori = 'ordine'
        WHERE f.otomatik_mi = 0
    """)
    donusum_satiri = c.fetchone()
    favori_toplam, favori_onaylanan = donusum_satiri[0] or 0, donusum_satiri[1] or 0
    donusum_orani = (favori_onaylanan / favori_toplam * 100) if favori_toplam else 0.0

    return {
        "olusturma_zamani": simdi.strftime("%d.%m.%Y %H:%M"),
        "kullanicilar": {
            "toplam_cihaz": toplam_cihaz,
            "yeni_bugun": yeni_cihaz["bugun"],
            "yeni_hafta": yeni_cihaz["hafta"],
            "yeni_ay": yeni_cihaz["ay"],
            "toplam_favori": toplam_favori,
            "toplam_otomatik_takip": toplam_otomatik_takip,
        },
        "sistem": {
            "son_basarili_tarama": son_basarili_tarama,
            "son_tarama_detay": son_tarama_detay,
            "toplam_kayit": toplam_kayit,
            "kategori_dagilimi": kategori_dagilimi,
            "durum_dagilimi": durum_dagilimi,
            "kritik_uyari_7gun": kritik_uyari_7gun,
            "son_kritik_uyarilar": son_kritik_uyarilar,
            "disk": disk,
        },
        "bildirimler": {
            "push_gonderim_7gun": push_gonderim_7gun,
            "son_push_gonderimler": son_push_gonderimler,
            "favori_toplam": favori_toplam,
            "favori_onaylanan": favori_onaylanan,
            "donusum_orani": donusum_orani,
        },
    }


def _e(deger):
    """HTML'e basmadan önce güvenli şekilde kaçış yapar (bkz. hukuki_metinler.py
    sayfa_html'deki aynı gerekçe -- kullanıcı girdisi burada yok ama savunma
    katmanı olarak tutarlı tutuluyor)."""
    return html.escape(str(deger)) if deger is not None else "—"


def _olay_satirlari_html(olaylar, bos_mesaj):
    if not olaylar:
        return f'<p class="bos">{bos_mesaj}</p>'
    satirlar = []
    for detay, zaman in olaylar:
        try:
            zaman_okunabilir = datetime.fromisoformat(zaman).strftime("%d.%m.%Y %H:%M")
        except Exception:
            zaman_okunabilir = _e(zaman)
        satirlar.append(
            f'<li><span class="olay-zaman">{zaman_okunabilir}</span>'
            f'<span class="olay-detay">{_e(detay)}</span></li>'
        )
    return f'<ul class="olay-listesi">{"".join(satirlar)}</ul>'


def admin_sayfa_html(m):
    k = m["kullanicilar"]
    s = m["sistem"]
    b = m["bildirimler"]

    kategori_satirlari = "".join(
        f'<div class="dagilim-satir"><span>{_e(ad)}</span><b>{sayi}</b></div>'
        for ad, sayi in s["kategori_dagilimi"].items()
    ) or '<p class="bos">Henüz veri yok.</p>'

    durum_satirlari = "".join(
        f'<div class="dagilim-satir"><span>{_e(ad)}</span><b>{sayi}</b></div>'
        for ad, sayi in s["durum_dagilimi"].items()
    ) or '<p class="bos">Henüz veri yok.</p>'

    son_tarama_metin = "Hiç tarama kaydı yok."
    if s["son_basarili_tarama"]:
        try:
            zaman = datetime.fromisoformat(s["son_basarili_tarama"]).strftime("%d.%m.%Y %H:%M")
        except Exception:
            zaman = _e(s["son_basarili_tarama"])
        son_tarama_metin = f"{zaman}"
        if s["son_tarama_detay"]:
            son_tarama_metin += f" — {_e(s['son_tarama_detay'])}"

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Admin Paneli — Romanya Dosya Takip</title>
<style>
  :root {{
    --lacivert-koyu: {LACIVERT_KOYU}; --lacivert: {LACIVERT}; --altin: {ALTIN};
    --zemin: #f6f7fb; --yuzey: #ffffff; --kenar: #e4e7ee;
    --metin: #1c2433; --metin-ikincil: #6b7280;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 32px 20px 60px; background: var(--zemin); color: var(--metin);
    font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
  }}
  .sayfa {{ max-width: 860px; margin: 0 auto; }}
  header.ustbilgi {{
    display: flex; justify-content: space-between; align-items: baseline;
    margin-bottom: 22px; flex-wrap: wrap; gap: 8px;
  }}
  header.ustbilgi h1 {{ font-size: 20px; margin: 0; color: var(--lacivert-koyu); }}
  header.ustbilgi .zaman {{ font-size: 12.5px; color: var(--metin-ikincil); }}

  .bolum {{ margin-bottom: 26px; }}
  .bolum-baslik {{
    font-size: 12px; font-weight: 700; letter-spacing: .07em; text-transform: uppercase;
    color: var(--altin); margin: 0 0 10px;
  }}
  .kart-izgara {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }}
  .kart {{
    background: var(--yuzey); border: 1px solid var(--kenar); border-radius: 10px;
    padding: 14px 16px;
  }}
  .kart .rakam {{ font-size: 26px; font-weight: 700; color: var(--lacivert-koyu); line-height: 1.1; }}
  .kart .etiket {{ font-size: 12px; color: var(--metin-ikincil); margin-top: 3px; }}

  .genis-kart {{
    background: var(--yuzey); border: 1px solid var(--kenar); border-radius: 10px;
    padding: 16px 18px; margin-top: 12px;
  }}
  .genis-kart h3 {{ font-size: 13.5px; margin: 0 0 8px; color: var(--lacivert-koyu); }}

  .dagilim-satir {{
    display: flex; justify-content: space-between; padding: 5px 0;
    border-bottom: 1px solid var(--kenar); font-size: 13.5px;
  }}
  .dagilim-satir:last-child {{ border-bottom: none; }}
  .dagilim-satir b {{ color: var(--lacivert-koyu); }}

  .olay-listesi {{ list-style: none; margin: 0; padding: 0; }}
  .olay-listesi li {{
    display: flex; gap: 10px; padding: 6px 0; border-bottom: 1px solid var(--kenar);
    font-size: 12.8px; align-items: baseline;
  }}
  .olay-listesi li:last-child {{ border-bottom: none; }}
  .olay-zaman {{ color: var(--metin-ikincil); white-space: nowrap; font-variant-numeric: tabular-nums; }}
  .olay-detay {{ color: var(--metin); }}
  p.bos {{ color: var(--metin-ikincil); font-size: 13px; font-style: italic; margin: 4px 0; }}

  .donusum-cubuk-zemin {{ height: 8px; background: var(--kenar); border-radius: 5px; overflow: hidden; margin-top: 8px; }}
  .donusum-cubuk-dolu {{ height: 100%; background: linear-gradient(90deg, var(--altin), #f0c069); }}

  footer.altbilgi {{ text-align: center; font-size: 11.5px; color: var(--metin-ikincil); margin-top: 30px; }}
</style>
</head>
<body>
<div class="sayfa">
  <header class="ustbilgi">
    <h1>📊 Admin Paneli</h1>
    <span class="zaman">Oluşturulma: {m['olusturma_zamani']}</span>
  </header>

  <div class="bolum">
    <p class="bolum-baslik">Kullanıcılar</p>
    <div class="kart-izgara">
      <div class="kart"><div class="rakam">{k['toplam_cihaz']}</div><div class="etiket">Toplam cihaz</div></div>
      <div class="kart"><div class="rakam">{k['yeni_bugun']}</div><div class="etiket">Bugün yeni</div></div>
      <div class="kart"><div class="rakam">{k['yeni_hafta']}</div><div class="etiket">Bu hafta yeni</div></div>
      <div class="kart"><div class="rakam">{k['yeni_ay']}</div><div class="etiket">Bu ay yeni</div></div>
      <div class="kart"><div class="rakam">{k['toplam_favori']}</div><div class="etiket">Favori (elle eklenen)</div></div>
      <div class="kart"><div class="rakam">{k['toplam_otomatik_takip']}</div><div class="etiket">Otomatik izlenen</div></div>
    </div>
  </div>

  <div class="bolum">
    <p class="bolum-baslik">Sistem / Bot Sağlığı</p>
    <div class="kart-izgara">
      <div class="kart"><div class="rakam">{s['toplam_kayit']}</div><div class="etiket">Toplam kayıt</div></div>
      <div class="kart"><div class="rakam">{s['kritik_uyari_7gun']}</div><div class="etiket">Kritik uyarı (7 gün)</div></div>
      <div class="kart"><div class="rakam" style="font-size:17px">{s['disk']['db_boyutu']}</div><div class="etiket">Veritabanı boyutu</div></div>
      <div class="kart"><div class="rakam" style="font-size:17px">{s['disk']['pdf_boyutu']}</div><div class="etiket">PDF klasörü boyutu</div></div>
    </div>

    <div class="genis-kart">
      <h3>Son tarama</h3>
      <p style="margin:0;font-size:13.5px">{son_tarama_metin}</p>
    </div>

    <div class="genis-kart">
      <h3>Ana kategori dağılımı</h3>
      {kategori_satirlari}
    </div>

    <div class="genis-kart">
      <h3>Durum dağılımı</h3>
      {durum_satirlari}
    </div>

    <div class="genis-kart">
      <h3>Son kritik uyarılar</h3>
      {_olay_satirlari_html(s['son_kritik_uyarilar'], "Son dönemde kritik uyarı yok — iyi haber.")}
    </div>
  </div>

  <div class="bolum">
    <p class="bolum-baslik">Bildirimler</p>
    <div class="kart-izgara">
      <div class="kart"><div class="rakam">{b['push_gonderim_7gun']}</div><div class="etiket">Gönderim turu (7 gün)</div></div>
      <div class="kart"><div class="rakam">{b['favori_toplam']}</div><div class="etiket">Takipteki favori</div></div>
      <div class="kart"><div class="rakam">{b['favori_onaylanan']}</div><div class="etiket">Onaylanan</div></div>
    </div>

    <div class="genis-kart">
      <h3>Favori → Onay dönüşüm oranı</h3>
      <p style="margin:0 0 2px;font-size:13.5px">%{b['donusum_orani']:.1f}
        <span style="color:var(--metin-ikincil)">({b['favori_onaylanan']} / {b['favori_toplam']})</span></p>
      <div class="donusum-cubuk-zemin"><div class="donusum-cubuk-dolu" style="width:{min(b['donusum_orani'],100):.1f}%"></div></div>
    </div>

    <div class="genis-kart">
      <h3>Son bildirim gönderimleri</h3>
      {_olay_satirlari_html(b['son_push_gonderimler'], "Henüz push bildirimi gönderilmedi.")}
    </div>
  </div>

  <footer class="altbilgi">Romanya Dosya Takip — sadece proje sahibi için, salt-okunur görünüm.</footer>
</div>
</body>
</html>"""
