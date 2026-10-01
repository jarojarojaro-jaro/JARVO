import { StyleSheet, Text, type TextProps } from 'react-native';

import { useKolory } from '@/theme';

type Wariant = 'tytul' | 'naglowek' | 'tresc' | 'drobny' | 'etykieta';

type Props = TextProps & { wariant?: Wariant; drugi?: boolean; kolor?: string };

/** Tekst z typografią aplikacji. Skaluje się z czcionką systemową (dostępność); tytuły do 2×, żeby się mieściły. */
export function Tekst({ wariant = 'tresc', drugi, kolor, style, ...props }: Props) {
  const k = useKolory();
  return (
    <Text
      maxFontSizeMultiplier={wariant === 'tytul' || wariant === 'naglowek' ? 2 : undefined}
      accessibilityRole={wariant === 'tytul' || wariant === 'naglowek' ? 'header' : undefined}
      style={[style_[wariant], { color: kolor ?? (drugi ? k.tekstDrugi : k.tekst) }, style]}
      {...props}
    />
  );
}

const style_ = StyleSheet.create({
  tytul: { fontSize: 28, lineHeight: 34, fontWeight: '700' },
  naglowek: { fontSize: 20, lineHeight: 26, fontWeight: '600' },
  tresc: { fontSize: 16, lineHeight: 24 },
  drobny: { fontSize: 13, lineHeight: 18 },
  etykieta: { fontSize: 15, lineHeight: 20, fontWeight: '600' },
});
