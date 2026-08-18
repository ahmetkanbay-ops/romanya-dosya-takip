import React from 'react';
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useDil } from '@/constants/i18n';

// 2026-08-18 EKLENTİSİ (kullanıcı isteği): "kullanıcılar uygulamanın bütün
// özelliklerini bilmeleri çok güzel olur" -- Ana Sayfa'daki küçük bilgi (i)
// ikonuna basınca açılan, uygulamanın kullanıcılara sunduğu hizmetleri
// (sorgulama, otomatik bildirim, favoriler, istatistikler vb.) tek bir
// yerde özetleyen sayfa. İçerik constants/i18n.tsx'te 3 dilli (TR/EN/RO)
// tutuluyor -- bkz. t.ozellikler dizisi.
//
// 2026-08-18 (kullanıcı geri bildirimi -- "açılışta beyaz ekran" teşhisi
// sırasında öğrenilen ders): Android'de RN'in <Modal> bileşeni kendi ayrı
// native penceresini açıyor, içerik çizilmeden önce kısa süreli varsayılan
// beyaz pencere zemini gösterebiliyor. Bu risk burada (uygulama açılışıyla
// yarışmadığı için) çok daha düşük olsa da, disclaimer-gate.tsx'te
// kanıtlanmış aynı güvenli deseni (Modal yerine normal absolute-overlay
// View) burada da kullanmak tutarlılık ve garanti sağlıyor.
const LACIVERT = '#1E2C4A';
const KART_YUZEY = '#27375A';
const ALTIN = '#E3A83B';
const BEYAZ = '#F5F7FA';
const GRI = '#8E9AB8';
const KENAR = '#2E3B5C';

export default function OzelliklerModal({
  gorunur,
  kapat,
}: {
  gorunur: boolean;
  kapat: () => void;
}) {
  const { t } = useDil();

  if (!gorunur) return null;

  return (
    <View style={[StyleSheet.absoluteFill, styles.disKapsayici]}>
      <View style={styles.hero}>
        <Text style={styles.heroBaslik}>{t.ozelliklerBaslik}</Text>
        <TouchableOpacity style={styles.kapatButon} onPress={kapat} hitSlop={12}>
          <Text style={styles.kapatMetin}>✕</Text>
        </TouchableOpacity>
      </View>
      <View style={styles.kart}>
        <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
          <Text style={styles.aciklama}>{t.ozelliklerAciklama}</Text>
          {t.ozellikler.map((ozellik, index) => (
            <View key={index} style={styles.satir}>
              <Text style={styles.ikon}>{ozellik.ikon}</Text>
              <View style={styles.satirMetin}>
                <Text style={styles.satirBaslik}>{ozellik.baslik}</Text>
                <Text style={styles.satirAciklama}>{ozellik.aciklama}</Text>
              </View>
            </View>
          ))}
        </ScrollView>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  // 2026-08-18 (kullanıcı geri bildirimi -- ekran görüntüsüyle bildirdi):
  // Ana ekranın başlığındaki dil seçici (zIndex:20) ve bilgi ikonu
  // (zIndex:10), bu modalın kendisi bir zIndex tanımlamadığı için
  // modalın ÜSTÜNE sızıyordu -- kapatma butonuyla iç içe geçmiş
  // görünüyorlardı. React Native'de bir kardeş zIndex tanımladığında,
  // SIRALAMA artık salt JSX/mount sırasına değil zIndex değerine göre
  // belirleniyor -- bu yüzden modalın kendi zIndex'i o değerlerin
  // hepsinden yüksek olmalı.
  disKapsayici: { flex: 1, backgroundColor: LACIVERT, zIndex: 1000, elevation: 1000 },
  hero: {
    backgroundColor: LACIVERT,
    paddingTop: 54,
    paddingHorizontal: 20,
    paddingBottom: 20,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  heroBaslik: { fontSize: 19, fontWeight: 'bold', color: '#fff' },
  kapatButon: {
    position: 'absolute',
    top: 50,
    right: 16,
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: KART_YUZEY,
    alignItems: 'center',
    justifyContent: 'center',
  },
  kapatMetin: { color: BEYAZ, fontSize: 16, fontWeight: 'bold' },
  kart: {
    flex: 1,
    backgroundColor: KART_YUZEY,
    borderRadius: 18,
    marginHorizontal: 16,
    marginTop: 18,
    marginBottom: 20,
    paddingHorizontal: 20,
    paddingTop: 20,
    borderWidth: 1,
    borderColor: KENAR,
    overflow: 'hidden',
  },
  scroll: { paddingBottom: 20 },
  aciklama: { fontSize: 15, lineHeight: 22, color: GRI, marginBottom: 18 },
  satir: { flexDirection: 'row', gap: 14, marginBottom: 20, alignItems: 'flex-start' },
  ikon: { fontSize: 26, width: 34, textAlign: 'center' },
  satirMetin: { flex: 1 },
  satirBaslik: { fontSize: 16, fontWeight: 'bold', color: BEYAZ, marginBottom: 4 },
  satirAciklama: { fontSize: 14, lineHeight: 20, color: GRI },
});
