# -*- coding: utf-8 -*-
"""
Uygulamanın herkese açık tanıtım (landing) sayfası -- backend'in kök
adresinde ("/") sunulur. Önceden bu adres sadece boş bir sağlık kontrolü
JSON'u ("status: ok") döndürüyordu, hiçbir işe yaramıyordu (2026-08-20,
kullanıcı isteği: Instagram'da paylaşılabilecek, Play Console'un "web
sitesi" alanına girilebilecek gerçek bir sayfa).

Mobil uygulamanın kullandığı sağlık kontrolü ayrı bir adreste
(/api/durum), bu sayfaya HİÇ dokunmuyor -- ikisi birbirinden bağımsız.
"""

PLAY_STORE_URL = None  # Uygulama yayınlanınca gerçek Play Store linki buraya girilecek.

_OZELLIKLER = [
    ("🔍", "Anında Sorgulama", "Dosya numaranızı girin, Stadiu Dosar ve Ordine kategorilerinde saniyeler içinde güncel durumunuzu görün."),
    ("🔔", "Otomatik Bildirim", "Favorilere eklemeseniz bile, sorguladığınız bir dosya numarası onaylandığında size otomatik bildirim gönderilir."),
    ("⭐", "Favorilerim", "Takip etmek istediğiniz dosya numaralarını favorilere ekleyin, tek ekrandan hepsinin güncel durumunu görün."),
    ("📊", "Sıra Tahmini", "Aynı yılda ve maddede, dosyanızın tahmini kaçıncı sırada olduğunu ve size en yakın onaylanmış numaraları görün."),
    ("📄", "Resmi Belge Görüntüleme", "Sistemin sizin için bulduğu resmi PDF belgesini uygulamadan doğrudan açıp inceleyin."),
    ("🌐", "3 Dil Desteği", "Türkçe, İngilizce ve Romence arasında anında geçiş yapın."),
    ("🔒", "Gizlilik Odaklı", "Ad, TC/CNP kimlik numarası, adres gibi hiçbir kişisel bilginiz istenmez ya da saklanmaz."),
    ("💳", "Tek Seferlik Satın Alma", "Aynı Google hesabıyla istediğiniz kadar cihaza ücretsiz olarak tekrar yükleyin -- telefon değiştirseniz bile tekrar ödeme yapmazsınız."),
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
]

_EKRAN_GORUNTULERI = [
    ("ekran-ana.png", "Sorgulama ekranı"),
    ("ekran-onay.png", "Onaylanmış başvuru sonucu"),
    ("ekran-sira.png", "Sıra tahmini"),
    ("ekran-istatistik.png", "Genel istatistikler"),
    ("ekran-grafik.png", "Yıllara göre dağılım"),
]


