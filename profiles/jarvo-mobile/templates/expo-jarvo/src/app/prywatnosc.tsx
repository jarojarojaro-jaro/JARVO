import * as WebBrowser from 'expo-web-browser';

import { Ekran } from '@/components/Ekran';
import { Przycisk } from '@/components/Przycisk';
import { Tekst } from '@/components/Tekst';
import { APLIKACJA } from '@/config/aplikacja';

// Skrót polityki prywatności w aplikacji + pełna wersja pod stałym adresem (ten sam adres jest w App Store Connect
// i Play Console). Treść skrótu ma się zgadzać z etykietami prywatności Apple i formularzem Data safety.
export default function Prywatnosc() {
  const f = APLIKACJA.firma;
  return (
    <Ekran>
      <Tekst wariant="naglowek">Twoje dane</Tekst>
      <Tekst>
        {`Administratorem danych jest ${f.nazwa.replace(/\.$/, '')}. Zbieramy tylko dane potrzebne do działania aplikacji i nie sprzedajemy ich.`}
      </Tekst>
      {APLIKACJA.funkcje.ai ? (
        <Tekst>
          Część funkcji korzysta z zewnętrznego modelu sztucznej inteligencji. Zanim wyślemy do niego Twoje dane, poprosimy o zgodę.
        </Tekst>
      ) : null}
      <Tekst drugi>{`Pytania o dane: ${f.email}`}</Tekst>
      <Przycisk tytul="Pełna polityka prywatności" onPress={() => WebBrowser.openBrowserAsync(f.prywatnosc_url)} />
    </Ekran>
  );
}
