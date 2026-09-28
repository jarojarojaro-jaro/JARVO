# Poziom „na nagrodę” (CSS Design Awards)

Tylko gdy karta prosi o „stronę na nagrodę” albo „wow”. Dane za oh-my-hermes (odczyt reguł CSSDA i dziewięciu
nagrodzonych stron, 2026-09-03); przed cytowaniem liczb sprawdź reguły na nowo.

- **Osie jury:** UI 40% (estetyka, rzemiosło, efekty), UX 30% (doświadczenie, działanie), Innowacja 30%.
  **8,0** = Website of the Day, **6,0** = Special Kudos.
- „Nagrodzona” znaczy **przekroczyła 8,0**, nie „wyjątkowa”: zwycięzcy skupiają się tuż nad progiem (8,0–8,5).
  Brief traktujący to jak wyjątek przesadza z budową.
- **Osie idą razem:** różnica między osiami jednej strony to zwykle ok. 0,1 (maks. 0,5), a między stronami ok. 2.
  Jury ocenia stronę, nie trzy osobne cechy. Poniżej ok. 7,7 problemem jest cała strona, nie jedna oś.
- **Minimum wejścia:** płynna typografia (`clamp()`, 8/9 stron) i własny albo zmienny font (8/9). Ich brak kosztuje,
  obecność nie daje punktów.
- **WebGL/Three.js nie jest wymagany** (3/9 stron); 8,50 osiągnięto samym GSAP i przewijaniem.
- Ruch: 6/9 stron ma bibliotekę ruchu, ale dwie najlepsze **respektują `prefers-reduced-motion`**. Dostępna ścieżka
  nie jest gorzej oceniana.
- Każdy ruch „pod innowację”, który łamie budżet (WCAG, Core Web Vitals), zapisujesz w raporcie jako kompromis
  i zostawiasz decyzję użytkownikowi. Najpierw szukasz wersji bez kosztu: ruch za `prefers-reduced-motion`,
  natywna kontrolka ostylowana zamiast przebudowanej, scena 3D z plakatem zastępczym.

Ocena wg tej skali to samoocena: nie przewiduje decyzji jury.
