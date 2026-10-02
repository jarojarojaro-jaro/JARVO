// Przypomnienia w przeglądarce (podgląd w HQ): niedostępne. Bez importu expo-notifications, które w przeglądarce
// sięga do localStorage, a w podglądzie HQ (piaskownica bez dostępu do pamięci strony) kończy się błędem konsoli.
// Telefon (Expo Go, buildy) używa przypomnienia.native.ts; oba pliki mają to samo API.
export type StanZgody = 'zgoda' | 'odmowa' | 'nie-pytano' | 'niedostepne';

export type Zaplanowane = { identifier: string; content: { title: string | null } };

export async function stanZgody(): Promise<StanZgody> {
  return 'niedostepne';
}

export async function poprosOZgode(): Promise<boolean> {
  return false;
}

export async function zaplanuj(_kiedy: Date, _tytul: string, _tresc: string): Promise<string | null> {
  return null;
}

export async function zaplanowane(): Promise<Zaplanowane[]> {
  return [];
}

export async function anuluj(_id: string): Promise<void> {}
