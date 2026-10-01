import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useColorScheme } from 'react-native';

import { BrakSieci } from '@/components/BrakSieci';
import { useKolory } from '@/theme';

export { ErrorBoundary } from '@/components/BladEkranu';

export default function UkladGlowny() {
  const ciemny = useColorScheme() === 'dark';
  const k = useKolory();
  const baza = ciemny ? DarkTheme : DefaultTheme;
  return (
    <ThemeProvider
      value={{ ...baza, colors: { ...baza.colors, primary: k.glowny, background: k.tlo, card: k.tlo, text: k.tekst, border: k.linia } }}>
      <BrakSieci />
      <Stack screenOptions={{ headerBackButtonDisplayMode: 'minimal', contentStyle: { backgroundColor: k.tlo } }}>
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="kontakt" options={{ title: 'Kontakt' }} />
        <Stack.Screen name="prywatnosc" options={{ title: 'Prywatność' }} />
        <Stack.Screen name="usun-konto" options={{ title: 'Usuń konto' }} />
      </Stack>
      <StatusBar style="auto" />
    </ThemeProvider>
  );
}
