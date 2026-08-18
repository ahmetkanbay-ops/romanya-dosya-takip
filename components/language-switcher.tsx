import React, { useState } from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { DILLER, useDil } from '@/constants/i18n';

type Varyant = 'acik' | 'koyu';

// 2026-08-16 (kullanıcı isteğiyle YENİDEN TASARLANDI): önceden üç dilin
// hepsi (TR/EN/RO) her zaman yan yana görünüyordu. Artık bir AÇILIR MENÜ --
// sadece o an SEÇİLİ olan dilin bayrağı (uygulama varsayılanı Türkçe olduğu
// için ilk açılışta "🇹🇷" görünür) + altında/yanında altın renkli aşağı
// üçgen ikonu gösteriliyor. Buna dokununca diğer 2 dil seçeneği aşağıya
// doğru açılan küçük bir kutuda beliriyor.
//
// İki varyantı var:
//  - 'acik'  (varsayılan): beyaz zeminli ekranlarda kullanılır
//  - 'koyu'  : lacivert başlık kutusunun İÇİNDE kullanılır (ana ekran,
//              onay ekranı) -- açılır kutunun rengi de koyu zemine göre.
export default function LanguageSwitcher({ varyant = 'acik' }: { varyant?: Varyant }) {
  const { dil, dilDegistir } = useDil();
  const koyu = varyant === 'koyu';
  const [acikMi, setAcikMi] = useState(false);

  const aktifDil = DILLER.find((d) => d.kod === dil) ?? DILLER[0];
  const digerDiller = DILLER.filter((d) => d.kod !== dil);

  return (
    <View style={styles.kapsayici}>
      <TouchableOpacity
        style={[styles.dugme, koyu && styles.dugmeKoyu]}
        onPress={() => setAcikMi((onceki) => !onceki)}
        accessibilityLabel="Dil seçimini aç"
      >
        <Text style={styles.bayrakMetin}>{aktifDil.bayrak}</Text>
        <View style={[styles.ucgen, acikMi && styles.ucgenAcikken]} />
      </TouchableOpacity>

      {acikMi && (
        <View style={[styles.acilirKutu, koyu && styles.acilirKutuKoyu]}>
          {digerDiller.map((d) => (
            <TouchableOpacity
              key={d.kod}
              style={styles.acilirOge}
              onPress={() => {
                dilDegistir(d.kod);
                setAcikMi(false);
              }}
              accessibilityLabel={`Dili ${d.etiket} yap`}
            >
              <Text style={styles.acilirBayrak}>{d.bayrak}</Text>
              <Text style={[styles.acilirMetin, koyu && styles.acilirMetinKoyu]}>{d.etiket}</Text>
            </TouchableOpacity>
          ))}
        </View>
      )}
    </View>
  );
}

// 2026-08-15: koyu lacivert/antrasit + altın temasına geçirildi (bkz.
// app/(tabs)/index.tsx üstündeki tasarım notu) -- ana ekranla BİREBİR aynı.
const LACIVERT = '#1E2C4A';
const KART_YUZEY = '#27375A';
const ALTIN = '#E3A83B';
const KENAR = '#2E3B5C';

const styles = StyleSheet.create({
  // 2026-08-16: açılır kutu üstteki içeriğin üzerine BİNSİN diye (yer
  // kaplayıp başlığı aşağı itmesin diye) position: relative + absolute
  // çocuk kombinasyonu kullanılıyor.
  kapsayici: { position: 'relative', zIndex: 20 },
  dugme: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 5,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#ccc',
    backgroundColor: '#fff',
  },
  dugmeKoyu: {
    backgroundColor: '#0F1B30',
    borderColor: 'rgba(255,255,255,0.18)',
  },
  bayrakMetin: { fontSize: 17 },
  // Aşağı bakan, içi altın sarısı ile dolgulu üçgen -- klasik "border
  // triangle" tekniği: genişlik/yükseklik 0, sadece üst kenar renkli.
  ucgen: {
    width: 0,
    height: 0,
    borderLeftWidth: 5,
    borderRightWidth: 5,
    borderTopWidth: 6,
    borderLeftColor: 'transparent',
    borderRightColor: 'transparent',
    borderTopColor: ALTIN,
  },
  // Açıkken üçgen yukarı dönsün -- "menü açık" hissi versin.
  ucgenAcikken: {
    transform: [{ rotate: '180deg' }],
  },
  acilirKutu: {
    position: 'absolute',
    top: '100%',
    left: 0,
    marginTop: 6,
    backgroundColor: '#fff',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#ccc',
    paddingVertical: 4,
    minWidth: 96,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.25,
    shadowRadius: 6,
    elevation: 8,
  },
  acilirKutuKoyu: {
    backgroundColor: KART_YUZEY,
    borderColor: KENAR,
  },
  acilirOge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 12,
    paddingVertical: 9,
  },
  acilirBayrak: { fontSize: 16 },
  acilirMetin: { fontSize: 13, fontWeight: '700', color: '#333' },
  acilirMetinKoyu: { color: '#fff' },
});
