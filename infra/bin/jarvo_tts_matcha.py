"""Fonemizer polskiego lektora Matcha-TTS-PL v2: tekst → IPA (espeak-ng) → numery symboli modelu.

Licencja tego pliku: CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/), jak pierwowzór.
Port plików `english/polish_cleaners.py` i `english/polish_mixed_cleaners.py` z modelu
Matcha-TTS-PL v2 (machinekind, https://huggingface.co/machinekind/Matcha-TTS-PL, rewizja
93744740ae645648c003abb09e8c617d9c5e34cd, CC BY-SA 4.0) oraz poprawki z jego przeglądarkowego portu `cleaner.js`
(„iʲ” → „i” jak w danych treningowych, „?” przyklejony do słowa). Tablica symboli: `matcha/text/symbols.py`
z Matcha-TTS (Shivam Mehta i in., MIT; https://github.com/shivammehta25/Matcha-TTS) z dopisaną tyldą U+0303
(samogłoski nosowe), n_vocab 179 — jak `symbols.js` w Space machinekind/matcha-tts-pl-v2.

Zmiany względem pierwowzoru: biblioteka espeak-ng z koła `espeakng-loader` (to samo espeak-ng, którego misaki używa
dla lektora angielskiego; bez apt), backendy tworzone przy pierwszym użyciu, polskie skróty rozwija wcześniej
normalizator Jarvo (jarvo_tts_pl.py; lista z pierwowzoru zostaje tu jako druga linia), nieznane symbole pomijane
zamiast błędu. Słowa w {klamrach} czyta espeak-ng en-us (angielskie wstawki); bez klamer wszystko po polsku.
"""

from __future__ import annotations

import re

# --- tablica symboli (Matcha-TTS symbols.py + U+0303), id = indeks; podwójny apostrof: wygrywa ostatni, jak w Matcha
_PAD = "_"
_PUNCTUATION = ';:,.!?¡¿—…"«»“” '
_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
_LETTERS_IPA = ("ɑɐɒæɓʙβɔɕçɗɖðʤəɘɚɛɜɝɞɟʄɡɠɢʛɦɧħɥʜɨɪʝɭɬɫɮʟɱɯɰŋɳɲɴøɵɸθœɶʘɹɺɾɻʀʁɽʂʃʈʧʉʊʋⱱʌɣɤʍχʎʏʑʐʒʔʡʕʢǀǁǂǃˈˌːˑʼʴʰʱʲʷˠˤ˞"
                "↓↑→↗↘'̩'ᵻ̃")
SYMBOLE = [_PAD] + list(_PUNCTUATION) + list(_LETTERS) + list(_LETTERS_IPA)
SYMBOL_ID = {s: i for i, s in enumerate(SYMBOLE)}

_PL_WORD = "0-9a-ząćęłńóśźż"


def _abbr(k: str, v: str):
    """Regex dla skrótu: musi stać na granicy słowa. 'r.'/'w.' tylko po liczbie/liczbie rzymskiej
    (inaczej 'Piotr.' -> 'Piotroku')."""
    if k in ("r.", "w."):
        return re.compile(rf"(?<=[0-9ivx])\s?{re.escape(k)}"), f" {v}"
    tail = "" if k.endswith(".") else rf"(?![{_PL_WORD}])"
    return re.compile(rf"(?<![{_PL_WORD}]){re.escape(k)}{tail}"), v


_PL_ABBREV = [_abbr(k, v) for k, v in [
    ("np.", "na przykład"), ("tzn.", "to znaczy"), ("tj.", "to jest"), ("itd.", "i tak dalej"),
    ("itp.", "i tym podobne"), ("m.in.", "między innymi"), ("dr", "doktor"), ("prof.", "profesor"),
    ("inż.", "inżynier"), ("mgr", "magister"), ("ul.", "ulica"), ("al.", "aleja"), ("r.", "roku"), ("w.", "wieku"),
    ("godz.", "godzina"), ("min.", "minut"), ("św.", "święty"), ("nr", "numer"), ("tel.", "telefon"),
    ("zł", "złotych")]]


def _expand_pl_abbreviations(text: str) -> str:
    for rx, rep in _PL_ABBREV:
        text = rx.sub(rep, text)
    return text


