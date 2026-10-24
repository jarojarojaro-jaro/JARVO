"""Jarvo natywnie (docs/NATYWNIE.md): instalator, nadzorca procesów i polecenie `jarvo` bez Dockera i WSL.

Pakiet działa na samej bibliotece standardowej Pythona: uruchamia go Python z python-build-standalone, zanim
powstanie środowisko Hermesa. Skrypty, które potrzebują YAML (build.py, fleetlib), wołamy Pythonem Hermesa.
"""

__all__ = ["sciezki", "srodowisko"]
