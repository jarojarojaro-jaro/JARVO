import Ionicons from '@expo/vector-icons/Ionicons';
import { Tabs } from 'expo-router';
import { Platform } from 'react-native';

import { useKolory } from '@/theme';

export default function UkladZakladek() {
  const k = useKolory();
  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: k.glowny,
        tabBarInactiveTintColor: k.tekstDrugi,
        // na telefonie wysokość paska liczy system (bezpieczny obszar, gesty); w przeglądarce trzeba jej więcej na podpis
        tabBarStyle: { backgroundColor: k.tlo, borderTopColor: k.linia, ...(Platform.OS === 'web' ? { height: 64 } : null) },
        tabBarLabelStyle: { fontSize: 12, lineHeight: 16 },
        headerStyle: { backgroundColor: k.tlo },
        headerTintColor: k.tekst,
        headerShadowVisible: false,
      }}>
      <Tabs.Screen
        name="index"
        options={{ title: 'Start', tabBarIcon: ({ color, size }) => <Ionicons name="home-outline" color={color} size={size} /> }}
      />
      <Tabs.Screen
        name="wiecej"
        options={{ title: 'Więcej', tabBarIcon: ({ color, size }) => <Ionicons name="menu-outline" color={color} size={size} /> }}
      />
    </Tabs>
  );
}