def tanitim_sayfasi_html(toplam_stadiu=None, toplam_onay=None, toplam_bekleyen=None):
    """
    toplam_* verilirse (main.py /api/istatistikler/genel'in önbelleğinden),
    sayfada gerçek/güncel rakamlar gösterilir -- verilmezse (önbellek henüz
    hesaplanmadıysa) o bölüm sessizce atlanır, sayfa yine de tam çalışır.
    """
    # 2026-08-20 (kullanıcı isteği: "otomatik döngülü galeri" -- gerçek bir
    # video üretme aracımız olmadığı için, elimizdeki gerçek ekran
    # görüntülerini CSS animasyonuyla otomatik geçişli bir "slayt" haline
    # getiriyoruz. JavaScript GEREKMİYOR (saf CSS keyframe animasyonu) --
    # betikler engellenen bir tarayıcıda bile çalışır. Her görüntü kendi
    # animation-delay'iyle sırayla belirip kayboluyor.
    _ADET = len(_EKRAN_GORUNTULERI)
    _SLOT_SN = 3.4  # her görüntünün ekranda kaldığı süre
    _TOPLAM_SN = _SLOT_SN * _ADET
    karusel_resim_html = "".join(
        f'<img src="/statik/landing/{dosya}" alt="{aciklama}" loading="lazy" '
        f'style="animation-delay:{i * _SLOT_SN:.1f}s">'
        for i, (dosya, aciklama) in enumerate(_EKRAN_GORUNTULERI)
    )
    karusel_nokta_html = "".join(
        f'<span style="animation-delay:{i * _SLOT_SN:.1f}s"></span>'
        for i in range(_ADET)
    )
    karusel_altyazi_html = "".join(
        f'<span style="animation-delay:{i * _SLOT_SN:.1f}s">{aciklama}</span>'
        for i, (_, aciklama) in enumerate(_EKRAN_GORUNTULERI)
    )

    ozellik_html = "".join(
        f'<div class="ozellik"><span class="ikon">{ikon}</span>'
        f'<div><h3>{baslik}</h3><p>{aciklama}</p></div></div>'
        for ikon, baslik, aciklama in _OZELLIKLER
    )

    sss_html = "".join(
        f'<div class="sss-satir"><h3>{soru}</h3><p>{cevap}</p></div>'
        for soru, cevap in _SSS
    )

    if PLAY_STORE_URL:
        magaza_html = f'<a class="magaza-buton" href="{PLAY_STORE_URL}">▶ Play Store\'da İndir</a>'
    else:
        magaza_html = '<div class="magaza-rozet">🕒 Yakında Play Store\'da</div>'

    istatistik_html = ""
    if toplam_stadiu is not None and toplam_onay is not None and toplam_bekleyen is not None:
        istatistik_html = f"""
        <section class="istatistik-serit">
          <div class="ist-oge"><b>{toplam_stadiu:,}</b><span>Toplam kabul edilen başvuru</span></div>
          <div class="ist-oge"><b>{toplam_onay:,}</b><span>Onaylanan</span></div>
          <div class="ist-oge"><b>{toplam_bekleyen:,}</b><span>Hâlâ bekleyen</span></div>
        </section>""".replace(",", ".")

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
<style>
  :root {{
    --lacivert-koyu: #0f1a2e;
    --lacivert: #1E2C4A;
    --yuzey: #27375A;
    --kenar: #2E3B5C;
    --altin: #E3A83B;
    --beyaz: #F5F7FA;
    --gri: #8E9AB8;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--lacivert-koyu); color: var(--beyaz);
    font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
    line-height: 1.6;
  }}
  a {{ color: var(--altin); }}
  .kapsayici {{ max-width: 1040px; margin: 0 auto; padding: 0 20px; }}

  header {{ text-align: center; padding: 56px 20px 40px; }}
  /* 2026-08-20 DÜZELTMESİ (kullanıcı Windows'ta fark etti): 🇷🇴 bayrak
     emojisi Windows'ta çoğu tarayıcıda düzgün render edilmiyor, sadece
     "RO" harfleri görünüyor. Uygulamanın kendisinde ZATEN emoji değil,
     elle çizilmiş 3 renkli bant kullanılıyor (bkz. components/flag-mark.tsx)
     -- aynısı burada da, platform/font bağımsız garanti çalışsın diye. */
  .bayrak {{
    display: flex; width: 52px; height: 36px; margin: 0 auto;
    border-radius: 8px; overflow: hidden; border: 2px solid var(--altin);
  }}
  .bayrak span {{ flex: 1; }}
  h1 {{ font-size: clamp(28px, 5vw, 44px); margin: 8px 0 6px; }}
  .slogan {{ color: var(--gri); font-size: 17px; max-width: 560px; margin: 0 auto 28px; }}

  .magaza-rozet {{
    display: inline-block; background: var(--yuzey); border: 1px solid var(--kenar);
    color: var(--gri); padding: 12px 24px; border-radius: 30px; font-weight: 700; font-size: 14px;
  }}
  .magaza-buton {{
    display: inline-block; background: var(--altin); color: var(--lacivert-koyu);
    padding: 14px 30px; border-radius: 30px; font-weight: 800; text-decoration: none; font-size: 15px;
  }}

  .istatistik-serit {{
    display: flex; justify-content: center; gap: 40px; flex-wrap: wrap;
    margin: 40px auto 0; max-width: 720px;
  }}
  .ist-oge {{ text-align: center; }}
  .ist-oge b {{ display: block; font-size: 28px; color: var(--altin); }}
  .ist-oge span {{ color: var(--gri); font-size: 12.5px; }}

  section {{ padding: 40px 0; }}
  h2 {{ text-align: center; font-size: 26px; margin-bottom: 8px; }}
  .bolum-alt {{ text-align: center; color: var(--gri); margin-bottom: 32px; }}

  /* Otomatik döngülü ekran görüntüsü "slaytı" -- saf CSS, JS yok. */
  .karusel {{
    position: relative; width: 240px; height: 520px; margin: 0 auto;
  }}
  .karusel img {{
    position: absolute; top: 0; left: 0; width: 100%; height: 100%;
    object-fit: cover; object-position: top;
    border-radius: 20px; border: 1px solid var(--kenar);
    box-shadow: 0 16px 40px rgba(0,0,0,0.4);
    opacity: 0; animation-name: karusel-gecis; animation-duration: {_TOPLAM_SN}s;
    animation-iteration-count: infinite; animation-timing-function: ease-in-out;
  }}
  @keyframes karusel-gecis {{
    0% {{ opacity: 0; }}
    3% {{ opacity: 1; }}
    {100 / _ADET - 3:.1f}% {{ opacity: 1; }}
    {100 / _ADET:.1f}% {{ opacity: 0; }}
    100% {{ opacity: 0; }}
  }}
  .karusel-altyazi {{ position: relative; height: 26px; margin-top: 16px; text-align: center; }}
  .karusel-altyazi span {{
    position: absolute; left: 0; right: 0; color: var(--gri); font-size: 13px;
    opacity: 0; animation-name: karusel-gecis; animation-duration: {_TOPLAM_SN}s;
    animation-iteration-count: infinite; animation-timing-function: ease-in-out;
  }}
  .karusel-noktalar {{ display: flex; justify-content: center; gap: 7px; margin-top: 14px; }}
  .karusel-noktalar span {{
    width: 7px; height: 7px; border-radius: 4px; background: var(--kenar);
    animation-name: karusel-nokta; animation-duration: {_TOPLAM_SN}s;
    animation-iteration-count: infinite; animation-timing-function: ease-in-out;
  }}
  @keyframes karusel-nokta {{
    0% {{ background: var(--kenar); width: 7px; }}
    3% {{ background: var(--altin); width: 20px; }}
    {100 / _ADET - 3:.1f}% {{ background: var(--altin); width: 20px; }}
    {100 / _ADET:.1f}% {{ background: var(--kenar); width: 7px; }}
    100% {{ background: var(--kenar); width: 7px; }}
  }}
  /* Hareket hassasiyeti tercih edenler için: tek görüntü sabit kalır. */
  @media (prefers-reduced-motion: reduce) {{
    .karusel img, .karusel-altyazi span, .karusel-noktalar span {{ animation: none !important; opacity: 0; }}
    .karusel img:first-child, .karusel-altyazi span:first-child {{ opacity: 1 !important; }}
    .karusel-noktalar span:first-child {{ background: var(--altin); width: 20px; }}
  }}

  .ozellikler-izgara {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 20px;
  }}
  .ozellik {{
    display: flex; gap: 14px; background: var(--yuzey); border: 1px solid var(--kenar);
    border-radius: 14px; padding: 18px;
  }}
  .ozellik .ikon {{ font-size: 26px; line-height: 1; }}
  .ozellik h3 {{ margin: 0 0 4px; font-size: 15px; }}
  .ozellik p {{ margin: 0; color: var(--gri); font-size: 13px; }}

  .sss-liste {{ max-width: 720px; margin: 0 auto; display: flex; flex-direction: column; gap: 16px; }}
  .sss-satir {{
    background: var(--yuzey); border: 1px solid var(--kenar); border-radius: 14px; padding: 18px 22px;
  }}
  .sss-satir h3 {{ margin: 0 0 6px; font-size: 15.5px; color: var(--beyaz); }}
  .sss-satir p {{ margin: 0; color: var(--gri); font-size: 13.5px; }}

  .cta {{ text-align: center; padding: 56px 20px; }}
  .cta h2 {{ margin-bottom: 18px; }}

  footer {{
    text-align: center; padding: 30px 20px 50px; color: var(--gri); font-size: 12.5px;
    border-top: 1px solid var(--kenar); margin-top: 20px;
  }}
  footer a {{ color: var(--gri); margin: 0 8px; }}
  .imza {{ margin-top: 10px; opacity: 0.8; }}

  .uyari-serit {{
    background: rgba(227,168,59,0.10); border: 1px solid rgba(227,168,59,0.3);
    border-radius: 12px; padding: 14px 18px; font-size: 12.5px; color: var(--gri);
    max-width: 720px; margin: 0 auto;
  }}
