import { router } from 'expo-router';
import { StyleSheet, View } from 'react-native';

import { Ekran } from '@/components/Ekran';
import { Przycisk } from '@/components/Przycisk';
import { Tekst } from '@/components/Tekst';
import { APLIKACJA } from '@/config/aplikacja';
import { ODSTEP, PROMIEN, useKolory } from '@/theme';

// Ekran startowy z szablonu: Twórca aplikacji zastępuje go ekranami z planu (out/PLAN.md). Wartość ma być widoczna
// bez zakładania konta (pierwsze 30 sekund decydują, czy klient zostanie).
export default function Start() {
  const k = useKolory();
  return (
    <Ekran>
      <View style={[styles.karta, { backgroundColor: k.glowny }]}>
        <Tekst wariant="tytul" kolor={k.naGlownym}>{APLIKACJA.nazwa}</Tekst>
        <Tekst kolor={k.naGlownym}>{APLIKACJA.opis}</Tekst>
      </View>
      <Tekst wariant="naglowek">Co możesz zrobić</Tekst>
      {/* JARVO-TODO: funkcje z planu zamiast tego tekstu (sklep_check.py blokuje wysłanie z tym znacznikiem). */}
      <Tekst drugi>Tu pojawią się główne funkcje aplikacji z planu.</Tekst>
      <Przycisk tytul="Skontaktuj się z nami" wariant="drugi" onPress={() => router.push('/kontakt')} />
    </Ekran>
  );
}

const styles = StyleSheet.create({
  karta: { borderRadius: PROMIEN.l, padding: ODSTEP.xl, gap: ODSTEP.s },
});
