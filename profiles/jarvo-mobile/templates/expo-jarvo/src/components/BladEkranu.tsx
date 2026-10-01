import type { ErrorBoundaryProps } from 'expo-router';

import { Blad } from '@/components/Stan';

/** Granica błędów każdego ekranu: zamiast białego ekranu komunikat i „Spróbuj ponownie”. */
export function ErrorBoundary({ retry }: ErrorBoundaryProps) {
  return <Blad tekst="Ten ekran się nie wczytał. Spróbuj jeszcze raz." onPonow={retry} />;
}
