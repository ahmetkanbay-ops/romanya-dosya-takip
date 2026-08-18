import React, { useEffect, useMemo, useRef } from 'react';
import { Animated, StyleSheet, View } from 'react-native';
import Svg, { Circle } from 'react-native-svg';

// Başlığın alt kenarında beliren "erime" geçişi.
//
// 2026-08-15 -- BEŞİNCİ revizyon (kullanıcı geri bildirimi): dördüncü
// sürümde, hero kutusuyla kesintisiz birleşsin diye eklenen ince DOLU
// ŞERİT (Rect), noktaların tam üstünde matematiksel olarak DÜZ bir çizgi
// oluşturuyordu -- kullanıcı "geçiş düz bir çizgiyle başlamasın, doğal
// olsun" dedi, haklı: o şerit tam olarak istenmeyen düz çizgiydi.
//
// O şerit TAMAMEN kaldırıldı. Bunun yerine EN ÜST SIRADAKİ noktalar
// bilerek BÜYÜK ve BİRBİRİNE DEĞECEK/ÖRTÜŞECEK kadar SIK -- iç içe geçen
// daireler, kenarı matematiksel değil organik/düzensiz (kabarcıklı) yapan
// doğal bir doku oluşturuyor. Aşağı indikçe hem yarıçap hem sıklık azalıp
// aralık açılıyor, renk de lacivertten sayfa zeminine doğru karışıyor --
// sonuç: dalga/çizgi şekli değil, saf ve doğal bir doku/renk geçişi.
//
// Bu bileşen zümrüt/lacivert kutunun İÇİNDE değil, kutunun HEMEN ALTINDA
// (sayfa zemini üzerinde, kutuya bitişik) render edilmeli (bkz.
// app/(tabs)/index.tsx kullanımı: renkler={[LACIVERT, ZEMIN]}).
//
// 2026-08-15 -- YEDİNCİ revizyon (kullanıcı: "sürekli eriyormuş gibi,
// hareketli olsun"): durağan nokta dokusunun (yukarıdaki) üzerine, yavaşça
// aşağı süzülüp kaybolan (ve tekrar başa dönen) küçük hareketli noktalar
// bindirildi -- confetti.tsx / (kaldırılan) veri-akisi.tsx ile AYNI
// `Animated` tekniği (native driver, döngüsel). Kullanıcının isteğiyle
// hero kutusundaki ayrı "veri akışı" çizgileri KALDIRILDI, hareket artık
// tek yerde (burada) toplanıyor.

const VARSAYILAN_RENKLER = ['#0B2A6B', '#F4F6FB'];

// Normalize edilmiş koordinat uzayı -- gerçek piksel genişlik/yüksekliğe
// bakılmaksızın burada sabit birimlerle çalışıyoruz, SVG viewBox +
// preserveAspectRatio="none" gerçek ölçüye esnetiyor.
const VB_GENISLIK = 390;
const VB_YUKSEKLIK = 100;

// 2026-08-15 (sekizinci revizyon): satır bazlı yapı TAMAMEN kaldırıldı --
// hem satırların kendisi hafif bir "bant" izlenimi verebiliyordu hem de
// üst sınırdaki dikiş yeri kullanıcıya hâlâ belli oluyordu. Yerine gerçek
// bir "yarım ton / stipple" dağılımı geldi: SABİT SAYIDA çok küçük nokta,
// dikey konumları y=0'a (kartın dibi) DOĞRU ÜSTEL OLARAK YIĞILACAK şekilde
// rastgele üretiliyor (bkz. YOGUNLUK_USSU). Sonuç: y=0 civarında binlerce
// nokta üst üste yığılıp neredeyse dolu görünüyor (kartla dikişsiz
// birleşiyor), aşağı indikçe seyrekleşerek zemine karışıyor -- HER ZAMAN
// küçük noktalarla, satır/bant izi olmadan, tamamen rastgele/organik.
const TOPLAM_NOKTA = 950;
const YOGUNLUK_USSU = 3.6; // >1 ne kadar büyükse üstteki yığılma o kadar güçlü

function ikiliRenge(hex: string): [number, number, number] {
  const h = hex.replace('#', '');
  return [parseInt(h.substring(0, 2), 16), parseInt(h.substring(2, 4), 16), parseInt(h.substring(4, 6), 16)];
}

function renkKaristir(ustHex: string, altHex: string, t: number): string {
  const [r1, g1, b1] = ikiliRenge(ustHex);
  const [r2, g2, b2] = ikiliRenge(altHex);
  const r = Math.round(r1 + (r2 - r1) * t);
  const g = Math.round(g1 + (g2 - g1) * t);
  const b = Math.round(b1 + (b2 - b1) * t);
  return `rgb(${r}, ${g}, ${b})`;
}

type Nokta = { x: number; y: number; r: number; renk: string; opaklik: number };

