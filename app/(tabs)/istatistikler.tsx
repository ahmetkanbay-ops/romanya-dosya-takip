import React, { useEffect, useState } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TextInput,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { apiIstek } from '@/constants/api';
import { useDil } from '@/constants/i18n';
import { DonutGrafik, YillikCubukGrafik, SiraGostergesi } from '@/components/istatistik-grafikleri';

// ---------------------------------------------------------------------------
// İSTATİSTİKLER SEKMESİ (2026-08-16, kullanıcı isteğiyle eklendi)
// ---------------------------------------------------------------------------
// İki bölüm: (1) Kişisel yıl istatistiği -- dosya no + yıl girilince, o yılki
// toplam başvuru/onay sayıları ve kullanıcının TAHMİNİ sırası gösterilir.
// (2) Genel istatistik -- tüm sistemdeki toplam sayılar, ekran açılır
// açılmaz otomatik yüklenir.
//
// ÖNEMLİ (dürüstlük): "sıra" bilgisi resmi bir kuyruk numarası DEĞİLDİR --
// dosya numaralarının o yıl içinde artan sırada verildiği varsayımıyla
// hesaplanan bir TAHMİNDİR (bkz. backend/main.py istatistikler_kisisel
// notu). Bu ekranda her zaman açıkça belirtiliyor.
//
// Bu ekran deneysel-arama.tsx ile aynı prensiple index.tsx'ten bağımsız
// yazıldı -- kendi state'i, kendi stilleri var, ana akışa dokunmuyor.

const LACIVERT = '#1E2C4A';
const KART_YUZEY = '#27375A';
const ALTIN = '#E3A83B';
const BEYAZ = '#F5F7FA';
const GRI = '#8E9AB8';
const YESIL_INDIR = '#1E7A4C';
const KENAR = '#2E3B5C';
const KIRMIZI = '#D64545';

