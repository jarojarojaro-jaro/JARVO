// Paleta z koloru marki (generuje `aplikacja.py ustaw`; kontrast WCAG AA sprawdzony przy generowaniu).
export const KOLORY = {
  jasny: {
    tlo: '#FFFFFF',
    powierzchnia: '#F4F5F7',
    tekst: '#111318',
    tekstDrugi: '#5B616E',
    linia: '#E3E5EA',
    glowny: '#2F5BEA',
    naGlownym: '#FFFFFF',
    blad: '#B42318',
    sukces: '#067647',
  },
  ciemny: {
    tlo: '#0E0F12',
    powierzchnia: '#1A1C21',
    tekst: '#F2F3F5',
    tekstDrugi: '#A3A8B3',
    linia: '#2A2D33',
    glowny: '#7C9BF5',
    naGlownym: '#0E0F12',
    blad: '#F97066',
    sukces: '#47CD89',
  },
} as const;
