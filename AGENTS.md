# Expo HAS CHANGED

Read the exact versioned docs at https://docs.expo.dev/versions/v54.0.0/ before writing any code.

# Proje: Romanya Dosya Takip

Romanya vatandaşlık başvurularının resmi cetatenie.just.ro listelerini
(Stadiu Dosar / Ordine) takip edip kullanıcıya sorgulama + otomatik
bildirim sunan bir sistem. Backend FastAPI (Render'da barındırılıyor),
mobil taraf Expo/React Native.

## Yerel geliştirme -- kritik davranış

- Backend `python main.py` ile **`--reload` OLMADAN** çalışıyor -- kod
  değişikliği, süreç yeniden başlatılmadan asla etkili olmaz. Değişiklik
  sonrası: 10000 portundaki eski süreci öldür, `python main.py`'yi tekrar
  başlat, `curl http://127.0.0.1:10000/api/durum` ile doğrula.
- Deploy etmeden ÖNCE mutlaka `cd backend && python -c "import main"` çalıştır
  -- import hataları (ör. eksik paket) böyle yakalanır, canlıda değil.
- `cd backend && python -m pytest tests/ -v` -- `dosya_utils.py`'de bir
  değişiklik yaptıysan bunu çalıştırmadan "bitti" deme.

## Git commit mesajları

- Türkçe ama **ASCII-safe** yaz (ç/ğ/ı/ö/ş/ü kullanma) -- Windows konsol
  kod sayfası sorunlarından ders.
- Mesajda kesme işareti (`'`) ya da çok satırlı içerik varsa `git commit -m`
  ile Bash'te tırnak kapanma hatası yaşanıyor -- bunun yerine mesajı bir
  dosyaya yaz, `git commit -F <dosya>` kullan.
- Sonuna her zaman `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.

## Render deploy deseni

- `git push` otomatik deploy tetikler. Durumu Render API'sinden
  (`GET /v1/services/{id}/deploys?limit=1`) yoklayıp `live` olana kadar bekle,
  sonra canlıda `curl` ile GERÇEKTEN doğrula -- "push ettim, biter" deme.
- **Yalnızca canlıda test edilebilen bir şey** varsa (ör. Backblaze B2 --
  yerel ağdan erişilemiyor): admin-korumalı GEÇİCİ bir teşhis ucu ekle,
  deploy et, tetikle, gerçek kanıt (HTTP yanıtı/e-posta) topla, SONRA o ucu
  kaldırıp tekrar deploy et. Geçici ucu kaldırmayı unutma.
- `WEB_CONCURRENCY=1` (tek süreç) -- modül seviyesi `{"veri":None,"zaman":0.0}`
  önbellek deseni bu sayede güvenli/tutarlı. Yeni pahalı bir hesaplama
  eklerken aynı deseni kullan (bkz. `admin_panel.py`), süreç sayısı asla
  varsayılan olarak >1 olmamalı.
- Kalıcı disk: `VERI_DIZINI = os.environ.get("DATA_DIR", BASE_DIR)` --
  Render'da `DATA_DIR=/data`, yerelde ayarlı değil (o zaman `backend/`
  klasörüne düşer). Yeni bir dosya/klasör eklerken `backend/` yolunu SABİT
  YAZMA, bu değişkeni kullan.

## Zaman dilimi

SQLite'ın `CURRENT_TIMESTAMP`'ı HER ZAMAN UTC. Kullanıcıya gösterilen ya da
eşik/karşılaştırma yapılan her yerde `ROMANYA_SAAT_DILIMI` (Europe/Bucharest,
`dosya_utils.py`) ile çevir -- çevirmeyi unutmak birkaç saatlik görsel
(ama gerçek) bir kaymaya yol açar, bu oturumda birden fazla kez oldu.

## cetatenie.just.ro'ya nazik davran

Bot günde 2 kez (11:00 ve 15:00) tarıyor -- 2026-09-02'de kullanıcının
bilinçli kararıyla 1x'ten 2x'e çıkarıldı (gerekçe: aynı gün eklenen bir
PDF'in "1 gün geç" görünmesi güven sarsıcı bir izlenim riski taşıyordu).
Ayrıca SADECE pazar günü, mevcut taramalardan birine eklenti olarak
(sıklığı artırmadan) hafif bir "derin tarama" çalışır -- PDF'lerin
silinip silinmediğini/boyutunun değiştiğini HEAD isteğiyle kontrol eder.
Bundan DAHA SIK polling/retry EKLEME. 5x/gün (2 saatte bir) yapıldığında
site IP'yi bloke etmişti (2026-08-15) -- 2x/gün hâlâ ölçülü ama İLK
BİRKAÇ HAFTA Gece Nöbeti'nin "Günlük Tarama" durumu yakından izlenmeli;
WAF/erişim sorunu belirtisi görülürse hemen 1x/gün'e (main.py
`lifespan()` içindeki `scheduler.add_job` çağrılarından birini kaldır)
geri dönülmeli.

## Güvenlik başlıkları (CSP)

`main.py`deki `Content-Security-Policy: default-src 'self'` satır-içi
`<script>`/`<style>` etiketlerini SESSİZCE engeller (tarayıcıda hata bile
görünmez). Yeni bir script gerekiyorsa `/statik` altında ayrı bir dosya
olarak servis et -- `'unsafe-inline'` eklemeyi ÖNCE düşünme (güvenliği
zayıflatır), sadece gerçekten çaresizsen ve kullanıcıya söyleyerek.

## Admin paneli girişi

2026-08-23'ten beri HTTP Basic Auth DEĞİL -- imzalı (HMAC-SHA256), 90 gün
geçerli, stateless oturum çerezi (`main.py` `_admin_oturum_dogrula`).
Giriş: `/admin/giris`. `ADMIN_SIFRE`/`ADMIN_OTURUM_ANAHTARI` ayarlı değilse
panel fail-closed (tamamen kapalı) kalır -- bu bilinçli bir tasarım,
"varsayılan olarak açık" yapma.

## Geri dönüşü olmayan/dış etkili aksiyonlar -- önce sor

- Render planı/fiyat değişikliği, Play Store'u "Production"a alma, her
  türlü sosyal medya/pazarlama duyurusu: cetatenie.just.ro birkaç gün
  stabil çalıştığını göstermeden YAPMA (kullanıcı kararı).
- `.env` dosyalarını force ile git'e ekleme -- `.claude/hooks/env_koru.py`
  bunu otomatik engelliyor, bypass etmeye çalışma.

## Kod stili

Değişken/fonksiyon adları Türkçe (`dosya_no_norm`, `veritabani_baglantisi`
gibi) -- tüm kod tabanında tutarlı, İngilizce'ye karışık geçme.
