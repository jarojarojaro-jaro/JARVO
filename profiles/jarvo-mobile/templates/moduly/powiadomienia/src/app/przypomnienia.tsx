import { useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { Linking, View } from 'react-native';

import { Ekran } from '@/components/Ekran';
import { Przycisk } from '@/components/Przycisk';
import { Tekst } from '@/components/Tekst';
import { Wiersz } from '@/components/Wiersz';
import { APLIKACJA } from '@/config/aplikacja';
import { anuluj, poprosOZgode, stanZgody, zaplanowane, zaplanuj, type StanZgody } from '@/lib/przypomnienia';

// Ekran przypomnień (moduł JARVO „powiadomienia”): wyjaśnienie przed prośbą o zgodę, stan zgody, lista zaplanowanych
// przypomnień i próbne przypomnienie, żeby klient zobaczył, jak wygląda. Funkcje z planu (wizyta, odbiór zamówienia)
// wołają `zaplanuj()` z `@/lib/przypomnienia`.
export default function Przypomnienia() {
  const [zgoda, setZgoda] = useState<StanZgody>('nie-pytano');
  const [lista, setLista] = useState<{ id: string; tytul: string }[]>([]);
  const [laduje, setLaduje] = useState(false);

  const odswiez = useCallback(() => {
    stanZgody().then(setZgoda);
    zaplanowane().then((z) => setLista(z.map((p) => ({ id: p.identifier, tytul: p.content.title ?? 'Przypomnienie' }))));
  }, []);
  useFocusEffect(odswiez);

  const wlacz = async () => {
    setLaduje(true);
    await poprosOZgode();
    setLaduje(false);
    odswiez();
  };
  const probne = async () => {
    await zaplanuj(new Date(Date.now() + 10_000), APLIKACJA.nazwa, 'Tak będzie wyglądać przypomnienie z aplikacji.');
    odswiez();
  };

  return (
    <Ekran>
      <Tekst wariant="naglowek">Przypomnienia</Tekst>
      <Tekst drugi>
        {`${APLIKACJA.nazwa} przypomni Ci o tym, co ważne: wizycie, odbiorze zamówienia albo wydarzeniu. Przypomnienia
zostają na Twoim telefonie; możesz je wyłączyć w każdej chwili.`.replace(/\n/g, ' ')}
      </Tekst>
      {zgoda === 'niedostepne' ? (
        <Tekst drugi>Przypomnienia działają w aplikacji na telefonie.</Tekst>
      ) : zgoda === 'zgoda' ? (
        <Przycisk tytul="Wyślij próbne przypomnienie (za 10 s)" wariant="drugi" onPress={probne} />
      ) : zgoda === 'odmowa' ? (
        <>
          <Tekst drugi>Powiadomienia są wyłączone w ustawieniach telefonu.</Tekst>
          <Przycisk tytul="Otwórz ustawienia" wariant="drugi" onPress={() => Linking.openSettings()} />
        </>
      ) : (
        <Przycisk tytul="Włącz przypomnienia" laduje={laduje} onPress={wlacz} />
      )}
      {lista.length ? (
        <View>
          <Tekst wariant="etykieta">Zaplanowane</Tekst>
          {lista.map((p) => (
            <Wiersz key={p.id} tytul={p.tytul} opis="Dotknij, aby usunąć" ikona="notifications-outline"
              onPress={() => anuluj(p.id).then(odswiez)} />
          ))}
        </View>
      ) : null}
    </Ekran>
  );
}
