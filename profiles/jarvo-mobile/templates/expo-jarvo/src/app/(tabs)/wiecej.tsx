import { router } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import { View } from 'react-native';

import { Ekran } from '@/components/Ekran';
import { Tekst } from '@/components/Tekst';
import { Wiersz } from '@/components/Wiersz';
import { APLIKACJA } from '@/config/aplikacja';

// Elementy wymagane przez sklepy są zawsze dostępne w dwóch dotknięciach: kontakt (wsparcie), polityka prywatności
// (Apple 5.1.1(i), Google Data safety) i usuwanie konta, gdy aplikacja ma konta (Apple 5.1.1(v), Google Play).
export default function Wiecej() {
  return (
    <Ekran>
      <View>
        <Wiersz tytul="Kontakt" opis="Telefon, e-mail, adres" ikona="call-outline" onPress={() => router.push('/kontakt')} />
        <Wiersz tytul="Prywatność" opis="Jakie dane zbieramy i po co" ikona="shield-checkmark-outline" onPress={() => router.push('/prywatnosc')} />
        {APLIKACJA.firma.strona ? (
          <Wiersz tytul="Strona internetowa" ikona="globe-outline" link onPress={() => WebBrowser.openBrowserAsync(APLIKACJA.firma.strona)} />
        ) : null}
        {APLIKACJA.funkcje.konta ? (
          <Wiersz tytul="Usuń konto" opis="Trwale usuwa konto i dane" ikona="trash-outline" niebezpieczny onPress={() => router.push('/usun-konto')} />
        ) : null}
      </View>
      <Tekst wariant="drobny" drugi>{`${APLIKACJA.nazwa} · wersja ${APLIKACJA.wersja}`}</Tekst>
    </Ekran>
  );
}
