import Constants from 'expo-constants';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { useEffect } from 'react';
import { Platform } from 'react-native';
import { apiIstek, cihazKimligiGetir } from '@/constants/api';

// Uygulama açıldığında: (1) bildirim izni ister, (2) verilirse gerçek bir
// Expo push token'ı alır, (3) bunu backend'e kaydeder (bkz. backend/main.py
// /api/push-token -- endpoint zaten vardı, sadece hiçbir ekran çağırmıyordu).
//
// 2026-08-15: Faz 1.8'de bırakılan yarım iş tamamlandı -- önceden
// favoriler cihaza özel RASTGELE bir kimlik (cihazKimligiGetir) kullanıyordu,
// bu KALMAYA devam ediyor (favorileri eşleştirmek için hâlâ yeterli). Bu
// hook AYRICA, üstüne EK olarak gerçek bir push token kaydediyor ki
// bot.py'nin ürettiği "Tebrikler, onaylandı!" bildirimi gerçekten telefona
// düşebilsin.
//
// ÖNEMLİ: Fiziksel bir cihaz + gerçek bir EAS projectId (app.json'ın
// extra.eas.projectId alanı, "eas login" + "eas init" ile bir kere
// oluşturulur) gerektirir. İkisi de yoksa hook sessizce hiçbir şey
// yapmaz -- geliştirmeyi/diğer özellikleri BOZMAZ.

async function androidKanaliniAyarla() {
  if (Platform.OS !== 'android') return;
  await Notifications.setNotificationChannelAsync('default', {
    name: 'Genel Bildirimler',
    importance: Notifications.AndroidImportance.HIGH,
    vibrationPattern: [0, 250, 250, 250],
    lightColor: '#E3A83B',
  });
}

// 2026-08-18 KRİTİK DÜZELTME (uzun bir teşhis sürecinin sonunda bulundu):
// Expo Notifications, `setNotificationHandler` HİÇ ÇAĞRILMAMIŞSA, uygulama
// ÖN PLANDAYKEN (foreground) gelen bildirimleri VARSAYILAN OLARAK
// GÖSTERMİYOR -- bu, dokümantasyonda açıkça belirtilen bir davranış, "hata"
// değil. Bu projede bu çağrı HİÇ YOKTU, bu yüzden Firebase/FCM kurulumu
// (google-services.json, servis hesabı anahtarı) tamamen doğru olmasına
// rağmen (canlı cihazda adb logcat ile "FirebaseApp initialization
// successful" ve FCM mesajının native tarafa ulaştığı doğrulandı) hiçbir
// test bildirimi GÖRÜNMÜYORDU -- çünkü SIRAYLA yapılan tüm testler
// uygulama açıkken (foreground) yapılmıştı. Bu çağrı, modül import
// edilir edilmez (component/hook'tan bağımsız, EN ÜST SEVİYEDE) bir kere
// çalıştırılmalı -- useEffect içine konursa, ilk render'dan SONRA
// çalışır, bu arada gelen çok erken bir bildirim yine kaçabilir.
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

export function usePushBildirimleri() {
  useEffect(() => {
    (async () => {
      try {
        // Simülatör/emülatörde push token alınamaz -- gerçek cihaz şart.
        if (!Device.isDevice) {
          console.log('ℹ️ Push bildirimleri sadece gerçek cihazda çalışır (simülatör atlandı).');
          return;
        }

        await androidKanaliniAyarla();

        const mevcutIzin = await Notifications.getPermissionsAsync();
        let nihaiDurum = mevcutIzin.status;
        if (nihaiDurum !== 'granted') {
          const istek = await Notifications.requestPermissionsAsync();
          nihaiDurum = istek.status;
        }
        if (nihaiDurum !== 'granted') {
          console.log('ℹ️ Kullanıcı bildirim iznini reddetti.');
          return;
        }

        const projectId =
          Constants.expoConfig?.extra?.eas?.projectId ?? Constants.easConfig?.projectId;
        if (!projectId) {
          // "eas init" henüz çalıştırılmadıysa buraya düşer -- sessizce
          // atlanır, geliştirme akışını bozmaz.
          console.log('ℹ️ EAS projectId bulunamadı -- push token alınamadı (eas init gerekiyor).');
          return;
        }

        const tokenSonucu = await Notifications.getExpoPushTokenAsync({ projectId });
        const token = tokenSonucu.data;

        // 2026-08-17 EKLENTİSİ: cihaz kimliği de gönderiliyor -- backend
        // bunu 'favoriler' tablosundaki (aslında cihaz kimliği tutan,
        // bkz. dosya_utils.py notu) kayıtlarla GERÇEK push token'ı
        // eşleştirmek için kullanıyor (bkz. backend/bot.py
        // _favori_sahiplerini_bul). Bu olmadan "favori onaylandı"
        // bildirimi hiçbir zaman gerçekten ulaşamıyordu.
        const cihazKimligi = await cihazKimligiGetir();

        await apiIstek('/api/push-token', {
          method: 'POST',
          body: JSON.stringify({ expo_push_token: token, cihaz_kimligi: cihazKimligi }),
        });
        // 2026-08-18 (güvenlik denetimi madde 14): gerçek bildirim
        // kimliğinin (token) konsola yazılması sadece GELİŞTİRME modunda
        // yapılıyor -- üretim (Play Store) derlemesinde bu satır hiç
        // çalışmaz, token cihazın kendi log'unda bile görünmez.
        if (__DEV__) {
          console.log('✓ Push token kaydedildi:', token);
        }
      } catch (e) {
        // Bildirim kaydı ana uygulama akışını ASLA bozmamalı -- hata
        // olursa sessizce yut, sadece logla.
        console.log('✗ Push bildirim kaydı başarısız:', e);
      }
    })();
  }, []);
}
