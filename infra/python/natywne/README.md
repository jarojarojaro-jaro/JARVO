# Locki venvów instalacji natywnej

Locki z sumą sha256 każdego koła dla venvów Jarva poza obrazem ([NATYWNIE.md](../../../docs/NATYWNIE.md), P01, I31).
Który venv bierze który lock i na którym Pythonie, mówi sekcja `venvy` w
[`vendor/natywne.yaml`](../../../vendor/natywne.yaml). Suma każdego locka trafia do `vendor/natywne.lock.json`, więc
lock zmieniony bez `python scripts/natywne.py generuj` nie przejdzie `scripts/natywne.py sprawdz` ani testów.

| Plik | Venv | Wejście |
|---|---|---|
| `narzedzia.lock` | `narzedzia` (Python 3.12) | `wejscia/narzedzia.in`, `wejscia/narzedzia.wyklucz` (docopt ma tylko sdist) |
| `claude-seo.lock` | `claude-seo` (Python 3.12) | `wejscia/claude-seo.in` (requirements.txt claude-seo `e77e783`), `wejscia/claude-seo.ograniczenia` |
| `rembg.lock`, `mgaudio.lock`, `lemo-wake.lock` | dodatki (Python 3.12) | `wejscia/<venv>.in` |
| `docling-cpu.lock` | dodatek `docling` (Python 3.12) | `wejscia/docling-cpu.in`, z `--torch-backend cpu` |
| `../requirements-ocr.txt`, `../requirements-cad.txt`, `../requirements-manimgx.txt` | `ocr`, `cad` (3.12), `manimgx` (3.13) | locki obrazu bez zmian; `wejscia/ocr.in`, `cad.in`, `manimgx.in` z `ocr.wyklucz` i `cad.wyklucz` odtwarzają je co do linii i sumy, gdy `-o` wskazuje istniejący lock (uv zostawia przypięte wersje) |

`wejscia/py312/pyproject.toml` i `wejscia/py313/pyproject.toml` mają `required-environments` dla czterech platform
koła (win_amd64, macOS arm64, Linux x86_64 i aarch64). Dzięki temu compile kończy się błędem, gdy któraś paczka nie ma
koła dla którejś platformy. Windows arm64 bierze koła x64 (Python x64 w emulacji, I27).

Odtworzenie locka (uv 0.12.13, w czystym środowisku: uv czyta też `uv.toml` użytkownika i systemu), w tym katalogu:

    uv pip compile --project wejscia/py312 --universal --generate-hashes --python-version 3.12 \
      --only-binary :all: --exclude-newer <data> [--excludes wejscia/<venv>.wyklucz] \
      [--constraints wejscia/<venv>.ograniczenia] wejscia/<venv>.in -o <venv>.lock

Dokładne polecenie każdego locka jest w jego nagłówku. Potem trzeba wkleić nagłówek z powrotem, uruchomić
`python scripts/natywne.py generuj` i przejrzeć nowe wersje według [SOURCES.md](../../../docs/SOURCES.md).
Instalacja (instalator, c3 krok 6):

    uv pip install --no-config --no-deps --require-hashes --only-binary :all: --compile-bytecode -r <lock>

Na Windows z `UV_LINK_MODE=copy`, dla docling z `--torch-backend cpu` (pole `torch_backend` venvu).
