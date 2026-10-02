# Zrzuty do sklepów

**Scenariusz** (`out/sklep/zrzuty.yaml`): 2–8 kadrów w kolejności karty. Kadr = jedna korzyść dla klienta
i ekran, który ją pokazuje w użyciu (Apple 2.3.3: nie samo logowanie, nie ekran startowy, nie pusty stan).
Nagłówek ≤ 40 znaków po polsku (copy od Studia), podtytuł opcjonalny. Dane na ekranach przykładowe, te same na obu
platformach, bez danych prawdziwych klientów.

```yaml
motyw: jasny
kadry:
  - trasa: /
    naglowek: "Wizyta w salonie w 30 sekund"
    podtytul: "Usługa, stylistka, godzina"
  - trasa: /karta
    naglowek: "Pieczątki zawsze przy Tobie"
```

**Źródła ekranów** (`pakiet.py zrzuty <app> --zrodlo …`):

| Źródło | Skąd | Do czego |
|---|---|---|
| `web` | eksport `dist-web` (`aplikacja.py podglad`), Playwright w profilach iPhone 17 Pro Max, Pixel, iPad 13″; pasek stanu 9:41 dorysowany | szkic karty dla właściciela; **nie do wysłania** (lista kontrolna oznacza go „?”) |
| `android` | telefon testowy floty (`urzadzenie.py`), zainstalowany build, tryb demo paska stanu (9:41, pełna bateria, bez powiadomień), trasy przez `schemat://trasa` | zrzuty Google Play |
| `ios` | artefakt `ios_ci.py` (symulator iPhone 17 Pro Max, `simctl status_bar override` 9:41), pliki `jasny-<trasa>.png` | zrzuty App Store 6,9″ |

**Kompozycja:** HTML w dokładnych wymiarach (kolor marki z gradientem, nagłówek bez polskich „sierotek”, ekran
w ramce bez kadrowania paska zakładek), render Playwright, zapis PNG bez alfy (sharp `removeAlpha`):

| Zestaw | Plik | Wymiary |
|---|---|---|
| App Store iPhone 6,9″ | `out/sklep/apple/pl-PL/ios-6.9/NN.png` | 1320×2868 (1–10) |
| App Store iPad 13″ (`tablet: true`) | `out/sklep/apple/pl-PL/ipad-13/NN.png` | 2064×2752 (1–10) |
| Google Play telefon | `out/sklep/google/pl-PL/images/phoneScreenshots/NN.png` | 1080×1920 (2–8) |
| Google ikona | `out/sklep/google/pl-PL/images/icon.png` | 512×512 PNG ≤ 1 MB |
| Google grafika promocyjna | `out/sklep/google/pl-PL/images/featureGraphic.png` | 1024×500 bez alfy |

**Kontrola:** punkty 34–38 listy (`sklep_check.py`): wymiary, alfa, liczba, OCR zrzutów iOS (żadnego „Android”,
„Google Play”), kadry z logowaniem, źródło. Potem oglądasz każdy kadr: nagłówek czytelny z odległości ręki, ekran
pokazuje to, co obiecuje nagłówek, nic nie ucięte, ten sam motyw w całym zestawie.

**Film podglądowy** (opcjonalnie): Wideograf skleja 15–30 s z nagrania przepływu (skill `demo-strony`); Apple wymaga
nagrania z samej aplikacji, bez kadrów spoza niej.
