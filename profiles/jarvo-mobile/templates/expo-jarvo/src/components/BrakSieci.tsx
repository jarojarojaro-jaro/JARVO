import Ionicons from '@expo/vector-icons/Ionicons';
import { useNetworkState } from 'expo-network';
import { StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Tekst } from '@/components/Tekst';
import { ODSTEP, useKolory } from '@/theme';

/** Pasek „Brak internetu” nad treścią zamiast pustych ekranów i niekończącego się ładowania. */
export function BrakSieci() {
  const siec = useNetworkState();
  const wciecia = useSafeAreaInsets();
  const k = useKolory();
  if (siec.isConnected !== false && siec.isInternetReachable !== false) return null;
  return (
    <View
      accessibilityRole="alert"
      accessibilityLiveRegion="polite"
      style={[styles.pasek, { paddingTop: wciecia.top + ODSTEP.s, backgroundColor: k.tekst }]}>
      <Ionicons name="cloud-offline-outline" size={18} color={k.tlo} />
      <Tekst wariant="drobny" kolor={k.tlo}>Brak internetu. Pokazujemy to, co już jest w telefonie.</Tekst>
    </View>
  );
}

const styles = StyleSheet.create({
  pasek: { flexDirection: 'row', alignItems: 'center', gap: ODSTEP.s, paddingHorizontal: ODSTEP.l, paddingBottom: ODSTEP.s },
});
