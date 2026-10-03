#!/usr/bin/env python3
"""Biblioteka dźwięków edytora HQ i Wideografa (CC0, lokalnie): pobranie, przygotowanie i sprawdzenie zgodności.

Efekty i podkłady muzyczne na licencji CC0 (Kenney.nl i Freesound z licencją CC0, bez popularnych piosenek)
leżą w hq/web/dzwieki/<kategoria>/<id>.mp3 razem z katalog.json (generowany). Edytor HQ pokazuje je w menu Audio
(Efekty, Muzyka) z odsłuchem, a Wideograf ma je w `projekt.py dzwieki` i `dodaj-dzwiek`. Dodanie kopiuje plik
obok filmu (<katalog filmu>/dzwieki/), więc projekt działa bez biblioteki i po jej zmianie.

    python3 scripts/dzwieki.py pobierz [--cache KAT]   # surowe pliki do pamięci podręcznej (sieć: kenney.nl, freesound.org)
    python3 scripts/dzwieki.py zbuduj [--cache KAT]    # ffmpeg: przycięcie ciszy, głośność, mp3, katalog.json
    python3 scripts/dzwieki.py sprawdz                 # pliki, sumy SHA-256 i katalog zgodne z DZWIEKI (test i CI)

`pobierz` przy każdym dźwięku z Freesound czyta jego stronę i odmawia, gdy licencja nie jest CC0. Bez klucza API:
Freesound daje bez logowania podgląd HQ (mp3 128 kb/s), a to wystarcza do krótkich efektów i podkładów.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "hq" / "web" / "dzwieki"
KATALOG = DIR / "katalog.json"
CACHE = ROOT / ".cache" / "dzwieki"
CC0 = "creativecommons.org/publicdomain/zero/1.0"
MUZYKA_MAX = 60.0      # podkład najwyżej minuta (wyciszenie na końcu)
EFEKT_MAX = 10.0

# paczki Kenney (CC0, https://kenney.nl/assets/<nazwa>): adres pliku zip z numerem wersji
KENNEY = {
    "casino-audio": "https://kenney.nl/media/pages/assets/casino-audio/2472606a04-1721639069/kenney_casino-audio.zip",
    "digital-audio": "https://kenney.nl/media/pages/assets/digital-audio/216eac4753-1677590265/kenney_digital-audio.zip",
    "impact-sounds": "https://kenney.nl/media/pages/assets/impact-sounds/87b4ddecda-1677589768/kenney_impact-sounds.zip",
    "interface-sounds": "https://kenney.nl/media/pages/assets/interface-sounds/fa43c1dd4d-1677589452/kenney_interface-sounds.zip",
    "music-jingles": "https://kenney.nl/media/pages/assets/music-jingles/f37e530b9e-1677590399/kenney_music-jingles.zip",
    "rpg-audio": "https://kenney.nl/media/pages/assets/rpg-audio/8e99002d76-1677590336/kenney_rpg-audio.zip",
    "sci-fi-sounds": "https://kenney.nl/media/pages/assets/sci-fi-sounds/6b296f9ecf-1677589334/kenney_sci-fi-sounds.zip",
    "ui-audio": "https://kenney.nl/media/pages/assets/ui-audio/490d233f68-1677590494/kenney_ui-audio.zip",
}

# klucz → nazwa po polsku, po angielsku; kolejność = kolejność w edytorze. "muzyka" to podkłady (zakładka Muzyka).
KATEGORIE = [
    ("przejscia", "Przejścia", "Transitions"), ("reakcje", "Reakcje", "Reactions"), ("pieniadze", "Pieniądze", "Money"),
    ("uderzenia", "Uderzenia", "Impacts"), ("akcja", "Akcja", "Action"), ("interfejs", "Interfejs", "Interface"),
    ("technika", "Technika", "Tech"), ("natura", "Natura", "Nature"), ("zwierzeta", "Zwierzęta", "Animals"),
    ("codzienne", "Codzienne", "Everyday"), ("zabawne", "Zabawne", "Cartoon"), ("gry", "Gry i retro", "Games & retro"),
    ("dzingle", "Dżingle", "Jingles"), ("muzyka", "Muzyka", "Music"),
]


def fs(num: int, autor: str) -> dict:
    return {"fs": num, "autor": autor}


def kn(paczka: str, plik: str) -> dict:
    return {"kenney": paczka, "plik": plik, "autor": "Kenney"}


# id (unikalne, nazwa pliku), kategoria, nazwa PL, nazwa EN, źródło
DZWIEKI: list[tuple[str, str, str, str, dict]] = [
    # przejścia
    ("whoosh", "przejscia", "Whoosh", "Whoosh", fs(60013, "qubodup")),
    ("whoosh-szybki", "przejscia", "Whoosh szybki", "Quick whoosh", fs(683101, "florianreichelt")),
    ("swoosh", "przejscia", "Swoosh", "Swoosh", fs(169867, "Halgrimm")),
    ("swoosh-przejscie", "przejscia", "Swoosh przejścia", "Transition swoosh", fs(632763, "adh.dreaming")),
    ("whoosh-sredni", "przejscia", "Whoosh średni", "Medium whoosh", fs(425706, "moogy73")),
    ("swoosh-dlugi", "przejscia", "Swoosh długi", "Long swoosh", fs(264777, "Shinplaster")),
    ("swoosh-wybuch", "przejscia", "Swoosh z wybuchem", "Swoosh explosion", fs(234555, "Electroviolence")),
    ("bicz", "przejscia", "Smagnięcie", "Whip", fs(346373, "denao270")),
    ("narastanie", "przejscia", "Narastanie", "Riser", fs(685256, "syntheffects")),
    ("narastanie-krotkie", "przejscia", "Narastanie krótkie", "Short riser", fs(561207, "Rizzard")),
    ("uderzenie-przejscia", "przejscia", "Uderzenie przejścia", "Transition hit", fs(648534, "AudioPapkin")),
    ("przewijanie", "przejscia", "Przewijanie taśmy", "Rewind", fs(178555, "richienoodles")),
    # reakcje
    ("oklaski", "reakcje", "Oklaski", "Applause", fs(277022, "Sandermotions")),
    ("wiwaty", "reakcje", "Wiwaty", "Cheer", fs(333404, "jayfrosting")),
    ("tlum-hura", "reakcje", "Tłum: hura", "Crowd cheer", fs(182571, "qubodup")),
    ("smiech", "reakcje", "Śmiech", "Laughing", fs(138112, "snakebarney")),
    ("smiech-oklaski", "reakcje", "Śmiech i oklaski", "Sitcom laugh", fs(371562, "Kinoton")),
    ("werble", "reakcje", "Werble", "Drum roll", fs(191718, "adriann")),
    ("werble-talerz", "reakcje", "Werble z puentą", "Rimshot", fs(440829, "tlwmdbt")),
    ("porazka", "reakcje", "Porażka (trąbka)", "Fail horn", fs(362206, "TaranP")),
    ("tadam", "reakcje", "Ta-dam", "Ta-da", fs(397355, "plasterbrain")),
    ("dobrze", "reakcje", "Dobrze", "Correct", fs(243701, "ertfelda")),
    ("sukces", "reakcje", "Sukces", "Success", fs(456965, "FunWithSound")),
    ("zle", "reakcje", "Źle (brzęczyk)", "Wrong buzzer", fs(700641, "Producing_RayLite")),
    ("zgrzyt-plyty", "reakcje", "Zgrzyt płyty", "Record scratch", fs(43404, "simkiott")),
    ("magia", "reakcje", "Magia", "Magic sparkle", fs(511485, "MLaudio")),
    ("osiagniecie", "reakcje", "Osiągnięcie", "Achievement", fs(715067, "SkySpeira")),
    # pieniądze
    ("kasa", "pieniadze", "Kasa fiskalna", "Cash register", fs(209578, "Zott820")),
    ("kasa-2", "pieniadze", "Kasa: cha-ching", "Cha-ching", fs(184438, "CapsLok")),
    ("liczenie-banknotow", "pieniadze", "Liczenie banknotów", "Banknote counter", fs(178097, "madvedj")),
    ("spadajace-monety", "pieniadze", "Spadające monety", "Coins dropping", fs(17502, "Jace")),
    ("moneta", "pieniadze", "Moneta", "Coin drop", fs(343462, "Rocotilos")),
    ("moneta-gra", "pieniadze", "Moneta z gry", "Money pickup", fs(163451, "LeMudCrab")),
    ("wygrana-automat", "pieniadze", "Wygrana w automacie", "Slot payout", fs(361346, "jack126guy")),
    ("monety-w-dloni", "pieniadze", "Monety w dłoni", "Coins in hand", kn("rpg-audio", "Audio/handleCoins.ogg")),
    ("monety-w-dloni-2", "pieniadze", "Monety w dłoni 2", "Coins in hand 2", kn("rpg-audio", "Audio/handleCoins2.ogg")),
    ("zetony", "pieniadze", "Żetony", "Chips stack", kn("casino-audio", "Audio/chips-stack-1.ogg")),
    ("zetony-2", "pieniadze", "Żetony 2", "Chips collide", kn("casino-audio", "Audio/chips-collide-1.ogg")),
    ("skaner", "pieniadze", "Skaner w sklepie", "Store scanner", fs(144418, "zerolagtime")),
    # uderzenia
    ("boom-kinowy", "uderzenia", "Boom kinowy", "Cinematic boom", fs(201571, "Julien_Matthey")),
    ("uderzenie-duze", "uderzenia", "Duże uderzenie", "Big impact", fs(430977, "AudioPapkin")),
    ("uderzenie-niskie", "uderzenia", "Niskie uderzenie", "Low impact", fs(430978, "AudioPapkin")),
    ("bas", "uderzenia", "Zejście basu", "Sub drop", fs(59540, "uzerx")),
    ("cios-boks", "uderzenia", "Cios bokserski", "Boxing punch", fs(348244, "newagesoup")),
    ("cios", "uderzenia", "Cios", "Punch", kn("impact-sounds", "Audio/impactPunch_heavy_000.ogg")),
    ("cios-lekki", "uderzenia", "Cios lekki", "Light punch", kn("impact-sounds", "Audio/impactPunch_medium_000.ogg")),
    ("metal", "uderzenia", "Metal", "Metal hit", kn("impact-sounds", "Audio/impactMetal_heavy_000.ogg")),
    ("drewno", "uderzenia", "Drewno", "Wood hit", kn("impact-sounds", "Audio/impactWood_heavy_000.ogg")),
    ("szklo", "uderzenia", "Szkło", "Glass hit", kn("impact-sounds", "Audio/impactGlass_heavy_000.ogg")),
    ("dzwon", "uderzenia", "Dzwon", "Bell hit", kn("impact-sounds", "Audio/impactBell_heavy_000.ogg")),
    ("miekkie", "uderzenia", "Miękkie uderzenie", "Soft hit", kn("impact-sounds", "Audio/impactSoft_heavy_000.ogg")),
    ("talerz", "uderzenia", "Talerz", "Plate hit", kn("impact-sounds", "Audio/impactPlate_heavy_000.ogg")),
    ("tluczone-szklo", "uderzenia", "Tłuczone szkło", "Glass break", fs(141563, "avrahamy")),
    # akcja
    ("strzal-pistolet", "akcja", "Strzał z pistoletu", "Pistol shot", fs(427592, "michorvath")),
    ("strzal-strzelba", "akcja", "Strzał ze strzelby", "Shotgun", fs(427595, "michorvath")),
    ("strzal", "akcja", "Strzał", "Gunshot", fs(166191, "ShawnyBoy")),
    ("seria", "akcja", "Seria z karabinu", "Machine gun", fs(165394, "ShawnyBoy")),
    ("wybuch", "akcja", "Wybuch", "Explosion", kn("sci-fi-sounds", "Audio/explosionCrunch_000.ogg")),
    ("wybuch-2", "akcja", "Wybuch 2", "Explosion 2", kn("sci-fi-sounds", "Audio/explosionCrunch_002.ogg")),
    ("wybuch-gleboki", "akcja", "Wybuch głęboki", "Deep explosion", kn("sci-fi-sounds", "Audio/lowFrequency_explosion_000.ogg")),
    ("rakieta", "akcja", "Rakieta", "Rocket", fs(36847, "EcoDTR")),
    ("laser-duzy", "akcja", "Laser duży", "Large laser", kn("sci-fi-sounds", "Audio/laserLarge_000.ogg")),
    ("laser-maly", "akcja", "Laser mały", "Small laser", kn("sci-fi-sounds", "Audio/laserSmall_000.ogg")),
    ("laser-retro", "akcja", "Laser retro", "Retro laser", kn("sci-fi-sounds", "Audio/laserRetro_000.ogg")),
    ("pole-silowe", "akcja", "Pole siłowe", "Force field", kn("sci-fi-sounds", "Audio/forceField_000.ogg")),
    ("noz", "akcja", "Cięcie nożem", "Knife slice", kn("rpg-audio", "Audio/knifeSlice.ogg")),
    # interfejs
    ("klik", "interfejs", "Klik", "Click", kn("interface-sounds", "Audio/click_001.ogg")),
    ("klik-2", "interfejs", "Klik 2", "Click 2", kn("interface-sounds", "Audio/click_003.ogg")),
    ("klik-myszy", "interfejs", "Klik myszy", "Mouse click", kn("ui-audio", "Audio/mouseclick1.ogg")),
    ("wybor", "interfejs", "Wybór", "Select", kn("interface-sounds", "Audio/select_001.ogg")),
    ("potwierdzenie", "interfejs", "Potwierdzenie", "Confirmation", kn("interface-sounds", "Audio/confirmation_001.ogg")),
    ("blad", "interfejs", "Błąd", "Error", kn("interface-sounds", "Audio/error_001.ogg")),
    ("pytanie", "interfejs", "Pytanie", "Question", kn("interface-sounds", "Audio/question_001.ogg")),
    ("przelacznik", "interfejs", "Przełącznik", "Switch", kn("interface-sounds", "Audio/switch_001.ogg")),
    ("szarpniecie", "interfejs", "Szarpnięcie struny", "Pluck", kn("interface-sounds", "Audio/pluck_001.ogg")),
    ("upuszczenie", "interfejs", "Upuszczenie", "Drop", kn("interface-sounds", "Audio/drop_002.ogg")),
    ("ding-szklany", "interfejs", "Ding szklany", "Glass ding", kn("interface-sounds", "Audio/glass_001.ogg")),
    ("bong", "interfejs", "Bong", "Bong", kn("interface-sounds", "Audio/bong_001.ogg")),
    ("tik", "interfejs", "Tik", "Tick", kn("interface-sounds", "Audio/tick_001.ogg")),
    ("otworz", "interfejs", "Otwórz", "Open", kn("interface-sounds", "Audio/maximize_001.ogg")),
    ("zamknij", "interfejs", "Zamknij", "Close", kn("interface-sounds", "Audio/minimize_001.ogg")),
    ("powiadomienie", "interfejs", "Powiadomienie", "Notification", fs(380482, "Jofae")),
    ("wiadomosc", "interfejs", "Nowa wiadomość", "Message received", fs(760369, "Froey_")),
    ("pop", "interfejs", "Pop", "Pop", fs(401542, "ConarB13")),
    ("plop", "interfejs", "Plop", "Plop", fs(447910, "Breviceps")),
    # technika
    ("migawka", "technika", "Migawka aparatu", "Camera shutter", fs(170229, "roachpowder")),
    ("migawka-telefon", "technika", "Zdjęcie telefonem", "Phone camera", fs(431588, "pooky1")),
    ("lustrzanka", "technika", "Lustrzanka", "DSLR shutter", fs(61059, "xef6")),
    ("klawiatura", "technika", "Pisanie na klawiaturze", "Keyboard typing", fs(447909, "Breviceps")),
    ("klawiatura-mechaniczna", "technika", "Klawiatura mechaniczna", "Mechanical keyboard", fs(348239, "newagesoup")),
    ("pisanie-cyfrowe", "technika", "Pisanie cyfrowe", "Digital typing", fs(416777, "Sky_Motion")),
    ("dane", "technika", "Odsłonięcie danych", "Data reveal", fs(511418, "Sky_Motion")),
    ("wibracja", "technika", "Wibracja telefonu", "Phone vibration", fs(515295, "Breviceps")),
    ("bip", "technika", "Bip", "Beep", fs(250104, "phatcorns")),
    ("glitch", "technika", "Glitch", "Glitch", fs(332711, "AmicaSys")),
    ("glitch-vhs", "technika", "Glitch VHS", "VHS glitch", fs(264935, "Sassaby")),
    ("komputer", "technika", "Szum komputera", "Computer noise", kn("sci-fi-sounds", "Audio/computerNoise_000.ogg")),
    # natura
    ("plusk", "natura", "Plusk", "Splash", fs(9508, "petenice")),
    ("plusk-duzy", "natura", "Duży plusk", "Big splash", fs(442773, "qubodup")),
    ("kropla", "natura", "Kropla", "Water drop", fs(371274, "Mafon2")),
    ("deszcz", "natura", "Deszcz", "Light rain", fs(137022, "Jeffreys2")),
    ("duze-krople", "natura", "Duże krople", "Big raindrops", fs(396483, "macdaddyno1")),
    ("wiatr", "natura", "Wiatr", "Wind gust", fs(146932, "crashoverride6")),
    ("wiatr-krotki", "natura", "Wiatr krótki", "Short wind", fs(104078, "RutgerMuller")),
    ("grzmot", "natura", "Grzmot", "Thunder", fs(193170, "netaj")),
    ("grzmot-krotki", "natura", "Grzmot krótki", "Short thunder", fs(475094, "Josh74000MC")),
    ("ptaki", "natura", "Ptaki", "Birds chirping", fs(182502, "swiftoid")),
    ("ptaszarnia", "natura", "Wiele ptaków", "Birds in aviary", fs(204341, "bunting")),
    # zwierzęta
    ("kot", "zwierzeta", "Kot", "Cat meow", fs(110011, "tuberatanka")),
    ("kot-2", "zwierzeta", "Kot krótko", "Short meow", fs(412017, "skymary")),
    ("pies", "zwierzeta", "Pies", "Dog bark", fs(277058, "kwahmah_02")),
    ("piesek", "zwierzeta", "Mały pies", "Small dog bark", fs(163459, "LittleBigSounds")),
    ("mewy", "zwierzeta", "Mewy", "Seagulls", fs(166703, "Snapper4298")),
    # codzienne
    ("pukanie", "codzienne", "Pukanie", "Door knock", fs(268500, "wjtaylor")),
    ("walenie-w-drzwi", "codzienne", "Walenie w drzwi", "Angry knocking", fs(194365, "Macif")),
    ("dzwonek-do-drzwi", "codzienne", "Dzwonek do drzwi", "Doorbell", fs(361564, "MatthewWong")),
    ("drzwi-otwarcie", "codzienne", "Otwarcie drzwi", "Door open", kn("rpg-audio", "Audio/doorOpen_1.ogg")),
    ("drzwi-zamkniecie", "codzienne", "Zamknięcie drzwi", "Door close", kn("rpg-audio", "Audio/doorClose_1.ogg")),
    ("skrzypienie", "codzienne", "Skrzypienie", "Creak", kn("rpg-audio", "Audio/creak1.ogg")),
    ("krok-beton", "codzienne", "Krok na betonie", "Footstep concrete", kn("impact-sounds", "Audio/footstep_concrete_000.ogg")),
    ("krok-drewno", "codzienne", "Krok na drewnie", "Footstep wood", kn("impact-sounds", "Audio/footstep_wood_000.ogg")),
    ("kartka", "codzienne", "Kartka", "Page flip", kn("rpg-audio", "Audio/bookFlip1.ogg")),
    ("ksiazka", "codzienne", "Zamknięcie książki", "Book close", kn("rpg-audio", "Audio/bookClose.ogg")),
    ("zegar", "codzienne", "Zegar", "Clock ticking", fs(130388, "olver")),
    ("stoper", "codzienne", "Stoper", "Stopwatch", fs(275802, "DavidJGurney")),
    ("budzik", "codzienne", "Budzik", "Alarm clock", fs(102435, "tuberatanka")),
    ("dzwonek", "codzienne", "Dzwonek", "Bell ding", fs(611113, "5ro4")),
    ("ding-kuchenka", "codzienne", "Ding kuchenki", "Oven ding", fs(265012, "sethlind")),
    ("klakson", "codzienne", "Klakson", "Car horn", fs(434878, "MicktheMicGuy")),
    ("serce", "codzienne", "Bicie serca", "Heartbeat", fs(22416, "Lunardrive")),
    # zabawne
    ("boing", "zabawne", "Boing", "Boing", fs(540790, "magnuswaker")),
    ("odbicie", "zabawne", "Odbicie", "Bounce", fs(383240, "Jofae")),
    ("skok", "zabawne", "Skok", "Cute jump", fs(618961, "Hemplock")),
    ("skoki-anime", "zabawne", "Skoki jak z anime", "Anime jumps", fs(396196, "plasterbrain")),
    ("bum-kreskowka", "zabawne", "Bum z kreskówki", "Cartoon hit", fs(209771, "Johnnyfarmer")),
    ("pyk", "zabawne", "Pyk", "Cartoon pop", fs(221091, "AlaskaRobotics")),
    ("sluz", "zabawne", "Śluz", "Slime", kn("sci-fi-sounds", "Audio/slime_000.ogg")),
    # gry i retro
    ("power-up", "gry", "Power-up", "Power-up", kn("digital-audio", "Audio/powerUp1.ogg")),
    ("power-up-2", "gry", "Power-up 2", "Power-up 2", kn("digital-audio", "Audio/powerUp5.ogg")),
    ("wygrana-gra", "gry", "Wygrana", "Game success", fs(242501, "GabrielAraujo")),
    ("skok-retro", "gry", "Skok retro", "Retro jump", kn("digital-audio", "Audio/phaseJump1.ogg")),
    ("zap", "gry", "Zap", "Zap", kn("digital-audio", "Audio/zap1.ogg")),
    ("trzy-tony", "gry", "Trzy tony", "Three tone", kn("digital-audio", "Audio/threeTone1.ogg")),
    ("w-gore", "gry", "W górę", "High up", kn("digital-audio", "Audio/highUp.ogg")),
    ("w-dol", "gry", "W dół", "Low down", kn("digital-audio", "Audio/lowDown.ogg")),
    ("pep", "gry", "Pep", "Pep", kn("digital-audio", "Audio/pepSound1.ogg")),
    ("laser-gra", "gry", "Laser z gry", "Game laser", kn("digital-audio", "Audio/laser1.ogg")),
    # dżingle (krótkie melodie)
    ("dzingiel-hit", "dzingle", "Dżingiel: hit", "Jingle: hit", kn("music-jingles", "Audio/Hit jingles/jingles_HIT00.ogg")),
    ("dzingiel-hit-2", "dzingle", "Dżingiel: hit 2", "Jingle: hit 2", kn("music-jingles", "Audio/Hit jingles/jingles_HIT05.ogg")),
    ("dzingiel-8bit", "dzingle", "Dżingiel: 8-bit", "Jingle: 8-bit", kn("music-jingles", "Audio/8-Bit jingles/jingles_NES00.ogg")),
    ("dzingiel-8bit-2", "dzingle", "Dżingiel: 8-bit 2", "Jingle: 8-bit 2", kn("music-jingles", "Audio/8-Bit jingles/jingles_NES03.ogg")),
    ("dzingiel-pizzicato", "dzingle", "Dżingiel: pizzicato", "Jingle: pizzicato", kn("music-jingles", "Audio/Pizzicato jingles/jingles_PIZZI00.ogg")),
    ("dzingiel-pizzicato-2", "dzingle", "Dżingiel: pizzicato 2", "Jingle: pizzicato 2", kn("music-jingles", "Audio/Pizzicato jingles/jingles_PIZZI04.ogg")),
    ("dzingiel-saksofon", "dzingle", "Dżingiel: saksofon", "Jingle: sax", kn("music-jingles", "Audio/Sax jingles/jingles_SAX00.ogg")),
    ("dzingiel-saksofon-2", "dzingle", "Dżingiel: saksofon 2", "Jingle: sax 2", kn("music-jingles", "Audio/Sax jingles/jingles_SAX03.ogg")),
    ("dzingiel-steel", "dzingle", "Dżingiel: steel drum", "Jingle: steel drum", kn("music-jingles", "Audio/Steel jingles/jingles_STEEL00.ogg")),
    ("dzingiel-steel-2", "dzingle", "Dżingiel: steel drum 2", "Jingle: steel drum 2", kn("music-jingles", "Audio/Steel jingles/jingles_STEEL02.ogg")),
    # muzyka (podkłady, najwyżej minuta)
    ("muzyka-energia", "muzyka", "Energia", "Upbeat", fs(696111, "Seth_Makes_Sounds")),
    ("muzyka-pozytywna", "muzyka", "Pozytywnie", "Upbeat loop", fs(512340, "mistermender")),
    ("muzyka-hiphop", "muzyka", "Hip-hop na luzie", "Chill hip hop", fs(264081, "klaudux")),
    ("muzyka-spokojna", "muzyka", "Spokojnie", "Calm background", fs(671900, "Bertsz")),
    ("muzyka-gitara", "muzyka", "Gitara folk", "Folk guitar", fs(246315, "Dvideoguy")),
    ("muzyka-lofi", "muzyka", "Lo-fi gitara", "Lo-fi guitar", fs(629150, "holizna")),
    ("muzyka-reklama", "muzyka", "Reklama", "Advertisement", fs(561190, "code_box")),
    ("muzyka-napiecie", "muzyka", "Napięcie", "Suspense", fs(387223, "awrmacd")),
    ("muzyka-8bit", "muzyka", "8-bit przygoda", "8-bit adventure", fs(240376, "edtijo")),
]


def zrodlo_url(z: dict) -> str:
    if "fs" in z:
        return f"https://freesound.org/people/{z['autor']}/sounds/{z['fs']}/"
    return f"https://kenney.nl/assets/{z['kenney']}"


def plik_wzgl(d: tuple) -> str:
    return f"{d[1]}/{d[0]}.mp3"


# ---------------------------------------------------------------- pobranie (sieć)

def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Jarvo/1.0 (+https://github.com/jarojarojaro-jaro/JARVO)"})
    with urllib.request.urlopen(req, timeout=60) as r:   # noqa: S310 - stałe adresy z listy powyżej
        return r.read()


def podglad_fs(strona: str, num: int) -> str:
    """Adres podglądu HQ (mp3) ze strony dźwięku Freesound; strona musi wskazywać licencję CC0."""
    if CC0 not in strona:
        raise SystemExit(f"Freesound {num}: licencja inna niż CC0, nie bierzemy")
    m = re.search(rf'https://cdn\.freesound\.org/previews/\d+/{num}_\d+-lq\.mp3', strona)
    if not m:
        raise SystemExit(f"Freesound {num}: brak adresu podglądu na stronie")
    return m.group(0).replace("-lq.mp3", "-hq.mp3")


def pobierz(cache: Path) -> int:
    cache.mkdir(parents=True, exist_ok=True)
    for paczka in sorted({d[4]["kenney"] for d in DZWIEKI if "kenney" in d[4]}):
        z = cache / f"kenney_{paczka}.zip"
        if not z.exists():
            z.write_bytes(_get(KENNEY[paczka]))
            print(f"pobrano paczkę Kenney {paczka}")
    for d in DZWIEKI:
        z = d[4]
        if "fs" not in z:
            continue
        dest = cache / f"fs_{z['fs']}.mp3"
        if dest.exists():
            continue
        strona = _get(zrodlo_url(z)).decode("utf-8", "replace")
        dest.write_bytes(_get(podglad_fs(strona, z["fs"])))
        print(f"pobrano Freesound {z['fs']} ({d[0]})")
    return 0


# ---------------------------------------------------------------- przygotowanie (ffmpeg)

def _ff(*args: str) -> str:
    r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit((r.stderr.strip().splitlines() or ["ffmpeg: błąd"])[-1])
    return r.stderr


def poziomy(path: Path, af: str) -> tuple[float, float]:
    """(średnia, szczyt) w dB po filtrze `af` (volumedetect)."""
    log = _ff("-i", str(path), "-af", f"{af},volumedetect", "-f", "null", "-")
    mean = float(re.search(r"mean_volume: (-?[\d.]+) dB", log).group(1))
    peak = float(re.search(r"max_volume: (-?[\d.]+) dB", log).group(1))
    return mean, peak


def filtr(muzyka: bool) -> str:
    """Bez ciszy na początku (efekt gra od razu tam, gdzie go postawisz) i na końcu, najwyżej EFEKT_MAX / MUZYKA_MAX."""
    cisza = "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.01"
    if muzyka:
        return f"{cisza},atrim=0:{MUZYKA_MAX}"
    return f"{cisza},areverse,{cisza},areverse,atrim=0:{EFEKT_MAX}"


def przygotuj(src: Path, dest: Path, muzyka: bool) -> None:
    """Głośność: efekt ze szczytem −1 dBFS, podkład ze średnią −20 dB (szczyt najwyżej −1 dBFS); podkład dłuższy
    niż minuta dostaje 2 s wyciszenia na końcu. mp3 44,1 kHz: efekty VBR (mono zostaje mono), muzyka 96 kb/s."""
    af = filtr(muzyka)
    mean, peak = poziomy(src, af)
    gain = min(-1.0 - peak, (-20.0 - mean) if muzyka else 99.0)
    chain = f"{af},volume={gain:.2f}dB"
    if muzyka and dlugosc(src) > MUZYKA_MAX:
        chain += f",afade=t=out:st={MUZYKA_MAX - 2:.2f}:d=2"
    dest.parent.mkdir(parents=True, exist_ok=True)
    enc = ["-b:a", "96k"] if muzyka else ["-q:a", "6"]
    kanaly = "2" if muzyka or not _mono(src) else "1"
    _ff("-y", "-i", str(src), "-af", chain, "-ar", "44100", "-ac", kanaly, "-map_metadata", "-1",
        "-c:a", "libmp3lame", *enc, "-write_xing", "1", str(dest))


def _probe(path: Path) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=channels", "-of", "json", str(path)],
                       capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def dlugosc(path: Path) -> float:
    return float(_probe(path)["format"]["duration"])


def _mono(path: Path) -> bool:
    return all(s.get("channels") == 1 for s in _probe(path).get("streams") or [])


def zbuduj(cache: Path) -> int:
    if not shutil.which("ffmpeg"):
        raise SystemExit("brak ffmpeg (zbuduj w kontenerze jarvo-hermes albo z ffmpeg w PATH)")
    paczki = {p: zipfile.ZipFile(cache / f"kenney_{p}.zip") for p in {d[4]["kenney"] for d in DZWIEKI if "kenney" in d[4]}}
    wpisy = []
    with tempfile.TemporaryDirectory() as tmp:
        for d in DZWIEKI:
            id_, kat, nazwa, en, z = d
            if "fs" in z:
                src = cache / f"fs_{z['fs']}.mp3"
            else:
                src = Path(tmp) / f"{id_}{Path(z['plik']).suffix}"
                src.write_bytes(paczki[z["kenney"]].read(z["plik"]))
            dest = DIR / plik_wzgl(d)
            przygotuj(src, dest, kat == "muzyka")
            wpisy.append(wpis(d, dest))
            print(f"{plik_wzgl(d)}: {wpisy[-1]['dl']:.2f} s, {dest.stat().st_size // 1024} KB")
    for stary in DIR.glob("*/*.mp3"):
        if stary.relative_to(DIR).as_posix() not in {plik_wzgl(d) for d in DZWIEKI}:
            stary.unlink()
    KATALOG.write_text(json.dumps(katalog(wpisy), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (DIR / "LICENCJE.md").write_text(licencje(), encoding="utf-8")
    return sprawdz()


def wpis(d: tuple, path: Path) -> dict:
    id_, kat, nazwa, en, z = d
    return {"id": id_, "kat": kat, "nazwa": nazwa, "en": en, "plik": plik_wzgl(d), "dl": round(dlugosc(path), 3),
            "autor": z["autor"], "zrodlo": zrodlo_url(z), "licencja": "CC0-1.0",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def katalog(wpisy: list[dict]) -> dict:
    return {"wersja": 1, "opis": "Biblioteka dźwięków CC0 (scripts/dzwieki.py). Plik generowany.",
            "kategorie": [{"id": k, "nazwa": n, "en": e, "muzyka": k == "muzyka"} for k, n, e in KATEGORIE],
            "dzwieki": wpisy}


def licencje() -> str:
    wiersze = [f"| `{plik_wzgl(d)}` | {d[2]} | [{d[4]['autor']}]({zrodlo_url(d[4])}) |" for d in DZWIEKI]
    return ("# Licencje dźwięków\n\nWszystkie pliki w tym katalogu są na licencji **CC0 1.0** (domena publiczna,\n"
            "https://creativecommons.org/publicdomain/zero/1.0/): wolno ich używać w filmach, także komercyjnie,\n"
            "bez podawania autora. Autorów wymieniamy z wdzięczności. Plik generowany: `python3 scripts/dzwieki.py zbuduj`.\n\n"
            "| Plik | Nazwa | Autor i źródło |\n|---|---|---|\n" + "\n".join(wiersze) + "\n")


# ---------------------------------------------------------------- sprawdzenie (bez sieci i ffmpeg)

def bledy() -> list[str]:
    out = []
    ids = [d[0] for d in DZWIEKI]
    if len(ids) != len(set(ids)):
        out.append("powtórzone id w DZWIEKI")
    kats = {k for k, *_ in KATEGORIE}
    out += [f"{d[0]}: nieznana kategoria {d[1]}" for d in DZWIEKI if d[1] not in kats]
    out += [f"{d[0]}: id tylko z małych liter, cyfr i „-”" for d in DZWIEKI if not re.fullmatch(r"[a-z0-9-]+", d[0])]
    out += [f"{d[0]}: paczka Kenney spoza KENNEY" for d in DZWIEKI if "kenney" in d[4] and d[4]["kenney"] not in KENNEY]
    if not KATALOG.is_file():
        return out + ["brak katalog.json (python3 scripts/dzwieki.py zbuduj)"]
    kat = json.loads(KATALOG.read_text(encoding="utf-8"))
    wpisy = {w["id"]: w for w in kat.get("dzwieki") or []}
    if [w["id"] for w in kat.get("dzwieki") or []] != ids:
        out.append("katalog.json ma inne dźwięki albo kolejność niż DZWIEKI (zbuduj)")
    if [c["id"] for c in kat.get("kategorie") or []] != [k for k, *_ in KATEGORIE]:
        out.append("katalog.json ma inne kategorie niż KATEGORIE (zbuduj)")
    for d in DZWIEKI:
        w = wpisy.get(d[0])
        if not w:
            continue
        if (w["kat"], w["nazwa"], w["en"], w["plik"], w["zrodlo"], w["licencja"]) != (d[1], d[2], d[3], plik_wzgl(d), zrodlo_url(d[4]), "CC0-1.0"):
            out.append(f"{d[0]}: wpis w katalog.json niezgodny z DZWIEKI (zbuduj)")
        p = DIR / plik_wzgl(d)
        if not p.is_file():
            out.append(f"brak pliku {plik_wzgl(d)}")
        elif hashlib.sha256(p.read_bytes()).hexdigest() != w.get("sha256"):
            out.append(f"suma SHA-256 {plik_wzgl(d)} niezgodna z katalog.json")
        limit = MUZYKA_MAX if d[1] == "muzyka" else EFEKT_MAX
        if not 0 < float(w.get("dl") or 0) <= limit + 0.1:
            out.append(f"{d[0]}: długość {w.get('dl')} s poza 0–{limit:.0f} s")
    zbedne = sorted({p.relative_to(DIR).as_posix() for p in DIR.glob("*/*.mp3")} - {plik_wzgl(d) for d in DZWIEKI})
    if zbedne:
        out.append(f"pliki spoza DZWIEKI: {', '.join(zbedne)}")
    lic = DIR / "LICENCJE.md"
    if not lic.is_file() or lic.read_text(encoding="utf-8") != licencje():
        out.append("LICENCJE.md niezgodny z DZWIEKI (zbuduj)")
    return out


def sprawdz() -> int:
    err = bledy()
    for e in err:
        print(f"BŁĄD: {e}")
    if not err:
        efekty = sum(1 for d in DZWIEKI if d[1] != "muzyka")
        rozmiar = sum(p.stat().st_size for p in DIR.glob("*/*.mp3")) / 2**20
        print(f"OK: {efekty} efektów i {len(DZWIEKI) - efekty} podkładów w {len(KATEGORIE)} kategoriach, {rozmiar:.1f} MB")
    return 1 if err else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", nargs="?", default="sprawdz", choices=["pobierz", "zbuduj", "sprawdz"])
    ap.add_argument("--cache", type=Path, default=CACHE, help="surowe pliki (domyślnie .cache/dzwieki w repo)")
    a = ap.parse_args(argv)
    if a.cmd == "pobierz":
        return pobierz(a.cache)
    if a.cmd == "zbuduj":
        return zbuduj(a.cache)
    return sprawdz()


if __name__ == "__main__":
    sys.exit(main())
