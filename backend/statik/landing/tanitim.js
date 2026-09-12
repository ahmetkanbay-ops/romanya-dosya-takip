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
      if (captions[closest]) captionEl.textContent = captions[closest];
      Array.from(dotsEl.children).forEach(function (dot, i) {
        dot.className = i === closest ? "on" : "";
      });
    }
    scroller.addEventListener(
      "scroll",
      function () {
        window.requestAnimationFrame(updateActiveFrame);
      },
      { passive: true }
    );
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
