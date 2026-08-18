import React from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useDil } from '@/constants/i18n';

// ---------------------------------------------------------------------------
// "YASAL BİLGİLER" SEKMESİ (2026-08-16'da "Yasal Metin" adıyla eklendi)
// ---------------------------------------------------------------------------
// İlk açılışta gösterilen yasal uyarı/sorumluluk reddi metni (bkz.
// disclaimer-gate.tsx) burada da, istediği zaman tekrar okuyabilsin diye
// AYRI bir sekme olarak sunuluyor. İlk açılıştaki zorunlu onay ekranı
// KALDIRILMADI -- bu sekme sadece aynı metne kalıcı bir erişim noktası
// ekliyor (aynı i18n içeriğini kullanıyor, tek kaynak -- constants/i18n.tsx
// disclaimerBaslik/disclaimerMetin -- iki yerde ayrı ayrı metin bakımı
// gerekmiyor).
//
// 2026-08-17 EKLENTİSİ: Play Store, veri toplayan (push token vb.) her
// uygulamadan bir Gizlilik Politikası bekliyor. 5. bir sekme/ikon EKLEMEK
// yerine (kullanıcı tercihi), bu ekrana İKİNCİ bir kart olarak eklendi --
// sekme adı da bu yüzden "Yasal Metin"den "Yasal Bilgiler"e çevrildi.
// Play Console'un istediği DIŞARIDAN erişilebilir URL için AYRICA bir
// Artifact/statik sayfa yayınlandı (bkz. proje notları) -- bu ekran onun
// YERİNE değil, EK bir erişim noktası.
const LACIVERT = '#1E2C4A';
const KART_YUZEY = '#27375A';
const BEYAZ = '#F5F7FA';
const GRI = '#8E9AB8';
const KENAR = '#2E3B5C';

export default function YasalMetinEkrani() {
  const { t } = useDil();

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView contentContainerStyle={styles.scrollIcerik}>
        <Text style={styles.baslikUst}>📜 {t.sekmeYasalMetin}</Text>
        <View style={styles.kart}>
          <Text style={styles.baslik}>{t.disclaimerBaslik}</Text>
          <Text style={styles.metin}>{t.disclaimerMetin}</Text>
        </View>
        <View style={[styles.kart, styles.ikinciKart]}>
          <Text style={styles.baslik}>{t.gizlilikBaslik}</Text>
          <Text style={styles.metin}>{t.gizlilikMetin}</Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: LACIVERT },
  scrollIcerik: { padding: 20, paddingBottom: 60 },
  baslikUst: { color: BEYAZ, fontSize: 20, fontWeight: '800', marginBottom: 16 },
  kart: {
    backgroundColor: KART_YUZEY,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: KENAR,
    padding: 20,
  },
  ikinciKart: { marginTop: 16 },
  baslik: { fontSize: 18, fontWeight: 'bold', marginBottom: 14, color: BEYAZ },
  metin: { fontSize: 14.5, lineHeight: 22, color: GRI },
});
