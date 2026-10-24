"""`python -m jarvo <polecenie>`: to samo co polecenie `jarvo` (jarvo/cli.py), np. w katalogu repo bez instalacji."""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
