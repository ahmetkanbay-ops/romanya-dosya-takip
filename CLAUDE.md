# Romanya Dosya Takip — Proje Rehberi

**Yeni bir oturumda (konuşma geçmişi olmadan) önce bu dosyayı, sonra
gerekirse [`docs/karar-gunlugu.md`](docs/karar-gunlugu.md)'nu oku.**
Operasyonel/teknik kurallar aşağıdaki `@AGENTS.md` satırıyla otomatik
yükleniyor — o dosyayı ayrıca okumaya gerek yok, burada tekrarlanmıyor.

@AGENTS.md

## Bu proje ne, kimin için

Romanya vatandaşlık başvurusu yapan kişilerin, cetatenie.just.ro'nun
resmi "Stadiu Dosar" (durum) ve "Ordine" (karar) listelerini elle takip
etmek zorunda kalmadan dosya numaralarını sorgulayıp otomatik bildirim
almasını sağlayan bir sistem. Kullanıcı (proje sahibi) hem geliştirici
hem de gerçek bir başvurucu — kendi ihtiyacından doğan bir araç, şimdi
Play Store'da (kapalı test aşamasında) gerçek kullanıcılara açılıyor.

**Bileşenler:**
- **Backend** (`backend/`): FastAPI + SQLite (`dosyalar.db`, ~1.35M+
  satır), Render'da barındırılıyor (`romanya-dosya-takip.onrender.com`).
- **Scraper** (`backend/bot.py`): Playwright/Chromium ile
  cetatenie.just.ro'yu günde 2 kez tarayıp yeni PDF'leri indirip
  veritabanına işliyor.
- **Mobil uygulama** (`app/`): Expo/React Native, Play Store kapalı test
  aşamasında (paket adı `com.knby.romanyadosyatakip`).
- **Admin paneli** (`/admin`, `backend/admin_panel.py`): sistem
  sağlığı/istatistikler, imzalı oturum çerezi ile korunuyor.
- **Gözcü** (`.github/workflows/gece-nobeti.yml` + `/api/admin/
  nobetci-kontrol-et`): GitHub Actions'la 2 saatte bir çalışan, durum
  değişikliklerini Telegram+e-posta ile bildiren 7/24 izleme katmanı.

## Kullanılan hesaplar/hizmetler (özet — tam maliyet/gerekçe tablosu
[`docs/karar-gunlugu.md` §3](docs/karar-gunlugu.md#3-maliyet--hesaplar))

| Hizmet | Bu projede ne için |
|---|---|
| Render (`ahmet.kanbay@hotmail.com`) | Backend barındırma, Starter + 10GB kalıcı disk |
| Sentry | Canlı hata izleme (salt-okunur API token) |
| Backblaze B2 | Sadece `dosyalar.db` bulut yedeği |
| Gmail SMTP (`ahmet.knby.25@gmail.com`) | Admin bildirim e-postaları (Outlook OAuth kısıtı yüzünden Gmail'e geçildi) |
| Telegram (`@romanya_nobetci_bot`) | Gözcü'nün birincil bildirim kanalı |
| Play Console (`knby` hesabı) | Uygulama yayını, kapalı test |
| GitHub Actions | Gözcü'nün zamanlayıcısı |
| Windows Görev Zamanlayıcı (kullanıcının bilgisayarı) | Haftalık PDF yerel senkronu |

Global hesap listesi (bu projeye özel olmayanlar dahil) `~/.claude/CLAUDE.md`'de.

## Kritik mimari kararlar (tam detay + tarih: karar günlüğü §1)

- **`bot.py` artık FastAPI'den AYRI bir OS sürecinde çalışıyor**
  (`subprocess.run`, 2026-09-10) — Render'ın 512Mi bellek sınırını
  tekrar tekrar aşan (OOM) bir bellek birikim sorununu kalıcı çözdü.
- **Chromium kullanılıyor, Firefox DEĞİL** (2026-08-25) — Firefox
  headless tek başına 512Mi limitini aşıyordu, Chromium ~312MB'da
  kalıyor.
- **PDF indirme, sayfayı gezen Playwright context'in kendi ağ
  istemcisiyle yapılıyor**, ayrı bir HTTP oturumuyla DEĞİL (2026-08-25)
  — aksi halde WAF indirmeyi 503 ile reddediyor.
- **Kategori sınıflandırması dosya ADINA göre**, sayfa yapısına göre
  DEĞİL — site tasarımı değişse bile (ki değişti) sınıflandırma
  bozulmuyor. Sayfa yapısı değişirse sadece "PDF keşfi" etkilenir, onun
  için de tasarımdan bağımsız bir "B Planı" (WordPress REST API) var.
- **Cari yılın dosyası (`stadiu` için) her taramada yeniden indiriliyor**
  — çünkü site aynı dosya adını YERİNDE güncelliyor (`ordine` buna dahil
  değil, tek seferlik kararname).
- **Tarama sıklığı günde 2 (11:00 + 15:00 Romanya saati) + Pazar ek
  "derin tarama"** — bundan DAHA SIK artırılmamalı, site 5x/gün'de bir
  kez IP'yi bloke etmişti.

## Bilinen sınırlamalar / kırılgan noktalar

- `bot.py`'de eşzamanlı çalışmayı engelleyen bir kilit/mutex YOK —
  manuel tetikleme + zamanlanmış tarama üst üste binebilir (henüz
  gözlemsel kanıt var, kalıcı çözülmedi).
- Backblaze B2'ye SADECE veritabanı yedekleniyor, PDF dosyaları
  yedeklenmiyor — onun için ayrı, yerel (kullanıcının bilgisayarı)
  haftalık senkron var.
- Web Push (admin paneli PWA bildirimleri) Oppo/ColorOS cihazlarda arka
  planda güvenilir çalışmıyor — bu yüzden Gözcü'nün birincil kanalı
  Telegram, Web Push kod olarak duruyor ama kullanılmıyor.
- Sentry API token'ı salt-okunur — hatalar panelden elle "Resolve"
  edilmeli.
- cetatenie.just.ro bir WAF arkasında ve tarama sıklığına hassas —
  yukarıdaki "günde 2" sınırının üzerine çıkmadan önce mutlaka
  kullanıcıyla konuşulmalı.
- Site aynı dosya adını yerinde güncelleyebiliyor (cari yıl) — bu
  yüzden `/pdfs` statik dosyalarına agresif `Cache-Control` YOK
  (bilerek), sadece `/statik`'e var.

## Daha fazla detay

Kronolojik, konu başlıklarına göre organize tam karar günlüğü:
[`docs/karar-gunlugu.md`](docs/karar-gunlugu.md) — Play Store süreci,
güvenlik denetimi geçmişi, büyük arıza/kök-neden vakaları, mobil UI
kararları, ve kullanıcıyla çalışma tarzı notları dahil.
