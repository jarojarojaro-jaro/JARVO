// Przypomnienia lokalne (moduł JARVO „powiadomienia”, dodaje go `aplikacja.py ustaw`, gdy profil zgodności ma
// powiadomienia). Bez serwera push: telefon sam pokazuje przypomnienie o zaplanowanej porze. O zgodę prosimy dopiero
// w chwili, gdy klient włącza przypomnienia, z wyjaśnieniem po co (Apple 5.1.2(i), Google: uprawnienia); odmowa
// nie blokuje reszty aplikacji. Wersja webowa (podgląd w HQ): przypomnienia.ts, bez expo-notifications.
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

const KANAL = 'przypomnienia';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: false,
    shouldSetBadge: false,
  }),
});

export type StanZgody = 'zgoda' | 'odmowa' | 'nie-pytano' | 'niedostepne';

export async function stanZgody(): Promise<StanZgody> {
  if (Platform.OS === 'web') return 'niedostepne';
  const s = await Notifications.getPermissionsAsync();
  if (s.granted) return 'zgoda';
  return s.canAskAgain ? 'nie-pytano' : 'odmowa';
}

/** Prosi o zgodę (tylko po akcji klienta). Zwraca true, gdy przypomnienia mogą działać. */
export async function poprosOZgode(): Promise<boolean> {
  if (Platform.OS === 'web') return false;
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync(KANAL, {
      name: 'Przypomnienia',
      importance: Notifications.AndroidImportance.DEFAULT,
    });
  }
  const teraz = await Notifications.getPermissionsAsync();
  if (teraz.granted) return true;
  if (!teraz.canAskAgain) return false;
  return (await Notifications.requestPermissionsAsync()).granted;
}

/** Planuje przypomnienie na konkretną chwilę; zwraca jego identyfikator albo null bez zgody. */
export async function zaplanuj(kiedy: Date, tytul: string, tresc: string): Promise<string | null> {
  if (!(await poprosOZgode()) || kiedy.getTime() <= Date.now()) return null;
  return Notifications.scheduleNotificationAsync({
    content: { title: tytul, body: tresc },
    trigger: { type: Notifications.SchedulableTriggerInputTypes.DATE, date: kiedy, channelId: KANAL },
  });
}

export async function zaplanowane(): Promise<Notifications.NotificationRequest[]> {
  if (Platform.OS === 'web') return [];
  return Notifications.getAllScheduledNotificationsAsync();
}

export async function anuluj(id: string): Promise<void> {
  await Notifications.cancelScheduledNotificationAsync(id);
}