function noktalariUret(ustRenk: string, altRenk: string): Nokta[] {
  const noktalar: Nokta[] = [];
  for (let i = 0; i < TOPLAM_NOKTA; i++) {
    // Math.random() üssü alınarak y=0'a yığılan bir dağılım elde ediliyor
    // -- düz/eşit dağılım DEĞİL, kartın dibinde çok daha sık.
    const y = VB_YUKSEKLIK * Math.pow(Math.random(), YOGUNLUK_USSU);
    const ilerleme = y / VB_YUKSEKLIK; // 0 (üst/lacivert) -> 1 (alt/zemin)
    const x = Math.random() * VB_GENISLIK;
    const karisim = Math.min(1, Math.max(0, ilerleme + (Math.random() - 0.5) * 0.15));
    noktalar.push({
      x,
      y,
      r: 0.6 + Math.random() * 1.1, // HER ZAMAN küçük/piksel boyutunda
      renk: renkKaristir(ustRenk, altRenk, karisim),
      opaklik: Math.max(0.4, 1 - ilerleme * 0.35 + Math.random() * 0.1),
    });
  }
  return noktalar;
}

// ---------------------------------------------------------------------------
// Hareketli katman: durağan SVG dokusunun ÜZERİNE, yavaşça aşağı süzülüp
// kaybolan (sonra başa dönüp tekrar başlayan) küçük noktalar bindirilir --
// "sürekli eriyormuş" hissi bunlardan geliyor. confetti.tsx ile aynı teknik
// (React Native Animated, native driver, döngüsel) -- SVG değil, düz
// View'lar kullanılıyor çünkü react-native-svg'nin AnimatedCircle'ı native
// driver'la çalışmıyor (JS thread'de onlarca nokta animasyonu performans
// sorunu yaratabilirdi); az sayıda (bkz. AKAN_NOKTA_SAYISI) düz View ile
// bu risk yok.
const AKAN_NOKTA_SAYISI = 22;

type AkanNokta = {
  xYuzde: number;
  baslangicY: number;
  dususMesafesi: number;
  boyut: number;
  renk: string;
  sure: number;
  gecikme: number;
};

function akanNoktalariUret(yukseklik: number, ustRenk: string, altRenk: string): AkanNokta[] {
  return Array.from({ length: AKAN_NOKTA_SAYISI }, () => {
    // Üst yarıya yakın bir yerden "kopup" aşağı süzülüyor -- tamamen
    // rastgele her yükseklikten başlamıyor, dokunun daha yoğun/üst
    // kısmından kopan parçacıklar gibi.
    const baslangicY = Math.random() * yukseklik * 0.5;
    const karisim = Math.min(1, baslangicY / yukseklik + Math.random() * 0.15);
    return {
      xYuzde: Math.random(),
      baslangicY,
      dususMesafesi: yukseklik * (0.35 + Math.random() * 0.55),
      boyut: 1 + Math.random() * 1.8,
      renk: renkKaristir(ustRenk, altRenk, karisim),
      sure: 2800 + Math.random() * 2800,
      gecikme: Math.random() * 2800,
    };
  });
}

function AkanNoktaParcasi({ nokta }: { nokta: AkanNokta }) {
  const ilerleme = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const dongu = Animated.loop(
      Animated.sequence([
        Animated.delay(nokta.gecikme),
        Animated.timing(ilerleme, { toValue: 1, duration: nokta.sure, useNativeDriver: true }),
        Animated.timing(ilerleme, { toValue: 0, duration: 0, useNativeDriver: true }),
      ])
    );
    dongu.start();
    return () => dongu.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const translateY = ilerleme.interpolate({ inputRange: [0, 1], outputRange: [0, nokta.dususMesafesi] });
  const opacity = ilerleme.interpolate({ inputRange: [0, 0.12, 0.7, 1], outputRange: [0, 0.9, 0.5, 0] });

  return (
    <Animated.View
      style={{
        position: 'absolute',
        left: `${nokta.xYuzde * 100}%`,
        top: nokta.baslangicY,
        width: nokta.boyut,
        height: nokta.boyut,
        borderRadius: nokta.boyut / 2,
        backgroundColor: nokta.renk,
        opacity,
        transform: [{ translateY }],
      }}
    />
  );
}

export default function PikselErimesi({
  yukseklik = 100,
  renkler = VARSAYILAN_RENKLER,
}: {
  yukseklik?: number;
  renkler?: string[];
}) {
  const ustRenk = renkler[0] ?? VARSAYILAN_RENKLER[0];
  const altRenk = renkler[1] ?? VARSAYILAN_RENKLER[1];
  const noktalar = useMemo(() => noktalariUret(ustRenk, altRenk), [ustRenk, altRenk]);
  const akanNoktalar = useMemo(
    () => akanNoktalariUret(yukseklik, ustRenk, altRenk),
    [yukseklik, ustRenk, altRenk]
  );

  return (
    <View style={[styles.kap, { height: yukseklik }]} pointerEvents="none">
      <Svg width="100%" height="100%" viewBox={`0 0 ${VB_GENISLIK} ${VB_YUKSEKLIK}`} preserveAspectRatio="none">
        {noktalar.map((n, i) => (
          <Circle key={i} cx={n.x} cy={n.y} r={n.r} fill={n.renk} opacity={n.opaklik} />
        ))}
      </Svg>
      {akanNoktalar.map((n, i) => (
        <AkanNoktaParcasi key={i} nokta={n} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  kap: { width: '100%' },
});
