import { Linking, View } from 'react-native';

import { Ekran } from '@/components/Ekran';
import { Tekst } from '@/components/Tekst';
import { Wiersz } from '@/components/Wiersz';
import { APLIKACJA } from '@/config/aplikacja';

export default function Kontakt() {
  const f = APLIKACJA.firma;
  return (
    <Ekran>
      <Tekst wariant="naglowek">{f.nazwa}</Tekst>
      {f.adres ? <Tekst drugi>{f.adres}</Tekst> : null}
      <View>
        {f.telefon ? (
          <Wiersz tytul="Zadzwoń" opis={f.telefon} ikona="call-outline" onPress={() => Linking.openURL(`tel:${f.telefon.replace(/\s/g, '')}`)} />
        ) : null}
        {f.email ? <Wiersz tytul="Napisz e-mail" opis={f.email} ikona="mail-outline" onPress={() => Linking.openURL(`mailto:${f.email}`)} /> : null}
      </View>
    </Ekran>
  );
}
