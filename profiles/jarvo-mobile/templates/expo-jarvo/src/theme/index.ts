import { useColorScheme } from 'react-native';

import { KOLORY } from './kolory';

export type Kolory = { [K in keyof typeof KOLORY.jasny]: string };

/** Kolory dla bieżącego motywu systemu (jasny albo ciemny). */
export function useKolory(): Kolory {
  return useColorScheme() === 'dark' ? KOLORY.ciemny : KOLORY.jasny;
}

export const ODSTEP = { xs: 4, s: 8, m: 12, l: 16, xl: 24, xxl: 32 } as const;
export const PROMIEN = { s: 8, m: 12, l: 16 } as const;
/** Minimalny cel dotyku: 44 pt (Apple HIG), 48 dp (Material). Bierzemy większy. */
export const CEL_DOTYKU = 48;
export const MAKS_SZEROKOSC = 640;
