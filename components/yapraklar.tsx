import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Animated, StyleSheet, View } from 'react-native';

// Mavi başlık kutusunun TAMAMINI kaplayan, en yukarıdan aşağıya doğru
// sürekli süzülen küçük noktalar -- "ağaçtan dökülen yapraklar gibi"
// (kullanıcının 2026-08-15 tarifi). Kartın kendisinin İÇİNDE, metnin
// (başlık/slogan/dil pili) HEMEN ARKASINDA render edilmeli ki hem kartın
// tamamı noktalı görünsün hem de yazılar bozulmasın (bkz. app/(tabs)/
// index.tsx kullanımı -- Svg gradyanının hemen ardından, metin
// bileşenlerinden ÖNCE eklenir).
//
// confetti.tsx / piksel-erime.tsx'teki "akan nokta" ile AYNI teknik
// (React Native Animated, native driver, döngüsel) -- burada tek fark,
// noktaların kartın TAMAMI boyunca (üstten dibe) düşmesi ve metnin
// okunabilirliğini bozmaması için az sayıda + düşük opaklıkta olması.

const YAPRAK_SAYISI = 22;
// 2026-08-15: koyu lacivert/antrasit + altın temasıyla tutarlı --
// altın + soluk gri-beyaz, dönüşümlü (eski soluk mavi kaldırıldı).
const RENKLER = ['#E3A83B', '#C7CEE0'];

type Yaprak = {
  xYuzde: number;
  boyut: number;
  renk: string;
  sure: number;
  gecikme: number;
  maksOpaklik: number;
};

function yapraklariUret(): Yaprak[] {
  return Array.from({ length: YAPRAK_SAYISI }, (_, i) => ({
    xYuzde: Math.random(),
    boyut: 1.2 + Math.random() * 2,
    renk: RENKLER[i % 2],
    sure: 4200 + Math.random() * 4200,
    gecikme: Math.random() * 5000,
    // Metnin okunabilirliğini bozmasın diye HER ZAMAN düşük/orta opaklık.
    maksOpaklik: 0.28 + Math.random() * 0.22,
  }));
}

function YaprakParcasi({ yaprak, yukseklik }: { yaprak: Yaprak; yukseklik: number }) {
  const ilerleme = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const dongu = Animated.loop(
      Animated.sequence([
        Animated.delay(yaprak.gecikme),
        Animated.timing(ilerleme, { toValue: 1, duration: yaprak.sure, useNativeDriver: true }),
        Animated.timing(ilerleme, { toValue: 0, duration: 0, useNativeDriver: true }),
      ])
    );
    dongu.start();
    return () => dongu.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // En üstten (kartın hemen dibinden değil, tepesinden) başlayıp kartın
  // dibine kadar süzülüyor -- "en yukarıdan aşağıya doğru aksın" isteğiyle
  // birebir.
  const translateY = ilerleme.interpolate({
    inputRange: [0, 1],
    outputRange: [-yaprak.boyut * 2, yukseklik + yaprak.boyut * 2],
  });
  // Hafif sağa-sola savrulma -- gerçek bir yaprağın düşüşü gibi, dümdüz
  // bir çizgi halinde inmesin.
  const translateX = ilerleme.interpolate({
    inputRange: [0, 0.25, 0.5, 0.75, 1],
    outputRange: [0, 4, -3, 4, 0],
  });
  const opacity = ilerleme.interpolate({
    inputRange: [0, 0.1, 0.85, 1],
    outputRange: [0, yaprak.maksOpaklik, yaprak.maksOpaklik, 0],
  });

  return (
    <Animated.View
      style={{
        position: 'absolute',
        left: `${yaprak.xYuzde * 100}%`,
        top: 0,
        width: yaprak.boyut,
        height: yaprak.boyut,
        borderRadius: yaprak.boyut / 2,
        backgroundColor: yaprak.renk,
        opacity,
        transform: [{ translateY }, { translateX }],
      }}
    />
  );
}

export default function Yapraklar() {
  const [yukseklik, setYukseklik] = useState(0);
  const yapraklar = useMemo(() => yapraklariUret(), []);

  return (
    <View
      // 2026-08-16: "overflow: hidden" artık burada, kartın kendisinde
      // (heroKart) DEĞİL -- kart üstündeki dil seçici açılır menüsünün
      // (bkz. language-switcher.tsx) kart sınırının dışına taşarak
      // görünebilmesi gerekiyordu, ama bu yaprak parçacıklarının kart
      // kenarlarından "temiz kesilmesi" için hâlâ bir kırpma katmanı
      // lazımdı -- bu View kartla birebir aynı boyutta olduğu için
      // kendi üstünde kırpma yapmak görsel olarak aynı sonucu veriyor.
      style={[StyleSheet.absoluteFillObject, { overflow: 'hidden' }]}
      pointerEvents="none"
      onLayout={(e) => setYukseklik(e.nativeEvent.layout.height)}
    >
      {yukseklik > 0 &&
        yapraklar.map((y, i) => <YaprakParcasi key={i} yaprak={y} yukseklik={yukseklik} />)}
    </View>
  );
}
