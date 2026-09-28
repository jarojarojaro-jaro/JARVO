# Scena 3D

Przestrzeń i kamera są treścią: świat 3D, lot kamery, produkt w 3D, low-poly, shader, scena z głębią.
Nie to: płaska grafika z parallaxą → `motion-graphics.md`; gra do grania → `interaktywne.md`.

## Wynik
- 8–30 s (render na CPU jest drogi: krótko i dopracowane); 16:9 albo 9:16; 30 fps (60 tylko, gdy karta każe).
- Modele i tekstury z kodu albo z licencją CC0 (Poly Haven), zero cudzych modeli i marek.

## Silnik
| Styl | Silnik |
|---|---|
| własna scena Three.js (geometria z kodu, shadery, cząstki) | własny HTML (`kontrakt-html.md`, `/_lib/three`) |
| gotowy styl 3D (klocki, papier, lampiony) + reżyseria | `lemo-opuscar` (style 3D, HDRI w bibliotece) |
| 3D w projekcie Remotion (UI + 3D razem) | `remotion-best-practices` (`@remotion/three`) |

## Struktura
| 15 s | Ujęcie |
|---|---|
| 0–2 | **Wejście:** kamera już w ruchu (dolly, orbit), obiekt częściowo w kadrze |
| 2–10 | **Odsłona:** 1–2 ruchy kamery po krzywej, światło prowadzi do najważniejszego detalu |
| 10–13 | **Detal:** zbliżenie albo przemiana (rozłożenie na części, materiał, pora dnia) |
| 13–15 | **Kadr końcowy** jak plakat (miniatura), miejsce na tekst albo logo |

## Rzemiosło
- Wszystko z `t`: pozycje, kamera, uniformy shaderów; losowość z ziarnem; fizyka z krokiem stałym od `t = 0`.
- Kamera po krzywej (`CatmullRomCurve3`) z easingiem prędkości, bez szarpnięć; ogniskowa stała w ujęciu.
- Światło: klucz + kontra (rim) + wypełnienie albo HDRI; mgła dla głębi; tonemapping ACES, sRGB na wyjściu.
- Geometria z kodu (low-poly, instancing dla wielu obiektów); materiały proste, jeden materiał „bohatera”.
- Post-processing z umiarem (bloom tylko na świecących elementach); ziarno i winieta subtelne.
- Wydajność na VPS bez GPU (WebGL na CPU): cienie tylko z jednego światła, ≤ 200 tys. trójkątów,
  bez ciężkich przebiegów; zmierz czas 1 klatki przed renderem całości.

## Brief (`out/wideo/src/BRIEF.md`)
```
Obiekt / świat i nastrój (jedno zdanie):       Ujęcia (czas → ruch kamery → co widać):
Światło i paleta, materiały:                    Źródła geometrii i tekstur (kod / CC0):
Format, długość, fps, tekst na końcu:          Budżet renderu (czas 1 klatki × liczba klatek):
```

## Pułapki
- `clock.getDelta()` i animacje z zegara (klatki różne przy każdym renderze); losowość bez ziarna.
- Kamera, która kręci się bez celu; obiekt ginący w ciemności; tekst w 3D nieczytelny pod kątem.
- Render 60 s × 60 fps bez pomiaru (na CPU to godziny); cudze modele z internetu bez licencji.

## Kontrola
- Arkusz 1 klatka na ujęcie + pasek klatek przy ruchu kamery (płynność, brak skoków, brak migotania cieni).
- Pomiar czasu renderu zapisany w RAPORT; licencje HDRI i tekstur w RAPORT.

## Inspiracje
`python3 $HERMES_HOME/scripts/inspiracje.py scena-3d --ile 3` (albo `--tag shader`, `--szukaj flyover`).
