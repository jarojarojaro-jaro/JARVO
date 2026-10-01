import { ActivityIndicator, Pressable, StyleSheet, type PressableProps } from 'react-native';

import { Tekst } from '@/components/Tekst';
import { CEL_DOTYKU, ODSTEP, PROMIEN, useKolory } from '@/theme';

type Props = Omit<PressableProps, 'children'> & {
  tytul: string;
  wariant?: 'glowny' | 'drugi' | 'niebezpieczny';
  laduje?: boolean;
};

/** Przycisk z celem dotyku ≥ 48, stanami dla czytnika ekranu i blokadą podwójnego kliknięcia przy ładowaniu. */
export function Przycisk({ tytul, wariant = 'glowny', laduje, disabled, style, ...props }: Props) {
  const k = useKolory();
  const wylaczony = disabled || laduje;
  const tlo = wariant === 'glowny' ? k.glowny : wariant === 'niebezpieczny' ? k.blad : 'transparent';
  const tekst = wariant === 'drugi' ? k.glowny : k.naGlownym;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={tytul}
      accessibilityState={{ disabled: !!wylaczony, busy: !!laduje }}
      disabled={wylaczony}
      style={(stan) => [
        styles.przycisk,
        { backgroundColor: tlo, borderColor: wariant === 'drugi' ? k.glowny : tlo, opacity: wylaczony ? 0.5 : stan.pressed ? 0.8 : 1 },
        typeof style === 'function' ? style(stan) : style,
      ]}
      {...props}>
      {laduje ? <ActivityIndicator color={tekst} /> : <Tekst wariant="etykieta" kolor={tekst}>{tytul}</Tekst>}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  przycisk: {
    minHeight: CEL_DOTYKU,
    paddingHorizontal: ODSTEP.xl,
    borderRadius: PROMIEN.m,
    borderWidth: 1.5,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
