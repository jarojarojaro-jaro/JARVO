// Konto klienta. Usuwanie konta w aplikacji jest wymagane przez App Store (5.1.1(v)) i Google Play, gdy aplikacja
// pozwala założyć konto. Dezaktywacja się nie liczy: dane mają zniknąć albo zostać zanonimizowane.

/** Usuwa konto zalogowanego klienta w backendzie (np. funkcja Supabase z usunięciem danych). */
export async function usunKonto(): Promise<void> {
  // JARVO-TODO: podłącz do backendu przed wydaniem (sklep_check.py blokuje wysłanie z tym znacznikiem).
  throw new Error('Usuwanie konta nie jest jeszcze podłączone do serwera.');
}
