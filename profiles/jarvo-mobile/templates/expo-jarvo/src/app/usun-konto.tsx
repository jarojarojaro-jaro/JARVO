import { router } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import { useState } from 'react';
import { Alert, Platform } from 'react-native';

import { Ekran } from '@/components/Ekran';
import { Przycisk } from '@/components/Przycisk';
import { Tekst } from '@/components/Tekst';
import { APLIKACJA } from '@/config/aplikacja';
import { usunKonto } from '@/lib/konto';
import { useKolory } from '@/theme';

// Usuwanie konta w aplikacji (Apple 5.1.1(v), Google Play): trwałe, z potwierdzeniem, bez szukania po stronie.
export default function UsunKonto() {
  const k = useKolory();
  const [laduje, setLaduje] = useState(false);
  const [blad, setBlad] = useState<string | null>(null);

  async function usun() {
    setLaduje(true);
    setBlad(null);
    try {
      await usunKonto();
      router.replace('/');
    } catch (e) {
      setBlad(e instanceof Error ? e.message : 'Nie udało się usunąć konta.');
    } finally {
      setLaduje(false);
    }
  }

  function potwierdz() {
    const pytanie = 'Usunąć konto? Tego nie da się cofnąć: znikną Twoje dane i historia.';
    if (Platform.OS === 'web') {
      if (window.confirm(pytanie)) void usun();
      return;
    }
    Alert.alert('Usuń konto', pytanie, [
      { text: 'Anuluj', style: 'cancel' },
      { text: 'Usuń', style: 'destructive', onPress: () => void usun() },
    ]);
  }

  return (
    <Ekran>
      <Tekst wariant="naglowek">Usunięcie konta</Tekst>
      <Tekst>Usuniemy Twoje konto i dane z nim związane. Dane, które musimy przechowywać z mocy prawa (np. faktury), zostaną tylko na wymagany czas.</Tekst>
      {blad ? <Tekst accessibilityRole="alert" kolor={k.blad}>{blad}</Tekst> : null}
      <Przycisk tytul="Usuń konto" wariant="niebezpieczny" laduje={laduje} onPress={potwierdz} />
      {APLIKACJA.firma.usuwanie_konta_url ? (
        <Przycisk tytul="Instrukcja na stronie" wariant="drugi" onPress={() => WebBrowser.openBrowserAsync(APLIKACJA.firma.usuwanie_konta_url)} />
      ) : null}
    </Ekran>
  );
}
