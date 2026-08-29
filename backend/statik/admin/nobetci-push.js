// 2026-08-30 (Gece Nöbeti -- Faz 1): admin panelinin Web Push aboneliğini
// yöneten script. bugunun-durumu.js ile AYNI sebepten /statik altında,
// ayrı dosya olarak servis ediliyor (main.py CSP'si satır-içi <script>'i
// sessizce engelliyor -- bkz. o dosyadaki not).
//
// Akış: "Bildirimlere İzin Ver" -> tarayıcı izni iste -> service worker
// kaydet -> PushManager.subscribe() -> aboneliği backend'e gönder.
// Kayıtlı abonelik varsa "Test Bildirimi Gönder" butonu görünür.

(function () {
  var durumKutusu = document.getElementById('nobetci-push-durum');
  var izinButonu = document.getElementById('nobetci-push-izin-buton');
  var testButonu = document.getElementById('nobetci-push-test-buton');

  function durumGoster(ikon, mesaj) {
    durumKutusu.innerHTML =
      '<span class="durum-ikon">' + ikon + '</span><span class="durum-mesaj">' + mesaj + '</span>';
  }

  if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
    durumGoster('⚠️', 'Bu tarayıcı push bildirimlerini desteklemiyor.');
    izinButonu.style.display = 'none';
    return;
  }

  function base64UrlToUint8Array(base64Url) {
    var dolgu = '='.repeat((4 - (base64Url.length % 4)) % 4);
    var base64 = (base64Url + dolgu).replace(/-/g, '+').replace(/_/g, '/');
    var ham = window.atob(base64);
    var dizi = new Uint8Array(ham.length);
    for (var i = 0; i < ham.length; i++) dizi[i] = ham.charCodeAt(i);
    return dizi;
  }

  // 2026-08-30 DUZELTMESI: izin butonu abonelik varken artik GIZLENMIYOR --
  // yerine "Bildirimi Yenile"ye donusuyor. Once tamamen gizleniyordu, ama
  // tarayicida "abonelik var" gorunup backend'de geçersiz sayilip
  // silinmis (404/410, ornegin telefon pil ayarlari degistirilirken)
  // durumlarda kullanicinin yeniden abone olabilecegi bir yol kalmiyordu
  // (canli testte Oppo/ColorOS'ta tam boyle oldu).
  function mevcutAbonelikVarMi() {
    return navigator.serviceWorker.register('/admin/sw.js')
      .then(function (kayit) { return kayit.pushManager.getSubscription(); })
      .then(function (abonelik) {
        if (abonelik) {
          durumGoster('✅', 'Bu cihaz bildirim almak üzere kayıtlı.');
          izinButonu.textContent = 'Bildirimi Yenile';
          testButonu.style.display = 'inline-block';
        } else if (Notification.permission === 'denied') {
          durumGoster('🚫', 'Bildirim izni reddedilmiş -- tarayıcı ayarlarından açmanız gerekir.');
          izinButonu.style.display = 'none';
        } else {
          durumGoster('🔔', 'Bu cihazda bildirimler henüz açık değil.');
        }
      })
      .catch(function () {
        durumGoster('⚠️', 'Durum kontrol edilemedi, sayfayı yenileyin.');
      });
  }

  izinButonu.addEventListener('click', function () {
    izinButonu.disabled = true;
    durumGoster('⏳', 'İzin isteniyor…');

    fetch('/api/admin/push-genel-anahtar')
      .then(function (r) { return r.json(); })
      .then(function (veri) {
        if (!veri.etkin) {
          durumGoster('⚠️', 'Sunucuda VAPID anahtarı ayarlanmamış -- bildirim altyapısı henüz kapalı.');
          izinButonu.disabled = false;
          return Promise.reject('vapid-yok');
        }
        return navigator.serviceWorker.register('/admin/sw.js').then(function (kayit) {
          // 2026-08-30 DUZELTMESI: mevcut ama backend tarafinda gecersiz
          // sayilip silinmis (404/410) bir abonelik varsa, subscribe()
          // tarayicida hala "var" gorunen O ESKI/OLU aboneligi aynen geri
          // dondurup yeni bir tane OLUSTURMUYOR -- kullanicida "kayitli"
          // yaziyor ama bildirim hic gelmiyordu (canli testte yakalandi,
          // Oppo/ColorOS'ta pil ayari degisikligi sonrasi). Once varsa
          // eskisini unsubscribe edip GERCEKTEN taze bir abonelik aliyoruz.
          return kayit.pushManager.getSubscription().then(function (eski) {
            return eski ? eski.unsubscribe() : null;
          }).then(function () {
            return kayit.pushManager.subscribe({
              userVisibleOnly: true,
              applicationServerKey: base64UrlToUint8Array(veri.genel_anahtar),
            });
          });
        });
      })
      .then(function (abonelik) {
        var json = abonelik.toJSON();
        return fetch('/api/admin/push-abone-ol', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            endpoint: json.endpoint,
            p256dh: json.keys.p256dh,
            auth: json.keys.auth,
          }),
        });
      })
      .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
      .then(function () {
        durumGoster('✅', 'Bildirimler açıldı, bu cihaz kayıtlı.');
        izinButonu.textContent = 'Bildirimi Yenile';
        izinButonu.disabled = false;
        testButonu.style.display = 'inline-block';
      })
      .catch(function (hata) {
        if (hata === 'vapid-yok') return;
        izinButonu.disabled = false;
        if (Notification.permission === 'denied') {
          durumGoster('🚫', 'Bildirim izni reddedildi.');
          izinButonu.style.display = 'none';
        } else {
          durumGoster('⚠️', 'Bir şeyler ters gitti, tekrar deneyin.');
        }
      });
  });

  testButonu.addEventListener('click', function () {
    testButonu.disabled = true;
    var oncekiMetin = testButonu.textContent;
    testButonu.textContent = 'Gönderiliyor…';
    fetch('/api/admin/push-test-gonder', { method: 'POST' })
      .then(function (r) { return r.json(); })
      .then(function (sonuc) {
        testButonu.textContent = oncekiMetin;
        testButonu.disabled = false;
        if (sonuc.gonderildi > 0) {
          durumGoster('✅', 'Test bildirimi gönderildi -- telefonunuzu kontrol edin.');
        } else {
          durumGoster('⚠️', 'Gönderilemedi -- abonelik geçersiz olmuş olabilir, "Bildirimi Yenile"ye basıp tekrar deneyin.');
        }
      })
      .catch(function () {
        testButonu.textContent = oncekiMetin;
        testButonu.disabled = false;
        durumGoster('⚠️', 'Test bildirimi gönderilemedi.');
      });
  });

  mevcutAbonelikVarMi();
})();
