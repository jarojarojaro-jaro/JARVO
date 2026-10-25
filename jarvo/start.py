"""Launcher polecenia `jarvo` (docs/NATYWNIE.md, N01): `python -I -X utf8 <app>/jarvo/start.py <polecenie> ...`.

Tak wołają go `<root>\\bin\\jarvo.cmd` (Windows), `~/.local/bin/jarvo` (macOS, Linux), autostart nadzorcy i bootstrap.
Tryb izolowany (-I) pomija PYTHONPATH, PYTHONHOME i site-packages użytkownika, więc cudzy Python właściciela niczego
nie podmieni, ale nie dopisuje też katalogu skryptu do sys.path. Katalog kodu Jarva (rodzic katalogu jarvo/)
dopisujemy więc sami, na początek. -X utf8: wejście, wyjście i pliki w UTF-8 niezależnie od strony kodowej systemu.

Ścieżka kodu bez Path.resolve(): na Windows rozwinąłby krótką nazwę 8.3 (ASCII) do pełnej z polskimi znakami, a kod
Jarva w `<program>` ma ścieżkę ASCII (c1). Na Windows od pierwszej instrukcji NoDefaultCurrentDirectoryInExePath=1:
shutil.which i cmd.exe nie szukają programów w katalogu bieżącym (dziedziczą to procesy potomne).
"""
import os
import sys


def _uruchom() -> int:
    if os.name == "nt":
        os.environ["NoDefaultCurrentDirectoryInExePath"] = "1"
    app = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if app not in sys.path:
        sys.path.insert(0, app)
    from jarvo.cli import main
    return main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(_uruchom())