def _collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _normalize_punct(text: str) -> str:
    text = re.sub(r"\s*(?:—|–| - )\s*", ", ", text).replace("…", "...")
    for c in "„”“\"«»":
        text = text.replace(c, "")
    return text


_BACKENDY: dict = {}


def _backend(jezyk: str):
    """EspeakBackend (phonemizer) na bibliotece espeak-ng z espeakng-loader; jeden na język, tworzony raz."""
    if jezyk not in _BACKENDY:
        import espeakng_loader  # type: ignore
        from phonemizer.backend import EspeakBackend  # type: ignore
        from phonemizer.backend.espeak.wrapper import EspeakWrapper  # type: ignore

        EspeakWrapper.set_library(espeakng_loader.get_library_path())
        EspeakWrapper.set_data_path(espeakng_loader.get_data_path())
        _BACKENDY[jezyk] = EspeakBackend(language=jezyk, preserve_punctuation=True, with_stress=True,
                                         words_mismatch="ignore", language_switch="remove-flags")
    return _BACKENDY[jezyk]


def _fon(jezyk: str, text: str) -> str:
    return _backend(jezyk).phonemize([text], strip=True, njobs=1)[0]


def _pl_phon(text: str) -> str:
    text = _expand_pl_abbreviations(_normalize_punct(text.lower()))
    # espeak-ng nowszy niż treningowy (1.50) pisze „iʲ” przed samogłoską; w danych treningowych tego nie ma
    return _fon("pl", text).replace("iʲ", "i") if text.strip() else ""


def _en_phon(text: str) -> str:
    return _fon("en-us", text).replace("ʲ", "")


_VOICELESS = ("p", "t", "k", "f", "s", "ʃ", "θ", "h", "tʃ", "ˈp", "ˈt", "ˈk", "ˈf", "ˈs", "ˈʃ", "ˈθ", "ˈh", "ˌp", "ˌt",
              "ˌk", "ˌf", "ˌs", "ˌh")


def _one_letter(w: str, next_ph: str) -> str:
    voiceless = next_ph.startswith(_VOICELESS)
    return {"w": "f" if voiceless else "v", "z": "s" if voiceless else "z", "i": "i", "a": "a", "o": "ɔ", "u": "u"}[w]


def _unstress(ph: str) -> str:
    """Polska końcówka doklejona do angielskiego słowa ({Slack}a) jest nieakcentowana."""
    head, _, rest = ph.partition(" ")
    return head.replace("ˈ", "").replace("ˌ", "") + (" " + rest if rest else "")


def fonemy(text: str) -> str:
    """Tekst (po normalizacji) → IPA jak w treningu: polski przez espeak-ng pl, {klamry} przez en-us."""
    text = re.sub(r"\s+\?", "?", text)            # „?” przy słowie, jak w tekstach treningowych (intonacja pytań)
    if "{" not in text:
        return _collapse_whitespace(_pl_phon(text))
    out, pos = "", 0
    for m in re.finditer(r"\{([^{}]+)\}", text):
        pl = text[pos:m.start()]
        prep = ""
        mm = re.search(r"(?:^|\s)([wzaiouWZAIOU])\s*$", pl)        # jednoliterowy przyimek przed angielskim słowem:
        if mm:                                                       # espeak czytałby go jako nazwę litery („w” → „vɨ”)
            prep, pl = mm.group(1).lower(), pl[:mm.start(1)]
        if pl.strip():
            glue = not pl[0].isspace() and out != ""
            ph = _pl_phon(pl)
            out += ("" if glue else " ") + (_unstress(ph) if glue else ph)
        en = _en_phon(m.group(1))
        if prep:
            out += " " + _one_letter(prep, en)
        glue = m.start() > 0 and not text[m.start() - 1].isspace() and out != ""
        out += ("" if glue else " ") + en
        pos = m.end()
    tail = text[pos:]
    if tail.strip():
        glue = not tail[0].isspace()
        ph = _pl_phon(tail)
        out += ("" if glue else " ") + (_unstress(ph) if glue else ph)
    return _collapse_whitespace(out)


def na_id(ipa: str) -> list[int]:
    """IPA → numery symboli przeplatane zerem (intersperse z Matcha); nieznane znaki pominięte."""
    ids = [SYMBOL_ID[c] for c in ipa if c in SYMBOL_ID]
    out = [0] * (2 * len(ids) + 1)
    out[1::2] = ids
    return out
