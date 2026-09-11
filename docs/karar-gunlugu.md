# Karar Günlüğü — Romanya Dosya Takip

Bu dosya, projenin **konuşma geçmişinde geçen ama koddan/git log'dan tek
başına anlaşılamayan** kararları, kök nedenleri ve "neden böyle yapıldı"
bilgisini konu başlıklarına göre saklar. Kod zaten neyin ne yaptığını
gösteriyor — burası **neden** öyle yapıldığını gösteriyor.

Yeni bir oturumda önce [`CLAUDE.md`](../CLAUDE.md) okunmalı (genel
yönelim), sonra ihtiyaç duyulan konu başlığı burada aranmalı. Kronolojik
tam detay (bu özetin kaynağı) `.claude/projects/.../memory/` altındaki
hafıza dosyalarında ve `git log`'da duruyor.

---

## 1. Mimari

**Tek-süreç deseni (`WEB_CONCURRENCY=1`).** Render Starter plan 512Mi RAM
ile sınırlı. Backend tek Python sürecinde çalışıyor; bu yüzden basit
`{"veri": None, "zaman": 0.0}` bellek-içi önbellek deseni (ör.
`_genel_istatistik_onbellek`, `_disk_boyutu_onbellek`, `_metrikler_onbellek`)
güvenli/tutarlı — birden fazla süreç olsaydı önbellekler birbirini
görmeyip tutarsız kalırdı. Yeni bir pahalı hesaplama eklenirken aynı desen
kullanılmalı.

**Scraper mimarisi (`bot.py`) dosya-adı bazlı, sayfa-yapısı bazlı DEĞİL.**
Bir PDF'nin hangi kategoriye ait olduğu kararı `dosya_utils.py`'deki
`stadiu_dosya_kategorisi_uyusuyor_mu`/`ordine_dosya_kategorisi_uyusuyor_mu`
ile **dosya adından** veriliyor — cetatenie.just.ro sayfa tasarımını
değiştirse bile (ki 2026-08-19'da ORDİNE tarafında gerçekten değiştirdi,
aşağıya bkz.) sınıflandırma bozulmuyor, sadece "PDF'leri keşfetme" yöntemi
kırılabiliyor. Bu yüzden keşif için ikinci, tasarımdan bağımsız bir "B
Planı" var: `_wp_json_ile_pdf_kesfet()` (WordPress'in
`/wp-json/wp/v2/media` REST API'si, tarih sıralı tüm dosyaları JSON
döndürür) — SADECE A Planı (tıklama/sekme) bir kategoriyi hiç
bulamadığında tek seferlik devreye giriyor, sürekli paralel çalışmıyor
(siteye ek yük bindirmemek için bilinçli tercih, 2026-08-19).

**2026-08-25 — Firefox → Chromium (OOM kök neden #1).** Bot her
tetiklendiğinde Render'ın OOM-kill'i devreye giriyordu. `psutil` ile
kanıtlandı: Firefox headless tek başına context+page açar açmaz ~524MB
RSS'e çıkıyor (FastAPI'nin ~90MB taban kullanımı eklenmeden BİLE 512Mi
limitini aşıyor), Chromium aynı işi ~312MB'da yapıyor. Kullanıcı ilk
"Render planını yükselt" ($18/ay ek) önerisini reddedip kod seviyesinde
kök neden istedi — bkz. [[maliyetli-cozum-onerme-oncesi-analiz]] dersi.
`p.firefox.launch()` → `p.chromium.launch()`, Render build komutu
güncellendi (`playwright install chromium`). Commit `4800208`.

**2026-08-25 — WAF/indirme kök nedeni.** Sayfa gezinme Playwright ile
WAF'ın JS-challenge'ını geçiyordu ama PDF *indirme* ayrı bir `curl_cffi`
oturumuyla yapılıyordu — bu tutarsızlık WAF tarafından yakalanıp tüm
indirmeler 503 dönüyordu. Çözüm: hem A Planı hem B Planı artık sayfayı
zaten gezmiş olan Playwright context'in kendi ağ istemcisini
(`context.request.get`) kullanıyor. Commit `5500d65`.

