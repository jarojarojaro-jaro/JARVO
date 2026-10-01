import Ionicons from '@expo/vector-icons/Ionicons';
import { Pressable, StyleSheet, View } from 'react-native';

import { Tekst } from '@/components/Tekst';
import { CEL_DOTYKU, ODSTEP, useKolory } from '@/theme';

type Props = {
  tytul: string;
  opis?: string;
  ikona?: keyof typeof Ionicons.glyphMap;
  onPress: () => void;
  link?: boolean;
  niebezpieczny?: boolean;
};

/** Wiersz listy (ustawienia, menu): cały wiersz jest celem dotyku ≥ 52, z etykietą dla czytnika ekranu. */
export function Wiersz({ tytul, opis, ikona, onPress, link, niebezpieczny }: Props) {
  const k = useKolory();
  const kolor = niebezpieczny ? k.blad : k.tekst;
  return (
    <Pressable
      accessibilityRole={link ? 'link' : 'button'}
      accessibilityLabel={opis ? `${tytul}. ${opis}` : tytul}
      onPress={onPress}
      style={({ pressed }) => [styles.wiersz, { borderBottomColor: k.linia, opacity: pressed ? 0.7 : 1 }]}>
      {ikona ? <Ionicons name={ikona} size={22} color={kolor} /> : null}
      <View style={styles.teksty}>
        <Tekst wariant="etykieta" kolor={kolor}>{tytul}</Tekst>
        {opis ? <Tekst wariant="drobny" drugi>{opis}</Tekst> : null}
      </View>
      <Ionicons name={link ? 'open-outline' : 'chevron-forward'} size={18} color={k.tekstDrugi} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  wiersz: {
    minHeight: CEL_DOTYKU + 4,
    flexDirection: 'row',
    alignItems: 'center',
    gap: ODSTEP.m,
    paddingVertical: ODSTEP.m,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  teksty: { flex: 1, gap: 2 },
});
