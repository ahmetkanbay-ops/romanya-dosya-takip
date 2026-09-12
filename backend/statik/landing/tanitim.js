// 2026-09-12: tanıtım sayfası redesign'ının etkileşim katmanı.
// CSP (script-src 'self') satır-içi <script> etiketlerini engellediği
// için bu dosya ayrı servis ediliyor -- main.py'deki güvenlik başlığı
// middleware'ine bkz. Framer Motion KULLANILMIYOR (bu sayfa React değil,
// düz Python/HTML) -- aynı "scroll'da beliren, hover'da hareket eden"
// hedefine düz CSS geçişleri + IntersectionObserver ile ulaşılıyor.
(function () {
  "use strict";

  // ---- scroll'da beliren bölümler ----
  var revealEls = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window) {
    var revealIo = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("in");
            revealIo.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12 }
    );
    revealEls.forEach(function (el) {
      revealIo.observe(el);
    });
  } else {
    revealEls.forEach(function (el) {
      el.classList.add("in");
    });
  }

  // ---- istatistik + ziyaretçi sayaçları (scroll'a girince sayarak artar) ----
  var counters = document.querySelectorAll("[data-count]");
  var counted = false;
  function runCounters() {
    if (counted) return;
    counted = true;
    counters.forEach(function (el) {
      var target = parseInt(el.getAttribute("data-count"), 10);
      if (isNaN(target)) return;
      var start = performance.now();
      var dur = 1400;
      function tick(now) {
        var p = Math.min(1, (now - start) / dur);
        var eased = 1 - Math.pow(1 - p, 3);
        el.textContent = Math.round(target * eased).toLocaleString("tr-TR");
        if (p < 1) requestAnimationFrame(tick);
      }
      requestAnimationFrame(tick);
    });
  }
  var statBand = document.querySelector(".stats");
  var visitorBand = document.querySelector(".visitor-strip");
  if ((statBand || visitorBand) && "IntersectionObserver" in window) {
    var counterIo = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            runCounters();
            counterIo.disconnect();
          }
        });
      },
      { threshold: 0.4 }
    );
    if (statBand) counterIo.observe(statBand);
    if (visitorBand) counterIo.observe(visitorBand);
  } else {
    runCounters();
  }

  // ---- telefon ekran görüntüsü karuseli (yatay kaydırma) ----
  var scroller = document.getElementById("phoneScroll");
  if (scroller) {
    var scriptTag = document.currentScript || document.querySelector("script[data-captions]");
    var captions = [];
    try {
      captions = JSON.parse(scriptTag.getAttribute("data-captions") || "[]");
    } catch (e) {
      captions = [];
    }
    var captionEl = document.getElementById("phoneCaption");
    var dotsEl = document.getElementById("phoneDots");
    captions.forEach(function (_, i) {
      var dot = document.createElement("span");
      if (i === 0) dot.className = "on";
      dotsEl.appendChild(dot);
    });
    var frames = scroller.querySelectorAll(".phone-frame");
    var currentIndex = 0;
    function updateActiveFrame() {
      var center = scroller.scrollLeft + scroller.clientWidth / 2;
      var closest = 0;
      var closestDist = Infinity;
      frames.forEach(function (frame, i) {
        var mid = frame.offsetLeft + frame.offsetWidth / 2;
        var dist = Math.abs(mid - center);
        if (dist < closestDist) {
          closestDist = dist;
          closest = i;
        }
      });
      currentIndex = closest;
      if (captions[closest]) captionEl.textContent = captions[closest];
      Array.from(dotsEl.children).forEach(function (dot, i) {
        dot.className = i === closest ? "on" : "";
      });
    }
    // NOT: requestAnimationFrame ile erteleme burada BİLEREK kullanılmıyor
    // -- rAF, sekme arka planda/odakta değilken (ör. bazı otomasyon
    // bağlamlarında) hiç tetiklenmeyebiliyor, canlı testte bunu yakaladık.
    // updateActiveFrame zaten ucuz/salt-okunur bir hesaplama, doğrudan
    // çağırmak yeterince performanslı.
    scroller.addEventListener("scroll", updateActiveFrame, { passive: true });

    // 2026-09-13 EKLENTİSİ (kullanıcı fark etti -- eski tasarımda ekran
    // görüntüleri OTOMATİK dönüyordu, saf CSS animasyonuyla; bu redesign
    // manuel kaydırmaya geçerken otomatik oynatmayı unutmuştu, masaüstü
    // ziyaretçiler için "hareketsiz/bozuk" görünüyordu). Aynı eski
    // ritimle (3.4sn/görsel) otomatik ilerliyor; kullanıcı elle
    // kaydırırsa updateActiveFrame zaten currentIndex'i günceller, bir
    // sonraki otomatik adım kaldığı yerden devam eder (eski konuma
    // sıçramaz). prefers-reduced-motion'da otomatik oynatma kapalı.
    var prefersReducedMotion =
      window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (frames.length > 1 && !prefersReducedMotion) {
      // NOT: Element.scrollTo({behavior:'smooth'}) bazı otomasyon/arka
      // plan sekmesi bağlamlarında (compositor'a bağlı) hiç animasyon
      // üretmeyip sessizce hiçbir şey yapmıyor -- bunu canlı testte
      // yakaladık. Güvenilirlik için düz scrollLeft ataması kullanılıyor
      // (anlık geçiş) -- kullanıcının kendi elle kaydırması hâlâ
      // tarayıcının doğal/akıcı davranışıyla çalışıyor, bu sadece
      // OTOMATİK ilerlemeyi etkiliyor.
      setInterval(function () {
        var nextIndex = (currentIndex + 1) % frames.length;
        var frame = frames[nextIndex];
        var hedef = frame.offsetLeft - (scroller.clientWidth - frame.offsetWidth) / 2;
        scroller.scrollLeft = hedef;
        // 'scroll' olayının dispatch'i tarayıcıda asenkron/boyamaya bağlı
        // olabiliyor -- alt yazı/nokta senkronunu 'scroll' olayının
        // ateşlenmesine bel bağlamadan GARANTİYE almak için burada da
        // doğrudan çağrılıyor (ucuz bir işlem, çift çağrılması sorun değil).
        updateActiveFrame();
      }, 3400);
    }
  }

  // ---- SSS akordeon ----
  document.querySelectorAll(".faq-q").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var item = btn.closest(".faq-item");
      var open = item.getAttribute("data-open") === "true";
      item.setAttribute("data-open", open ? "false" : "true");
    });
  });
})();
