# Wybór stylu malarskiego

35 stylów z huashu-art-motion (MIT). Każdy ma kartę `style/<id>.md`: po czym go poznać (z liczbami i kolorami), jak
go zbudować, co się rusza, przejście-podpis, wydajność, pułapki i kontrola. Czytasz tylko kartę wybranego stylu.
Obraz wszystkich naraz: `malarz.py galeria -o out/wideo/galeria-stylow.jpg`; lista z wyszukiwaniem:
`malarz.py style --szukaj luksus`.

| Styl (`id`) | Do czego (przykłady) |
|---|---|
| Malowidło jaskiniowe (`01_cave`) | otwarcie filmu o początkach: historia firmy, miasta, wynalazku |
| Egipskie malowidło grobowe (`02_egypt`) | muzeum, wystawa, lekcja historii starożytnej |
| Grecka waza czarnofigurowa (`03_greek`) | restauracja grecka, oliwa, wino, karta dań |
| Mozaika rzymska (`04_roman`) | płytki, kamieniarz, łazienki, logo ułożone z kamyków |
| Gotycki iluminowany rękopis (`05_gothic`) | parafia, zabytek, festiwal średniowieczny |
| Renesans, sfumato (`06_renaissance`) | muzeum, galeria, wykład o sztuce, spokój i klasyka |
| Impresjonizm (`08_impressionism`) | kwiaciarnia, ogród, agroturystyka, wiosna i lato |
| Postimpresjonizm, Van Gogh (`09_postimp`) | festiwal, noc muzeów, kawiarnia nocą, marka rzemieślnicza |
| Secesja, plakat Muchy (`10_nouveau`) | kosmetyki, perfumy, herbata, wino, opakowanie w ozdobnej ramie |
| Kubizm analityczny (`11_cubism`) | galeria, kawiarnia artystyczna, festiwal sztuki |
| Bauhaus (`12_bauhaus`) | architektura, wzornictwo, meble, szkoła projektowania |
| Pop-art (`13_pop`) | social, krótka promocja, wyprzedaż |
| Gra 8-bit (`14_8bit`) | zwiastun gry, aplikacji, turnieju e-sportowego |
| Wczesne CGI z ray tracingu (`15_raytrace`) | rocznica firmy IT, „tak wyglądał komputer w 1993”, muzeum techniki |
| Płaska ilustracja 2026 z ziarnem (`16_2026`) | puenta z humorem na koniec explainera albo reklamy aplikacji |
| Tusz xieyi (`17_ink`) | herbaciarnia, sztuki walki, kaligrafia, wystawa sztuki Azji |
| Klimt, złoty okres (`18_klimt`) | luksus: jubiler, perfumy, wino, czekolada premium |
| Munch, ekspresjonizm „Krzyku” (`19_munch`) | kampania społeczna: stres, wypalenie, lęk |
| Malowidła z Dunhuangu (`20_dunhuang`) | turystyka Jedwabnego Szlaku, sztuka buddyjska, muzeum |
| Kusama, nieskończone kropki (`21_kusama`) | moda, kosmetyki, sztuka współczesna, concept store |
| Konstruktywizm rosyjski (`22_constructivism`) | kampania z hasłem: apel, akcja społeczna, frekwencja |
| Dalí, surrealizm (`23_dali`) | czas: termin, oszczędzanie, ubezpieczenia, zegarki, prokrastynacja |
| Hopper, twarde światło (`24_hopper`) | nieruchomości, mieszkanie w słońcu, okna, hotel |
| Akwarelowe tła w stylu Ghibli (`25_ghibli`) | ciepłe kampanie: rodzina, dom, wieś, natura, piekarnia |
| Vaporwave, cyber-neon (`26_vaporwave`) | impreza klubowa, koncert synthwave, premiera singla |
| Komiks Jacka Kirby'ego (`27_kirby`) | premiera gry, komiksu, serialu, konwent fantastyki |
| Monet, „Nenufary” (`28_monet`) | spa, ogród, hotel nad wodą, spokojne tło pod lektora |
| Puentylizm Seurata (`29_seurat`) | muzeum, lekcja o sztuce albo o tym, jak oko miesza barwy |
| Wycinanki Matisse'a (`30_matisse`) | studio projektowe, kawiarnia, księgarnia, zajęcia plastyczne |
| Keith Haring (`31_haring`) | muzyka, taniec, festiwal, klub; wszystko do bitu |
| Światłocień Rembrandta (`32_rembrandt`) | muzeum, historia, archiwum, dokument, nastrojowo |
| Kreskówka „rubber hose” (`33_rubberhose`) | retro reklama: barber, kawiarnia, jazz, browar rzemieślniczy |
| Chiński teatr cieni (`34_shadowpuppet`) | Nowy Rok księżycowy, teatr lalek, muzeum etnograficzne |
| Światło Makoto Shinkaia (`35_shinkai`) | lifestyle, turystyka, nieruchomości z widokiem, uczelnia |
| Okres błękitny Picassa (`36_picasso_blue`) | tematy poważne: zdrowie psychiczne, żałoba, samotność |

## Zasady wyboru
- **Jeden styl na film**, chyba że film jest o zmianie (przegląd epok, przemiana jednego miejsca, podróż przez
  style): wtedy mechanizm z `metoda.md` (stały szkielet sceny, przejście-podpis, siatka bitów, kotwica i puenta).
- **Styl niesie temat, nie ozdabia go.** Pytanie kontrolne: czy widz bez lektora poczuje, o czym jest film?
  Luksus złotem Klimta tak, wyprzedaż złotem Klimta nie.
- **Czas renderu przed decyzją.** Ciężkie (karty podają ok. 90–170 ms na klatkę): `09_postimp`, `17_ink`,
  `19_munch`, `28_monet`, `29_seurat`, `34_shadowpuppet`. Policz klatki × czas i przy renderze dłuższym niż kilka
  minut powiedz właścicielowi przed startem albo weź lżejszy styl z tej samej rodziny.
- **Malarze żyjący i znaki towarowe:** styl opisuje gramatykę formy (pociągnięcie, paleta, motyw), nie podpis
  artysty. Bez nazwisk żyjących twórców w napisach i opisach filmu klienta (Kusama, Shinkai: „kropki”, „światło
  anime”); postacie, logotypy i bohaterowie z cudzych dzieł (Marvel, Ghibli) nie wchodzą do kadru.
- **Pion 9:16:** wszystkie style są poziome (1920×1080): `SKILL.md`, „Pion 9:16”.
- **Brak stylu na liście** (np. ukiyo-e, witraż, linoryt): zbuduj go metodą z `metoda.md` (rozdz. 10, „Nie ma
  wzoru”), zaczynając od karty najbliższego stylu.