export default function IstatistiklerEkrani() {
  const { t } = useDil();

  // --- Kişisel yıl istatistiği ---
  const [dosyaNo, setDosyaNo] = useState('');
  const [yil, setYil] = useState('');
  const [kisiselYukleniyor, setKisiselYukleniyor] = useState(false);
  const [kisiselHata, setKisiselHata] = useState('');
  const [kisiselSonuc, setKisiselSonuc] = useState<any | null>(null);

  const kisiselSorgula = async () => {
    if (!dosyaNo.trim() || !yil.trim()) {
      setKisiselHata(t.istatistikKisiselEksikAlan);
      return;
    }
    setKisiselHata('');
    setKisiselYukleniyor(true);
    setKisiselSonuc(null);
    try {
      const response = await apiIstek('/api/istatistikler/kisisel', {
        method: 'POST',
        body: JSON.stringify({ dosya_no: dosyaNo.trim(), yil: yil.trim() }),
      });
      const data = await response.json();
      setKisiselSonuc(data);
    } catch {
      setKisiselHata(t.hataBaglanti);
    } finally {
      setKisiselYukleniyor(false);
    }
  };

  // --- Genel istatistik (ekran açılınca otomatik yüklenir) ---
  const [genelYukleniyor, setGenelYukleniyor] = useState(true);
  const [genelHata, setGenelHata] = useState('');
  const [genelSonuc, setGenelSonuc] = useState<any | null>(null);

  const genelVeriyiYukle = async () => {
    setGenelYukleniyor(true);
    setGenelHata('');
    try {
      const response = await apiIstek('/api/istatistikler/genel');
      const data = await response.json();
      setGenelSonuc(data);
    } catch {
      setGenelHata(t.hataBaglanti);
    } finally {
      setGenelYukleniyor(false);
    }
  };

  useEffect(() => {
    genelVeriyiYukle();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={styles.scrollIcerik} keyboardShouldPersistTaps="handled">
          <Text style={styles.baslik}>📊 {t.istatistikBaslik}</Text>

          {/* ================= BÖLÜM 1: KİŞİSEL YIL İSTATİSTİĞİ ================= */}
          <View style={styles.bolumKutu}>
            <Text style={styles.bolumBaslik}>{t.istatistikKisiselBaslik}</Text>
            <Text style={styles.bolumAciklama}>{t.istatistikKisiselAciklama}</Text>

            <View style={styles.satirGiris}>
              <TextInput
                style={[styles.girisAlani, { flex: 1.4 }]}
                placeholder={t.dosyaNoOrnek}
                placeholderTextColor={GRI}
                value={dosyaNo}
                onChangeText={setDosyaNo}
                keyboardType="numbers-and-punctuation"
              />
              <TextInput
                style={[styles.girisAlani, { flex: 1 }]}
                placeholder={t.yilOrnek}
                placeholderTextColor={GRI}
                value={yil}
                onChangeText={setYil}
                keyboardType="number-pad"
                maxLength={4}
              />
            </View>
            {kisiselHata ? <Text style={styles.hataMetin}>{kisiselHata}</Text> : null}
            <TouchableOpacity style={styles.gorüntuleButon} onPress={kisiselSorgula} disabled={kisiselYukleniyor}>
              {kisiselYukleniyor ? (
                <ActivityIndicator color={LACIVERT} />
              ) : (
                <Text style={styles.gorüntuleButonMetin}>{t.istatistikGoruntuleButon}</Text>
              )}
            </TouchableOpacity>

            {kisiselSonuc && kisiselSonuc.gecerli === false && (
              <Text style={styles.hataMetin}>{t.istatistikKisiselEksikAlan}</Text>
            )}

            {kisiselSonuc && kisiselSonuc.gecerli && (
              <View style={styles.sonucIcerik}>
                {kisiselSonuc.durum === 'bulunamadi' && (
                  <Text style={styles.durumMetni}>
                    {t.istatistikKisiselBulunamadi.replace('{yil}', kisiselSonuc.yil)}
                  </Text>
                )}
                {kisiselSonuc.durum === 'onaylanmis' && (
                  <Text style={[styles.durumMetni, { color: YESIL_INDIR }]}>
                    {t.istatistikKisiselOnaylanmis.replace('{yil}', kisiselSonuc.yil)}
                  </Text>
                )}
                {kisiselSonuc.durum === 'bekliyor' && (
                  <>
                    <Text style={styles.durumMetni}>
                      {t.istatistikKisiselBekliyor
                        .replace('{yil}', kisiselSonuc.yil)
                        .replace('{sira}', String(kisiselSonuc.sira))
                        .replace('{toplam}', String(kisiselSonuc.toplam_bekleyen))
                        .replace('{kalan}', String(kisiselSonuc.sonrasinda_kalan))}
                    </Text>
                    <SiraGostergesi
                      sira={kisiselSonuc.sira}
                      toplam={kisiselSonuc.toplam_bekleyen}
                      renk={ALTIN}
                      // 2026-08-17 (kullanıcı geri bildirimi): KENAR
                      // (#2E3B5C), kartın kendi arka plan rengine
                      // (#27375A) neredeyse birebir yakın olduğu için
                      // "sizden sonraki başvurular" çizgisi/noktası
                      // ekranda görünmüyordu. GRI (#8E9AB8) -- uygulamada
                      // zaten koyu zeminde okunaklı olduğu kanıtlanmış
                      // renk -- kullanılarak kontrast artırıldı.
                      renkArkaPlan={GRI}
                    />
                    <Text style={styles.tahminUyarisi}>⚠️ {t.istatistikSiraUyarisi}</Text>
                  </>
                )}

                <View style={{ marginTop: 18, alignItems: 'center' }}>
                  <DonutGrafik
                    onaylanan={kisiselSonuc.toplam_ordine}
                    bekleyen={kisiselSonuc.toplam_bekleyen}
                    renkOnay={YESIL_INDIR}
                    renkBekleyen={KENAR}
                  />
                  <Text style={styles.grafikAltYazi}>
                    {kisiselSonuc.yil}: {t.istatistikToplamKabul} {kisiselSonuc.toplam_stadiu} · {t.istatistikToplamOnay} {kisiselSonuc.toplam_ordine}
                  </Text>
                </View>
              </View>
            )}
          </View>

          {/* ================= BÖLÜM 2: GENEL İSTATİSTİK ================= */}
          <View style={styles.bolumKutu}>
            <Text style={styles.bolumBaslik}>{t.istatistikGenelBaslik}</Text>
            <Text style={styles.bolumAciklama}>{t.istatistikGenelAciklama}</Text>

            {genelYukleniyor && <ActivityIndicator color={ALTIN} style={{ marginTop: 16 }} />}
            {genelHata ? <Text style={styles.hataMetin}>{genelHata}</Text> : null}

            {genelSonuc && (
              <View style={styles.sonucIcerik}>
                <View style={{ alignItems: 'center' }}>
                  <DonutGrafik
                    onaylanan={genelSonuc.toplam_onaylanan}
                    bekleyen={genelSonuc.toplam_bekleyen}
                    renkOnay={YESIL_INDIR}
                    renkBekleyen={KENAR}
                    boyut={180}
                  />
                </View>

                <View style={styles.istatistikSatirlari}>
                  <View style={styles.istatistikSatiri}>
                    <Text style={styles.istatistikEtiket}>{t.istatistikToplamKabul}</Text>
                    <Text style={styles.istatistikDeger}>{genelSonuc.toplam_stadiu.toLocaleString('tr-TR')}</Text>
                  </View>
                  <View style={styles.istatistikSatiri}>
                    <Text style={styles.istatistikEtiket}>{t.istatistikToplamOnay}</Text>
                    <Text style={[styles.istatistikDeger, { color: YESIL_INDIR }]}>{genelSonuc.toplam_onaylanan.toLocaleString('tr-TR')}</Text>
                  </View>
                  <View style={styles.istatistikSatiri}>
                    <Text style={styles.istatistikEtiket}>{t.istatistikToplamBekleyen}</Text>
                    <Text style={[styles.istatistikDeger, { color: ALTIN }]}>{genelSonuc.toplam_bekleyen.toLocaleString('tr-TR')}</Text>
                  </View>
                </View>

                <Text style={styles.bolumAltBaslik}>{t.istatistikYillikGrafikBaslik}</Text>
                <YillikCubukGrafik veri={genelSonuc.yillik_dagilim} renkStadiu={ALTIN} renkOrdine={YESIL_INDIR} />
                <View style={styles.grafikLejant}>
                  <View style={styles.lejantSatir}>
                    <View style={[styles.lejantNokta, { backgroundColor: ALTIN }]} />
                    <Text style={styles.lejantMetin}>{t.istatistikToplamKabul}</Text>
                  </View>
                  <View style={styles.lejantSatir}>
                    <View style={[styles.lejantNokta, { backgroundColor: YESIL_INDIR }]} />
                    <Text style={styles.lejantMetin}>{t.istatistikToplamOnay}</Text>
                  </View>
                </View>
              </View>
            )}
          </View>

          <Text style={styles.dipnot}>ℹ️ {t.istatistikGenelDipnot}</Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: LACIVERT },
  scrollIcerik: { padding: 20, paddingBottom: 60 },
  baslik: { color: BEYAZ, fontSize: 20, fontWeight: '800', marginBottom: 16 },
  bolumKutu: {
    backgroundColor: KART_YUZEY, borderRadius: 16, borderWidth: 1, borderColor: KENAR,
    padding: 16, marginBottom: 18,
  },
  bolumBaslik: { color: BEYAZ, fontSize: 16, fontWeight: '800', marginBottom: 6 },
  bolumAltBaslik: { color: BEYAZ, fontSize: 13.5, fontWeight: '700', marginTop: 18, marginBottom: 10 },
  bolumAciklama: { color: GRI, fontSize: 12.5, lineHeight: 18, marginBottom: 14 },
  satirGiris: { flexDirection: 'row', gap: 10, marginBottom: 12 },
  girisAlani: {
    backgroundColor: LACIVERT, borderWidth: 1, borderColor: KENAR, borderRadius: 10,
    paddingHorizontal: 12, paddingVertical: 11, color: BEYAZ, fontSize: 14,
  },
  hataMetin: { color: KIRMIZI, fontSize: 13, marginBottom: 10 },
  gorüntuleButon: { backgroundColor: ALTIN, borderRadius: 10, paddingVertical: 13, alignItems: 'center' },
  gorüntuleButonMetin: { color: LACIVERT, fontWeight: '800', fontSize: 14.5 },
  sonucIcerik: { marginTop: 18 },
  durumMetni: { color: BEYAZ, fontSize: 14.5, lineHeight: 21, textAlign: 'center', fontWeight: '600' },
  tahminUyarisi: { color: GRI, fontSize: 11.5, textAlign: 'center', marginTop: 6, fontStyle: 'italic' },
  grafikAltYazi: { color: GRI, fontSize: 12, marginTop: 10, textAlign: 'center' },
  istatistikSatirlari: { marginTop: 18, gap: 8 },
  istatistikSatiri: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    borderTopWidth: 1, borderTopColor: KENAR, paddingTop: 8,
  },
  istatistikEtiket: { color: GRI, fontSize: 13 },
  istatistikDeger: { color: BEYAZ, fontSize: 15, fontWeight: '800' },
  grafikLejant: { flexDirection: 'row', gap: 16, marginTop: 8, justifyContent: 'center' },
  lejantSatir: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  lejantNokta: { width: 9, height: 9, borderRadius: 5 },
  lejantMetin: { color: GRI, fontSize: 11.5 },
  dipnot: { color: GRI, fontSize: 11, lineHeight: 16, textAlign: 'center', marginTop: 4 },
});
