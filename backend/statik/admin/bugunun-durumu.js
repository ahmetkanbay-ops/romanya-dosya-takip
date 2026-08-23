// 2026-08-22: Bu dosya ÖNCE admin_panel.py içinde satır-içi <script> olarak
// vardı. main.py'deki CSP başlığı ("default-src 'self'; style-src 'self'
// 'unsafe-inline'") script-src için ayrı bir izin İÇERMİYOR -- default-src
// 'self' script'lere de uygulanıyor ve tarayıcı satır-içi script'i SESSİZCE
// engelliyor (konsola bile hata basmıyor kullanıcı arayüzünde görünür bir
// şekilde). Sonuç: "Bugünün Durumu" kartı sonsuza kadar "Yükleniyor…"da
// takılı kalıyordu. Çözüm: script'i /statik altında AYNI KÖKENDEN (same-
// origin) servis edilen bu dosyaya taşımak -- 'unsafe-inline' eklemeye
// gerek kalmadan (bu, gerçek XSS riskini geri getirirdi) default-src 'self'
// kuralını zaten karşılıyor.
//
// Basic Auth kimlik bilgisi tarayıcı tarafından bu adrese otomatik ekleniyor
// (aynı köken/realm, /admin sayfası zaten doğrulanmıştı).
fetch('/api/admin/bugunun-durumu')
  .then(function (r) { return r.ok ? r.text() : Promise.reject(r.status); })
  .then(function (html) {
    document.getElementById('bugunun-durumu-icerik').innerHTML = html;
  })
  .catch(function () {
    document.getElementById('bugunun-durumu-icerik').innerHTML =
      '<p class="bos">Durum bilgisi alınamadı, sayfayı yenileyin.</p>';
  });
