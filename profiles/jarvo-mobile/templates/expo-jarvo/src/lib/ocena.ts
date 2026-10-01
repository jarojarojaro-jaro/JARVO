import * as StoreReview from 'expo-store-review';

/**
 * Prośba o ocenę w sklepie przez systemowe okno (Apple i Google same limitują, ile razy się pokaże).
 * Wołaj po udanej akcji klienta (rezerwacja, zamówienie), nigdy przy starcie aplikacji ani po błędzie.
 */
export async function poprosOOcene(): Promise<void> {
  try {
    if (await StoreReview.isAvailableAsync()) await StoreReview.requestReview();
  } catch {
    // brak okna oceny (np. w przeglądarce) nie może przerwać akcji klienta
  }
}