</style>
</head>
<body>

<header>
  <div class="bayrak"><span style="background:#002B7F"></span><span style="background:#FCD116"></span><span style="background:#CE1126"></span></div>
  <h1>Romanya Dosya Takip</h1>
  <p class="slogan">Romanya vatandaşlığı başvurunuzun Stadiu Dosar ve Ordine durumunu saniyeler içinde sorgulayın -- onaylandığında otomatik bildirim alın.</p>
  {magaza_html}
  {istatistik_html}
</header>

<div class="kapsayici">

  <section>
    <h2>Uygulamadan Gerçek Görüntüler</h2>
    <p class="bolum-alt">Uydurma değil, gerçek uygulamadan alınmış ekranlar</p>
    <div class="karusel">
      {karusel_resim_html}
    </div>
    <div class="karusel-altyazi">
      {karusel_altyazi_html}
    </div>
    <div class="karusel-noktalar">
      {karusel_nokta_html}
    </div>
  </section>

  <section>
    <h2>Özellikler</h2>
    <p class="bolum-alt">Vatandaşlık başvuru sürecinizi kolaylaştırmak için</p>
    <div class="ozellikler-izgara">
      {ozellik_html}
    </div>
  </section>

  <section>
    <h2>Sıkça Sorulan Sorular</h2>
    <p class="bolum-alt">Stadiu Dosar, Ordine ve dosya sorgulama hakkında</p>
    <div class="sss-liste">
      {sss_html}
    </div>
  </section>

  <section class="cta">
    <h2>Hazır mısınız?</h2>
    {magaza_html}
  </section>

  <div class="uyari-serit">
    ℹ️ Bu uygulama, resmi bir devlet uygulaması değildir -- başvuru sürecini yürütmez, yalnızca cetatenie.just.ro sitesinde yayınlanan resmi PDF listelerini takip etmenizi kolaylaştırır.
  </div>

</div>

<footer>
  <div>
    <a href="/gizlilik-politikasi">Gizlilik Politikası</a> ·
    <a href="/kullanim-sartlari">Kullanım Şartları</a> ·
    <a href="mailto:ahmet.knby.25@gmail.com">İletişim</a>
  </div>
  <div class="imza">🔒 Secured &amp; Encrypted System · By @knby · © 2026</div>
</footer>

</body>
</html>"""
