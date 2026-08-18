import React from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import Svg, { Circle, G, Line, Rect } from 'react-native-svg';

// ---------------------------------------------------------------------------
// 2026-08-16: İstatistikler sekmesi için hafif, elle çizilmiş SVG grafikler.
// react-native-svg zaten projede kurulu (Expo Go ile tam uyumlu, ekstra
// native kurulum gerektirmiyor) -- bu yüzden react-native-chart-kit/victory
// gibi ağır ek kütüphaneler yerine burada iki basit, bağımsız bileşen
// yazıldı: DonutGrafik ve YillikCubukGrafik.

const BEYAZ = '#F5F7FA';
const GRI = '#8E9AB8';

/** Basit 2 dilimli donut (halka) grafik -- "onaylanan / bekleyen" gibi oranlar için. */
export function DonutGrafik({
  onaylanan,
  bekleyen,
  renkOnay,
  renkBekleyen,
  boyut = 160,
}: {
  onaylanan: number;
  bekleyen: number;
  renkOnay: string;
  renkBekleyen: string;
  boyut?: number;
}) {
  const toplam = onaylanan + bekleyen;
  const yaricap = boyut / 2 - 14;
  const merkez = boyut / 2;
  const cevre = 2 * Math.PI * yaricap;
  const onayOrani = toplam > 0 ? onaylanan / toplam : 0;
  const onayUzunluk = cevre * onayOrani;

  return (
    <View style={{ alignItems: 'center' }}>
      <Svg width={boyut} height={boyut}>
        <G rotation={-90} originX={merkez} originY={merkez}>
          {/* arka halka (bekleyen) */}
          <Circle
            cx={merkez}
            cy={merkez}
            r={yaricap}
            stroke={renkBekleyen}
            strokeWidth={16}
            fill="none"
          />
          {/* on halka (onaylanan) -- sadece kendi oranı kadar cizgi */}
          {onayUzunluk > 0 && (
            <Circle
              cx={merkez}
              cy={merkez}
              r={yaricap}
              stroke={renkOnay}
              strokeWidth={16}
              fill="none"
              strokeDasharray={`${onayUzunluk}, ${cevre}`}
              strokeLinecap="butt"
            />
          )}
        </G>
      </Svg>
      <View style={StyleSheet.absoluteFillObject as any}>
        <View style={styles.donutMerkezIcerik}>
          <Text style={styles.donutYuzde}>{toplam > 0 ? `%${Math.round(onayOrani * 100)}` : '—'}</Text>
          <Text style={styles.donutAltMetin}>onaylandı</Text>
        </View>
      </View>
    </View>
  );
}

/**
 * Yıllara göre stadiu/ordine sayılarını yan yana çubuklarla gösteren, yatay
 * kaydırmalı grafik.
 *
 * 2026-08-16 (kullanıcı geri bildirimi -- 2 düzeltme):
 * (1) Kaydırılabilir olduğu belli değildi -- üstüne açık bir "◀ kaydırın ▶"
 *     ipucu eklendi, ayrıca son sütun kasıtlı olarak yarım kesiliyor (görünür
 *     alanın sığmadığını, devamı olduğunu HİSSETTİRMEK için -- paddingRight
 *     ile).
 * (2) Yıl etiketleri sadece son 2 hane gösteriyordu ("10" gibi, anlaşılır
 *     değildi) -- artık tam yıl ("2010") gösteriliyor, sütun biraz
 *     genişletildi ki sığsın.
 */
export function YillikCubukGrafik({
  veri,
  renkStadiu,
  renkOrdine,
}: {
  veri: { yil: string; stadiu: number; ordine: number }[];
  renkStadiu: string;
  renkOrdine: string;
}) {
  if (!veri || veri.length === 0) return null;
  const maksimum = Math.max(...veri.map((v) => Math.max(v.stadiu, v.ordine)), 1);
  const YUKSEKLIK = 140;
  const CUBUK_GENISLIK = 10;
  const GRUP_GENISLIK = 56;

  return (
    <View>
      <View style={styles.kaydirmaIpucu}>
        <Text style={styles.kaydirmaIpucuMetin}>◀ {'  '}kaydırarak tüm yılları görün{'  '} ▶</Text>
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={true} style={{ marginTop: 6 }}>
        <View style={{ flexDirection: 'row', alignItems: 'flex-end', paddingHorizontal: 8, paddingRight: 28 }}>
          {veri.map((v) => {
            const stadiuYukseklik = (v.stadiu / maksimum) * YUKSEKLIK;
            const ordineYukseklik = (v.ordine / maksimum) * YUKSEKLIK;
            return (
              <View key={v.yil} style={{ width: GRUP_GENISLIK, alignItems: 'center' }}>
                <Svg width={GRUP_GENISLIK} height={YUKSEKLIK}>
                  <Rect
                    x={GRUP_GENISLIK / 2 - CUBUK_GENISLIK - 2}
                    y={YUKSEKLIK - stadiuYukseklik}
                    width={CUBUK_GENISLIK}
                    height={stadiuYukseklik}
                    rx={3}
                    fill={renkStadiu}
                  />
                  <Rect
                    x={GRUP_GENISLIK / 2 + 2}
                    y={YUKSEKLIK - ordineYukseklik}
                    width={CUBUK_GENISLIK}
                    height={ordineYukseklik}
                    rx={3}
                    fill={renkOrdine}
                  />
                  <Line x1={0} y1={YUKSEKLIK} x2={GRUP_GENISLIK} y2={YUKSEKLIK} stroke={GRI} strokeWidth={0.5} />
                </Svg>
                <Text style={styles.cubukYilEtiket}>{v.yil}</Text>
              </View>
            );
          })}
        </View>
      </ScrollView>
    </View>
  );
}

