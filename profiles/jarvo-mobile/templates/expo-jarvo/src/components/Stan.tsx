import Ionicons from '@expo/vector-icons/Ionicons';
import { ActivityIndicator, StyleSheet, View } from 'react-native';

import { Przycisk } from '@/components/Przycisk';
import { Tekst } from '@/components/Tekst';
import { ODSTEP, useKolory } from '@/theme';

/** Stany ekranu: ładowanie, pusto, błąd. Ekran nigdy nie zostaje pusty ani biały. */
export function Ladowanie({ tekst = 'Ładowanie…' }: { tekst?: string }) {
  const k = useKolory();
  return (
    <View style={styles.srodek} accessibilityLiveRegion="polite">
      <ActivityIndicator color={k.glowny} />
      <Tekst drugi>{tekst}</Tekst>
    </View>
  );
}

export function Pusto({ tekst, akcja, onAkcja }: { tekst: string; akcja?: string; onAkcja?: () => void }) {
  const k = useKolory();
  return (
    <View style={styles.srodek}>
      <Ionicons name="file-tray-outline" size={40} color={k.tekstDrugi} />
      <Tekst drugi style={styles.wyrownaj}>{tekst}</Tekst>
      {akcja && onAkcja ? <Przycisk tytul={akcja} wariant="drugi" onPress={onAkcja} /> : null}
    </View>
  );
}

export function Blad({ tekst = 'Coś poszło nie tak.', onPonow }: { tekst?: string; onPonow?: () => void }) {
  const k = useKolory();
  return (
    <View style={styles.srodek} accessibilityLiveRegion="assertive">
      <Ionicons name="alert-circle-outline" size={40} color={k.blad} />
      <Tekst style={styles.wyrownaj}>{tekst}</Tekst>
      {onPonow ? <Przycisk tytul="Spróbuj ponownie" onPress={onPonow} /> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  srodek: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: ODSTEP.m, padding: ODSTEP.xl },
  wyrownaj: { textAlign: 'center' },
});
