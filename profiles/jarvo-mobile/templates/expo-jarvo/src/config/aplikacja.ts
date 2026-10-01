// Dane firmy i funkcje aplikacji z app.config.ts (extra.jarvo ← jarvo.app.json). Jedno źródło prawdy:
// zmiany przez `aplikacja.py ustaw`, nie ręcznie w ekranach.
import Constants from 'expo-constants';

export type Firma = {
  nazwa: string;
  adres: string;
  email: string;
  telefon: string;
  strona: string;
  prywatnosc_url: string;
  usuwanie_konta_url: string;
};

export type Funkcje = { konta: boolean; tresci_uzytkownikow: boolean; ai: boolean };

type Jarvo = { opis: string; firma: Firma; funkcje: Funkcje };

const jarvo = (Constants.expoConfig?.extra?.jarvo ?? {}) as Partial<Jarvo>;

export const APLIKACJA = {
  nazwa: Constants.expoConfig?.name ?? '',
  wersja: Constants.expoConfig?.version ?? '',
  opis: jarvo.opis ?? '',
  firma: jarvo.firma as Firma,
  funkcje: (jarvo.funkcje ?? { konta: false, tresci_uzytkownikow: false, ai: false }) as Funkcje,
};
