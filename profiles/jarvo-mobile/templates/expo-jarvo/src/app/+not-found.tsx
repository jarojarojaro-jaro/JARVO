import { Link, Stack } from 'expo-router';

import { Ekran } from '@/components/Ekran';
import { Tekst } from '@/components/Tekst';

export default function NieZnaleziono() {
  return (
    <Ekran>
      <Stack.Screen options={{ title: 'Nie ma takiego ekranu' }} />
      <Tekst wariant="naglowek">Tego ekranu nie ma.</Tekst>
      <Link href="/">
        <Tekst wariant="etykieta">Wróć na start</Tekst>
      </Link>
    </Ekran>
  );
}