/**
 * "Önünüzde X kişi -- SİZ -- arkanızda Y kişi" şeklinde yatay sıra göstergesi.
 *
 * 2026-08-16 (kullanıcı geri bildirimi): önceki sürüm sadece renkli bir
 * çizgi ve nokta gösteriyordu, ne ifade ettiği hiç yazmıyordu. Artık uç
 * etiketleri ("1" / toplam sayı), "SİZ" işaretçisi üstünde net bir etiket
 * ve altında renklerin ne anlama geldiğini açıklayan bir lejant var.
 */
export function SiraGostergesi({
  sira,
  toplam,
  renk,
  renkArkaPlan,
}: {
  sira: number;
  toplam: number;
  renk: string;
  renkArkaPlan: string;
}) {
  const GENISLIK = 280;
  const oran = toplam > 0 ? (sira - 1) / toplam : 0;
  const isaretciX = Math.min(Math.max(oran * GENISLIK, 6), GENISLIK - 6);

  return (
    <View style={{ alignItems: 'center', marginVertical: 4, width: GENISLIK }}>
      <Text style={[styles.siraEtiketMetin, { color: renk }]}>📍 Siz: {sira}. sıra</Text>
      <Svg width={GENISLIK} height={26}>
        <Line x1={0} y1={13} x2={GENISLIK} y2={13} stroke={renkArkaPlan} strokeWidth={5} strokeLinecap="round" />
        <Line x1={0} y1={13} x2={isaretciX} y2={13} stroke={renk} strokeWidth={5} strokeLinecap="round" />
        <Circle cx={isaretciX} cy={13} r={8} fill={renk} stroke={BEYAZ} strokeWidth={2} />
      </Svg>
      <View style={styles.siraUcEtiketSatiri}>
        <Text style={styles.siraUcEtiketMetin}>1 (ilk sırada bekleyen)</Text>
        <Text style={styles.siraUcEtiketMetin}>{toplam} (son sırada bekleyen)</Text>
      </View>
      <View style={styles.siraLejantSatiri}>
        <View style={styles.siraLejantOge}>
          <View style={[styles.siraLejantNokta, { backgroundColor: renk }]} />
          <Text style={styles.siraLejantMetin}>Önünüzdeki başvurular</Text>
        </View>
        <View style={styles.siraLejantOge}>
          <View style={[styles.siraLejantNokta, { backgroundColor: renkArkaPlan }]} />
          <Text style={styles.siraLejantMetin}>Sizden sonraki başvurular</Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  donutMerkezIcerik: {
    ...StyleSheet.absoluteFillObject,
    alignItems: 'center',
    justifyContent: 'center',
  },
  donutYuzde: { color: BEYAZ, fontSize: 22, fontWeight: '800' },
  donutAltMetin: { color: GRI, fontSize: 11, marginTop: 2 },
  cubukYilEtiket: { color: GRI, fontSize: 9.5, marginTop: 4, fontWeight: '600' },
  kaydirmaIpucu: {
    alignSelf: 'center',
    backgroundColor: 'rgba(227, 168, 59, 0.12)',
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  kaydirmaIpucuMetin: { color: '#E3A83B', fontSize: 11, fontWeight: '700' },
  siraEtiketMetin: { fontSize: 13, fontWeight: '800', marginBottom: 6 },
  siraUcEtiketSatiri: {
    flexDirection: 'row', justifyContent: 'space-between', width: '100%', marginTop: 6,
  },
  siraUcEtiketMetin: { color: GRI, fontSize: 9.5, maxWidth: 110 },
  siraLejantSatiri: { flexDirection: 'row', gap: 16, marginTop: 10 },
  siraLejantOge: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  siraLejantNokta: { width: 9, height: 9, borderRadius: 5 },
  siraLejantMetin: { color: GRI, fontSize: 11 },
});