**2026-09-10 — bot.py alt süreçte izolasyon (OOM kök neden #2).**
Chromium→Chromium geçişinden aylar sonra OOM tekrar başladı (7 ve 10
Eylül). Kök neden: bot.py FastAPI ile AYNI OS sürecinde çalışıyordu,
Python'un bellek ayırıcısı Chromium nesnelerini serbest bıraktıktan sonra
belleği işletim sistemine geri vermiyor — her taramadan sonra sürecin
taban kullanımı biraz yüksek kalıp gün içinde birikiyordu (kanıt: OOM
sonrası restart belleği sıfırlayınca aynı günün ikinci taraması hep
sorunsuz geçiyordu). Çözüm: `main.py`'deki `run_bot()`, `bot.py`'yi artık
`subprocess.run([sys.executable, "bot.py"], ...)` ile TAMAMEN AYRI bir OS
sürecinde çalıştırıyor — alt süreç bitince kullandığı tüm bellek OS
tarafından garanti geri alınıyor. Commit `fb7ad22`. Detay:
[[render-bellek-oom-kalici-cozum]] (proje hafızası).

**Kategori/sayfa yapısı kırılganlıkları (kronolojik, hepsi kod-seviyesinde
kalıcı çözüldü):**
- 2026-08-16: "NR. DOSAR" ve "CONSULAT/ANC" aslında tek sekme (metin
  satıra sarıldığı için iki sanılmıştı) — sadece "NR. DOSAR" kullanılıyor.
  Detay: [[stadiu-kategori-birlesmesi]].
- 2026-08-19: ORDİNE tarafı sitede TAMAMEN yeniden yapılandırıldı — tek
  sayfa JS sekmesinden, her kategorinin kendi kalıcı URL'sine geçti.
  `page.url` değişti mi kontrolüyle iki yapı da (STADIU hâlâ eski tip)
  otomatik ayırt ediliyor. Commit `41e53cf`.
- 2026-08-31 / 2026-09-06: Cari yılın PDF'i (ör. `Art-10-2026-...pdf`)
  sitede AYNI AD ile yerinde büyüyor (yeni kayıt eklendikçe) — botun
  "zaten indirildi, atla" kısayolu bunu es geçiyordu, 1-2 haneli (erken
  eklenmiş) dosya numaraları hiç görünmüyordu. `_guncel_yil_dosyasi_mi()`
  ile cari yıl SADECE stadiu için her taramada yeniden indiriliyor
  (ordine tek seferlik kararname, hiç değişmiyor — kapsam dışı
  bırakıldı). Bu düzeltmenin kendisi bir regex hatası içeriyordu (birden
  fazla "20XX" deseni olan dosya adlarında `re.search` ilk eşleşmeyi
  alıyordu) — `re.findall` + üyelik kontrolüne çevrilip düzeltildi
  (2026-09-06, commit `a3c9019`), hem `bot.py` hem
  `scripts/pdf_senkronize.py`'de.

**Bilinen, henüz çözülmemiş kırılganlık: `bot.py`'de eşzamanlı çalışmayı
engelleyen bir kilit/mutex yok.** 2026-08-31'de iki manuel tetiklemenin
aynı anda sürdüğüne dair zamanlama kanıtı bulundu (ör. 10:37 ve 11:21
başlayan iki ayrı tarama üst üste binmiş olabilir). Kullanıcıyla
konuşulmadı, kod değişikliği yapılmadı — ileride bir run-lock
eklenebilir.

## 2. Güvenlik

2026-08-18/19'da kapsamlı bir güvenlik denetimi yapılıp bulunan maddeler
tek tek kullanıcı onayıyla kapatıldı: HSTS+CSP+X-Content-Type-Options+
X-Frame-Options+Referrer-Policy başlıkları, SQL sorgularında whitelist ile
kolon adı doğrulama, `/pdfs` path traversal koruması (StaticFiles zaten
güvenli), CORS `allow_origins=["*"]` → `[]` (mobil uygulama CORS'a tabi
değil), cihaz kimliğinin `expo-crypto`/`expo-secure-store` ile
kriptografik güvenli üretimi/saklanması, `veri_sil.py` admin script'i
(kullanıcı verisi kalıcı silme, dry-run önizlemeli). Canlı yetkisiz
erişim testiyle (7/7 korumalı uç + 6 path-traversal denemesi) doğrulandı,
hiçbir açık bulunmadı.

**2026-08-23 — Admin girişi HTTP Basic Auth'tan imzalı oturum çerezine
geçirildi.** HMAC-SHA256 imzalı, 90 gün geçerli, stateless çerez
(`_admin_oturum_dogrula`, `main.py`). `ADMIN_SIFRE`/`ADMIN_OTURUM_ANAHTARI`
ayarlı değilse panel **fail-closed** (tamamen kapalı) kalıyor — bilinçli
tasarım.

**2026-09-05 — güvenlik taraması: 3 gerçek CVE + bilgi sızıntısı
bulundu.** `pip-audit` ile `pypdf` 6.15.0'da CVE-2026-84309/84310/84311
(kötü PDF ile CPU/bellek tükenmesi, `WEB_CONCURRENCY=1` olduğu için tüm
sunucuyu kilitleyebilirdi) — 6.16.1'e sabitlendi. `/docs`, `/redoc`,
`/openapi.json` herkese açıktı (admin uçları dahil tüm API yüzeyini
sızdırıyordu) — `FastAPI(docs_url=None, redoc_url=None, openapi_url=None)`
ile kapatıldı. `pip-audit` bu makinede `requirements.txt`'teki Türkçe
yorumlar yüzünden `PYTHONUTF8=1` olmadan cp1254 decode hatası veriyor —
tekrar çalıştırılırsa bu bayrakla çalıştırılmalı.

**Kalıcı kural: `.env` dosyaları force ile git'e eklenemez** —
`.claude/hooks/env_koru.py` bunu otomatik engelliyor. **IBAN/kart/ödeme
bilgisi alanlarına Claude hiçbir zaman dokunmuyor** — Play Console ödeme
profili sürecinde 3+ kez bilinçli olarak reddedildi, kullanıcı bizzat
girdi.

## 3. Maliyet / Hesaplar

| Hizmet | Hesap | Bu projede ne için | Maliyet |
|---|---|---|---|
| Render | `ahmet.kanbay@hotmail.com` (kişisel, projeden önce var olan unutulmuş bir servis keşfedildi) | Backend barındırma, Starter plan + 10GB kalıcı disk (`/data`) | ~9.5$/ay |
| Sentry | proje-özel org (`romanya-dosya-takip-th`) | Canlı hata izleme (crash-free sessions) | Ücretsiz, API token SADECE okuma yetkili — hatalar sentry.io panelinden elle "Resolve" edilmeli |
| Backblaze B2 | ayrı hesap | Sadece `dosyalar.db` bulut yedeği (PDF'ler yedeklenmiyor, ayrı bir yerel haftalık senkron var — bkz. [[pdf-senkron-kurulumu]]) | ~20-25 cent/ay (kredi kartı eklenene kadar günlük 10GB kota sorunu yaşandı, çözüldü) |
| Gmail SMTP | `ahmet.knby.25@gmail.com` (proje-özel, kişisel adres değil) | Admin bildirim e-postaları (Outlook/Hotmail artık SMTP temel kimlik doğrulamayı kapattığı için buraya geçildi) | Ücretsiz (uygulama şifresi) |
| Telegram Bot | `@romanya_nobetci_bot` | Gözcü'nün birincil, güvenilir bildirim kanalı (Web Push ColorOS'ta arka planda çalışmadığı için) | Ücretsiz |
| Play Console | `knby` geliştirici hesabı, `ahmet.knby.25@gmail.com` | Uygulama yayını, kapalı test | Tek seferlik geliştirici kayıt ücreti (kullanıcı öder) |
| Google Cloud | proje `romanya-dosya-takip-506621` | EAS submit servis hesabı (Play Console'a komut satırından AAB yükleme) | Ücretsiz katman |
| GitHub Actions | `ahmetkanbay-ops/romanya-dosya-takip` (public repo) | Gözcü'nün zamanlayıcısı (2 saatte bir) | Ücretsiz (public repo dakika kotası sorun değil) |

**Uygulama fiyatlandırması (Play Store):** Dünya geneli taban 15 USD,
**Türkiye özel olarak ₺721,00** (kullanıcının net talebi).

**Önemli ilke (kullanıcı geri bildirimiyle netleşti — bkz.
[[maliyetli-cozum-onerme-oncesi-analiz]]):** Maliyetli bir çözüm (plan
yükseltme, yeni abonelik) önermeden önce MUTLAKA kod seviyesinde ölçülmüş
bir kök neden araştırması yapılmalı — 2026-08-25'te bu atlanıp "Render
planını yükselt" önerilmişti, kullanıcı haklı olarak reddetti, gerçek
(ücretsiz) çözüm ölçümle bulundu.

## 4. Otomasyon / Zamanlanmış Görevler

| Görev | Sıklık | Nerede | Not |
|---|---|---|---|
| Site taraması (`run_bot`) | Günde 2x: 11:00 + 15:00 (Romanya saati) | Render, APScheduler (`main.py` `lifespan()`) | 2026-09-02'de 1x'ten 2x'e çıkarıldı (kullanıcı kararı, "aynı gün eklenen PDF'in 1 gün geç görünmesi" riskini azaltmak için) — bkz. [[tarama-sikligi-2x-izleme]]. Daha önce günde 5x (2 saatte bir) denenmiş, site IP'yi bloke etmişti (2026-08-15) — bir daha SIKLAŞTIRILMAMALI |
| Haftalık derin tarama | Sadece Pazar, mevcut taramalardan birine eklenti | Render, aynı scheduler | PDF'lerin silinip silinmediğini/boyut değiştiğini HEAD isteğiyle kontrol eder, sıklığı ARTIRMAZ |
| Veritabanı yedeği (yerel) | Her gece 03:00 | Render, APScheduler | `sqlite3` online backup API'si (WAL-güvenli), 2 gün saklanıyor (önceden 7 gündü, disk %80 dolunca düşürüldü) |
| Bulut yedeği (B2) | Aynı akışta, 03:00 sonrası | Render → Backblaze B2 | 30 gün saklanıyor, sadece DB |
| Disk kotası kontrolü | Her gün 06:00 | Render, APScheduler | |
| Gözcü sağlık kontrolü | 2 saatte bir | GitHub Actions (`gece-nobeti.yml`, dosya adı tarihsel, içerik "Gözcü" olarak yeniden adlandırıldı) | `/api/admin/nobetci-kontrol-et`'i çağırır, durum DEĞİŞİRSE Telegram+e-posta uyarısı |
| PDF yerel senkronu | Her Pazar 10:00 | **Kullanıcının kendi bilgisayarı**, Windows Görev Zamanlayıcı (`RomanyaDosyaTakip-PDFSenkron`) | `StartWhenAvailable=True` — PC kapalıysa bir sonraki açılışta tetiklenir. Detay: [[pdf-senkron-kurulumu]] |

## 5. Gözcü (İzleme Sistemi) — Mimari ve Geçmiş

Faz 0-1-2 olarak inşa edildi (plan: kullanıcı onaylı Artifact sunumu,
2026-08-29):

- **Faz 0** (`/api/admin/saglik-kontrolu`): makineler-arası JSON sağlık
  ucu, admin çerezinden ayrı statik anahtar (`NOBETCI_ANAHTARI`, header
  `X-Nobetci-Anahtar`).
- **Faz 1** (denendi, birincil kanal OLMADI): Admin paneline (PWA) Web
  Push eklendi — ama Oppo/ColorOS cihazlarda ekran kilitliyken/arka
  planda bildirim GELMİYORDU (6 farklı Android ayarı denendi, hiçbiri
  çözmedi — kök neden muhtemelen ColorOS'un web push'a özgü, root
  olmadan erişilemeyen bir kısıtlaması). Kod duruyor ama kullanılmıyor.
- **Faz 2** (canlı, birincil kanal): GitHub Actions (ücretsiz, 2 saatte
  bir) → `/api/admin/nobetci-kontrol-et` → `nobetci_durum_gecmisi`
  tablosuyla önceki durumla kıyaslama → SADECE değiştiyse
  `admin_kritik_uyari()` → **Telegram (`@romanya_nobetci_bot`) + e-posta**.
  Spam yok (durum sabitse sessiz).

**İzlenen kontroller (`admin_panel.py`
`bugunun_durumu_verisini_getir`/`bugunun_durumunu_getir`):** Günlük
Tarama, Render (genel), Render (bellek/OOM — 2026-09-07 eklendi),
Sentry, Backblaze B2, GitHub.

**"Gece Nöbeti" → "Gözcü" yeniden adlandırması (2026-09-06, kullanıcı
tercihi, AskUserQuestion ile seçildi).** İsim gece-spesifik bir çağrışım
yapıyordu ama sistem 7/24 çalışıyor — kullanıcı "sempatik" bir isim
istedi. `.github/workflows/gece-nobeti.yml` DOSYA ADI bilinçli olarak
değiştirilmedi (sadece içeriği), kod/yorumlardaki tüm referanslar
güncellendi.

**Kullanıcının standart talebi (2026-09-02, birebir):** *"sistem sadece
tespit ettiğimiz hatalara odaklanıp onunla yetinmemeli... esas olan
sitemde oluşabilecek bütün problemlerden haberdar olması, çözmesi,
çözemesede bildirmesi gerekir"* — Gözcü'nün kapsamı bu ilkeye göre
genişletiliyor (en son örnek: 2026-09-07 Render bellek/OOM kontrolü).

## 6. Bilinen Sorunlar / Çözümler (büyük vakalar, kronolojik)

- **2026-08-19 — Render'a taşıma.** Teknik altyapı ucuz yoldan
  tamamlandı: zaten var olan (unutulmuş) bir Render servisi bulunup
  kullanıldı, SSH/SCP ile 1GB DB (gzip ile 88MB'a küçültülüp) + 725MB PDF
  arşivi taşındı, uçtan uca doğrulandı (satır sayısı, dosya sayısı, güvenlik
  kontrolleri, gerçek sorgulama). `DATA_DIR` ortam değişkeni deseni
  eklendi (Render'da `/data`, yerelde `backend/`).
- **2026-08-21 — cetatenie.just.ro genel (bize özel olmayan) kesinti
  yaşadı.** Cloudflare 522, DNS bile çözülmüyordu — haber kaynağıyla
  doğrulandı (portal.just.ro da aynı anda çökmüştü). Kullanıcının "biz
  zorladık mı" endişesi teknik kanıtla giderildi.
- **2026-08-22/23 — Admin panel 33-45 saniye sürüyordu.** Kök neden yeni
  eklenen dış servis kontrolleri DEĞİLDİ — `dosyalar` tablosundaki
  (~1.3M satır) COUNT/GROUP BY sorguları hiç önbelleklenmemişti. 5
  dakikalık önbellek + panelin bu bölümü ayrı uçtan JS ile async
  yüklemesi ile çözüldü (soğuk yükleme ~45sn ama artık sayfayı bloke
  etmiyor, sıcak yükleme ~0.4-0.8sn).
- **2026-08-23 — Kalıcı disk %80.3 doluydu.** Kök neden: yerel yedek
  saklama süresi 7 gündü (~7GB), B2 zaten 30 gün ayrı depoda tutuyordu —
  2 güne indirildi.
- **2026-08-25 — 2 haftalık kesinti sonrası 1886 kayıt kaybı riski,
  iki bağımsız kök neden bulunup düzeltildi aynı gün** (WAF indirme +
  OOM — bkz. Mimari bölümü). Canlı kanıt: 1886 yeni kayıt sorunsuz
  işlendi, deploy sonrası hiç OOM/crash yok.
- **2026-09-02/03 — Backblaze B2 bağlantı sorunu.** 4 ayrı teori
  denendi başarısız oldu, sonunda kök neden anlaşıldı: hesapta kredi
  kartı YOKTU, Backblaze kartsız hesaplara düşük günlük kota
  uyguluyormuş (bucket kotaya ulaşınca düzgün hata yerine bağlantıyı
  kesiyor). Kart eklenince otomatik "No Cap" oldu.
- **2026-09-05 — Yavaş sayfa açılışı.** İlk varsayım ("10MB video
  yavaşlatıyor") ölçümle ÇÜRÜTÜLDÜ. Gerçek neden: `/statik` dosyaları
  `Cache-Control` taşımıyordu, Cloudflare her isteği Render'a (Oregon)
  yönlendiriyordu. `Cache-Control: public, max-age=86400` eklendi —
  BİLEREK sadece `/statik`'e, `/pdfs`'e DEĞİL (Articolul 10 yerinde
  güncelleme riski nedeniyle).
- **2026-09-05 — Google'da ana sayfa aramada çıkmıyor.** Teknik değil,
  otorite/backlink meselesi (site indekste ama sıfır backlink + ~3
  haftalık + paylaşılan `onrender.com` alt alan adı). Kod ile hızlı
  çözümü yok — zaman + backlink + gerçek alan adı gerekiyor.
- **2026-09-06 — 1-2 haneli dosya numarası eşleştirme sorunu (kullanıcı
  Play Store test sürümünde buldu).** ÜÇ ayrı, gerçek, daha önce
  bilinmeyen hata üst üste çıktı: (1) Expo Go yerel backend'e bağlanıyor,
  yerel `dosyalar.db` bayattı; (2) `pdf_senkronize.py` Ağustos'taki
  "yerinde güncellenen PDF'i yeniden indir" düzeltmesini hiç almamıştı;
  (3) o düzeltmenin kendi regex'i birden fazla yıl deseni olan dosya
  adlarında yanlış yılı seçiyordu. Production HİÇBİR ZAMAN bozuk
  değildi — üçü de yerel geliştirme/senkron araçlarındaydı. Hepsi
  düzeltildi (commit `8ff6050`, `a3c9019`).
- **2026-09-06 — Güvenli yük testi.** Kullanıcının "kullanıcı sayısı
  artarsa sistem dayanır mı" sorusu üzerine, ÖNCE global rate-limit
  gevşetmesi önerildi, kullanıcı haklı olarak riskini sorup reddetti —
  gizli anahtar/benzersiz `key_func` ile SADECE test istemcisini
  atlatan, diğer trafiği hiç etkilemeyen bir yönteme geçildi (geçici
  kod, test sonrası tamamen kaldırıldı). Sonuç: 1000 eşzamanlı istekte
  sıfır hata, gerçek tıkanma noktası ~95-98 istek/saniye, sistem
  çökmüyor sadece yavaşlıyor — lansman için engel yok.
- **2026-09-07/10 — Render bellek (OOM) tekrarı ve kalıcı çözümü** —
  bkz. Mimari bölümü ve [[render-bellek-oom-kalici-cozum]].

## 7. Play Store Süreci

- **Geliştirici hesabı:** `knby` (kişisel/individual), Gmail
  `ahmet.knby.25@gmail.com` ile. Kimlik onayı birkaç gün sürdü.
- **Uygulama:** paket adı `com.knby.romanyadosyatakip`, Uygulama ID
  `4973875955496985249`, ad "Romanya Dosya Takip" (Stadiu/Ordine
  ikisini de kapsadığı için "- Stadiu" eki kaldırıldı), dil Türkçe,
  ücretli.
- **Gizlilik/Şartlar linkleri (kalıcı, Play Console formlarında
  kullanılan):** bkz. [[play-store-linkler]].
- **Ödeme profili:** Türkiye'de "Bireysel" hesap türü konum "Türkiye"
  seçilince kilitlenip sadece "Kuruluş" seçilebiliyordu — kullanıcının
  bu Google hesabında ZATEN VAR OLAN bir Bireysel ödeme profili (eski
  Play Store alışverişlerinden) bağlanarak aşıldı, vergi mükellefi
  olmaya gerek kalmadı.
- **Kapalı test:** 12+ test kullanıcısı + 14 gün kesintisiz kayıt şartı
  (Google'ın genel zorunluluğu, yeni geliştirici hesapları için).
  Promosyon kodu ↔ kişi eşleştirmesi Play Console'da tutulmuyor, ayrıca
  kaydediliyor: [[promosyon-kodu-eslestirme]].
- **Yeni sürüm yükleme akışı (kalıcı, tekrar kurulum gerektirmez):**
  `eas build --profile production` → `eas submit` (Google Cloud servis
  hesabı ile, `eas.json`'da yapılandırılı) → Play Console'da "Sürümü
  hazırlayın" → yayın notları (TR/EN/RO) → "İncelemeye gönder". Test
  kullanıcılarının hiçbir şey yapmasına gerek yok, 14 günlük sayacı
  SIFIRLAMAZ.
- **Yayın koşulu (kullanıcı kararı, 2026-08-25'te güncellendi):** "Site
  stabilliği" ön koşul DEĞİL artık — asıl kriter "kesinti sonrası
  toparlanma yeteneği" (bu test edilip kanıtlandı, bkz. bölüm 6).
  Üretime (production) geçiş kararı kapalı test süreci bitince ayrıca
  değerlendirilecek.
- **Android Developer Verification (2026-09-09'da soruldu):** Play
  Console'da kontrol edildi — hesap "Tüm uygulamalarınız... başarıyla
  kaydedildi" durumunda, aksiyon gerekmiyor. Bu politika şu an sadece 4
  ülkeyi (Brezilya/Endonezya/Singapur/Tayland) etkiliyor, global
  genişleme 2027'ye planlı.

## 8. Mobil Uygulama — UI/UX Kararları

- **İkon:** Eski tasarım (Romanya bayrağı + tik) resmi onay mührü gibi
  algılanma riski taşıyordu — "Durum İğnesi" konseptine (altın konum
  iğnesi + lacivert daire + beyaz tik, bayrak rengi YOK) geçildi.
- **Tema:** Tüm ekranları saran altın neon çerçeve (SVG katmanlı,
  `components/neon-cerceve.tsx`), zemin `#1E2C4A`.
- **Footer imza satırı** (`🔒 Secured & Encrypted System · By @knby ·
  © 2026`) BİLİNÇLİ OLARAK her dilde İngilizce kalıyor — marka/güvenlik
  imzası, çevrilmiyor.
- **Cihaz kimliği** `expo-secure-store`'da (Android Keystore/iOS
  Keychain) tutuluyor, göç mantığıyla eski `AsyncStorage` kayıtları
  kaybolmadan taşınıyor.
- **Favoriler ekranı** (2026-09-06): "otomatik güncel tutulur" bilgi
  notu + "İndirilen PDF'i Görüntüle" butonu eklendi (ana ekranda zaten
  vardı, favorilerde hiç yoktu).
- **Yanlış kategori/yıl uyarısı:** "başka kategoride/yılda bulundu"
  önerisi SADECE kullanıcı `alt_kategori` ya da `yil` verdiyse güvenli —
  sadece `ana_kategori` tek başına yeterli daraltma değil, o durumda
  dürüstçe "bulunamadı" deniyor (`main.py` `/api/sorgula`).

## 9. İletişim / Çalışma Tarzı Notları

Bu bölüm kod ile ilgili değil ama gelecekteki oturumların kullanıcıyla
doğru şekilde çalışması için önemli — detaylar ilgili hafıza
dosyalarında:

- [[iletisim-uslubu]] — çok kısa/direkt kapanış cümleleri kaba geliyor.
- [[geriye-donuk-analiz-git-log-kontrolu]] — "neden düzeldi" sorularında
  tahmin yürütmeden `git log`'a bakılmalı.
- [[maliyetli-cozum-onerme-oncesi-analiz]] — maliyetli çözüm önermeden
  önce ücretsiz alternatif tüketilmeli.
- Kullanıcı forwarded email/bildirim ekran görüntülerini **kısa, sade,
  teknik olmayan dilde** özetlenmesini istiyor (2026-09-09, birebir:
  *"bana bir mail geldi ve sana ne olduğunu sordum bu kadar"*) — uzun
  teknik açıklama yerine doğrudan sonuç.
