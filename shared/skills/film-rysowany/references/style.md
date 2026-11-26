# 21 stylów filmu rysowanego (silnikjava)

Styl to jedna linijka sceny: `new Storyboard({ theme: '<id>' })`. Fizyka ręki, lint i lektor działają tak samo
w każdym stylu, a scena z kolorami z palety (`ink`, `pen`, `teal`, `sky`, `ochre`, `coral`, `plum`) wygląda dobrze
w każdym. Stopklatki filmu-wzoru stylu: `rysowany.py wzor <id>`; kod wzoru: `@@TOOLS_DIR@@/silnikjava/examples/scenes/styles/<id>.js`,
tekst jego lektora: `@@TOOLS_DIR@@/silnikjava/examples/voice/<id>/script.md`. Własny styl: `docs/STYLE.md` silnika.

| id | Styl | Podłoże i kreska | Kolor | Pismo | W ręce | Do czego |
|---|---|---|---|---|---|---|
| `paper` | Papier (domyślny) | kremowy papier, pióro | kredka | Caveat, Caveat Brush | ołówek | uniwersalny, neutralny |
| `chalk` | Tablica kredowa | zielona tablica z kurzem i ramą, kreda z ziarnem | kolorowa kreda (rozjaśnia) | Kalam, Caveat Brush | kawałek kredy | lekcje, matematyka, „szkolne” objaśnienia |
| `blueprint` | Blueprint | granatowa kalka z siatką, rapidograf o stałej grubości | kreskowanie pod 45° | Architects Daughter | rapidograf | architektura systemów, inżynieria, produkt |
| `neon` | Neon (lightboard) | prawie czarna szyba, świecąca kreska z poświatą | półprzezroczysta poświata | Patrick Hand | pisak ze świecącą końcówką | technologia, AI, prezentacje |
| `notebook` | Zeszyt w kratkę | kratka 5 mm, margines, niebieski długopis, czerwony do poprawek | kredki, zakreślacze | Shadows Into Light Two | długopis | finanse osobiste, nauka, „wytłumacz jak na lekcji” |
| `watercolor` | Akwarela | papier akwarelowy, cienkopis w sepii | plama farby z rozlanym brzegiem | Amatic SC, Mynerve | cienkopis i pędzel | przyroda, podróże, opowieści |
| `comic` | Komiks | papier gazetowy, pędzelek z mocnym naciskiem, dymki | marker z rastrem kropek | Bangers, Shantell Sans | pisak pędzelkowy | ciekawostki, popularyzacja nauki, social media |
| `flipchart` | Flipchart | arkusz z bloku, gruby marker ze smugą filcu | marker szerokimi pasami | Lilita One, Sriracha | marker | warsztaty, sprzedaż, strategia, szkolenia |
| `kraft` | Papier pakowy | brązowy kraft z włóknami i taśmą, czarny cienkopis, biały żelopis | kredki, przez które przebija papier | Caveat Brush, Kalam | pisak, kredka | przepisy, kawiarnie, rękodzieło, marki „eko” |
| `sketch` | Szkic ołówkiem | szkicownik na spirali, grafit z ziarnem, blada druga linia | kreskowanie, jeden akcent koloru | Caveat | ołówek | fizyka, technika, „jak to działa” |
| `parchment` | Stara mapa | pergamin z plamami i przypalonymi brzegami, pióro gęsie (kreska blednie) | akwarelowe podkolorowanie | Grenze Gotisch, MedievalSharp | gęsie pióro | historia, bitwy, podróże |
| `woodcut` | Drzeworyt | papier czerpany, gruba rytowana kreska | równoległe nacięcia dłuta, czerń i czerwień | Alfa Slab One, Special Elite | dłuto | dawne techniki, rzemiosło, legendy |
| `cosmos` | Kosmos | nocne niebo z mgławicami i gwiazdami, pastelowa świecąca kreska | miękka plama dodająca światła | Exo 2, Comfortaa | świecący pisak | astronomia, fizyka, science fiction |
| `terminal` | Terminal CRT | kineskop z liniami ekranu, zielony fosfor | paski światła | VT323 | pióro świetlne | historia techniki, komputery, kosmos |
| `poster` | Plakat | papier drukarski z ziarnem, gruba równa kreska | płaska kryjąca farba, czerwień i czerń | Bebas Neue, Oswald | pisak pędzelkowy | historia XX wieku, manifesty, kampanie |
| `corkboard` | Tablica korkowa | korek w drewnianej ramie, karteczki, pinezki, czerwona nitka | karteczki zamalowane kryjąco | Kalam, Special Elite | marker | zagadki historii, śledztwa, analizy przyczyn |
| `sumi` | Tusz i pędzel | papier ryżowy, pędzel gruby w poprzek i cienki wzdłuż | laweowanie tuszem, czerwona pieczęć | Kaushan Script, Spectral | pędzel | przyroda, geografia, spokojne opowieści |
| `patent` | Rysunek patentowy | biały karton z ramką, cienki tusz kreślarski, odsyłacze, FIG. 1 | przekroje kreskowane pod 45° | Libre Baskerville, EB Garamond | rapidograf | technika, wynalazki, budowa maszyn |
| `pixel` | Pixel art | ekran automatu, kreska przyciągnięta do siatki 8 px | kratki zamalowane po kolei | Pixelify Sans | pikselowy ołówek | historia gier i komputerów |
| `charcoal` | Węgiel | szary papier Ingres, gruba ziarnista kreska | cienie roztarte palcem, sangwina | Cinzel, Spectral | patyk węgla | historia, katastrofy, poważne tematy |
| `iso` | Izometria | szkice przedmiotów w 3D: mocna sylwetka, blade detale, zasłonięte linie się nie rysują | jeden pomarańczowy akcent | IBM Plex Mono, Space Grotesk | ołówek | sprzęt, sieci, architektura systemów |
| `ascii` | ASCII | ręka rysuje kreski, filtr klatki zamienia je w znaki (- / \| \\, . : = + * # @) | kolor zostaje w znakach | JetBrains Mono | kursor-blok | historia komputerów, internet, kultura cyfrowa |

Krój bez polskich liter (dziś `Lilita One` we `flipchart`) pisze litery z ogonkiem następnym krojem stylu: na arkuszu
klatek sprawdź tytuł z ą, ę, ł. Kroje ładują się lokalnie (`/_lib/silnikjava/kroje/fonts.css`, google/fonts OFL),
bez sieci w czasie renderu.
