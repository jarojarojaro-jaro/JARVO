// Konfiguracja aplikacji (Expo). Tożsamość, dane firmy i funkcje są w jarvo.app.json, który ustawia
// `aplikacja.py ustaw` (Twórca aplikacji); tu jest tylko mapowanie na pola Expo. Nie wpisuj tu sekretów:
// wszystko z tej konfiguracji trafia do paczki aplikacji.
import type { ConfigContext, ExpoConfig } from 'expo/config';

import app from './jarvo.app.json';

// APP_VARIANT=expo-go: podgląd w Expo Go przez EAS Update (runtime = wersja SDK); buildy sklepowe: odcisk kodu natywnego,
// żeby aktualizacja JS nigdy nie trafiła do builda z innym kodem natywnym.
const wariant = process.env.APP_VARIANT ?? 'produkcja';
// podgląd w HQ (serwer :9120) serwuje stronę spod /<token>/, więc eksport webowy potrzebuje bazowej ścieżki
const bazowyUrl = process.env.JARVO_BASE_URL || undefined;

export default ({ config }: ConfigContext): ExpoConfig => ({
  ...config,
  name: app.nazwa,
  slug: app.slug,
  owner: app.wlasciciel_expo || undefined,
  version: app.wersja,
  scheme: app.scheme,
  orientation: 'portrait',
  userInterfaceStyle: 'automatic',
  icon: './assets/icon.png',
  runtimeVersion: wariant === 'expo-go' ? { policy: 'sdkVersion' } : { policy: 'fingerprint' },
  updates: app.expo_project_id ? { url: `https://u.expo.dev/${app.expo_project_id}` } : undefined,
  ios: {
    bundleIdentifier: app.bundle_ios,
    supportsTablet: app.tablet,
    config: { usesNonExemptEncryption: false },
    infoPlist: {
      CFBundleDevelopmentRegion: 'pl',
      CFBundleAllowMixedLocalizations: true,
      ...app.uprawnienia_ios,
    },
  },
  android: {
    package: app.pakiet_android,
    adaptiveIcon: {
      foregroundImage: './assets/android-icon-foreground.png',
      backgroundImage: './assets/android-icon-background.png',
      monochromeImage: './assets/android-icon-monochrome.png',
      backgroundColor: app.kolory.tlo_ikony,
    },
    blockedPermissions: app.zablokowane_uprawnienia_android,
  },
  locales: { pl: './locales/pl.json' },
  web: { output: 'single', favicon: './assets/favicon.png' },
  plugins: [
    'expo-router',
    [
      'expo-splash-screen',
      { image: './assets/splash-icon.png', imageWidth: 160, backgroundColor: '#FFFFFF', dark: { backgroundColor: '#0E0F12' } },
    ],
    ...(app.wtyczki as unknown as NonNullable<ExpoConfig['plugins']>),
  ],
  experiments: { typedRoutes: true, reactCompiler: true, ...(bazowyUrl ? { baseUrl: bazowyUrl } : {}) },
  extra: {
    jarvo: { opis: app.opis, firma: app.firma, funkcje: app.funkcje },
    ...(app.expo_project_id ? { eas: { projectId: app.expo_project_id } } : {}),
  },
});
