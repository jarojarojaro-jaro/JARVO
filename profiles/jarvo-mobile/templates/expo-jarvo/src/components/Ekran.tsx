import type { ReactNode } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View } from 'react-native';

import { MAKS_SZEROKOSC, ODSTEP, useKolory } from '@/theme';

type Props = { children: ReactNode; przewijany?: boolean };

/**
 * Ekran z marginesami, szerokością czytelną na tabletach i w przeglądarce, przewijaniem i klawiaturą,
 * która nie zasłania pól (KeyboardAvoidingView). Bezpieczne obszary (wycięcie ekranu, pasek gestów)
 * obsługuje nagłówek nawigacji i contentInsetAdjustmentBehavior.
 */
export function Ekran({ children, przewijany = true }: Props) {
  const k = useKolory();
  const tresc = <View style={styles.tresc}>{children}</View>;
  return (
    <KeyboardAvoidingView
      style={[styles.pelny, { backgroundColor: k.tlo }]}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      {przewijany ? (
        <ScrollView
          contentInsetAdjustmentBehavior="automatic"
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={styles.przewijanie}>
          {tresc}
        </ScrollView>
      ) : (
        tresc
      )}
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  pelny: { flex: 1 },
  przewijanie: { flexGrow: 1, paddingVertical: ODSTEP.xl },
  tresc: { width: '100%', maxWidth: MAKS_SZEROKOSC, alignSelf: 'center', paddingHorizontal: ODSTEP.xl, gap: ODSTEP.l },
});
