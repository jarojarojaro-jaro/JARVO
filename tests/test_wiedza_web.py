"""Frontend zakładki „Wiedza”: renderer Markdown (wiedza/web/src/20-markdown.js) uruchamiany w Node ze stubami htm/React:
tokenizacja linków [[…]], pogrubienia, kodu; zagnieżdżenie kończy się (regresja: wspólny lastIndex regexu zapętlał panel)."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")

STUB = """
const L = (pl, en) => pl;
const html = (strings, ...values) => ({ s: strings.join("|"), v: values });
const React = { createElement: () => null };
%s
const out = inline(process.argv[2], () => {}, "k");
const flat = (x) => Array.isArray(x) ? x.map(flat) : (typeof x === "string" ? x : (x && typeof x === "object" && "s" in x ? { tag: x.s.slice(0, 90), inner: (x.v || []).map(flat) } : typeof x));
console.log(JSON.stringify(flat(out)));
"""


@pytest.mark.skipif(not NODE, reason="brak node")
@pytest.mark.parametrize("tekst", [
    "**pogrubione i *kursywa w środku* dalej** oraz [[agenci/jarvo-web/_hub-web|Web]] i `kod` i [strona](https://jarvo.pl)",
    "**a** **b** *c* [[x]]",
    "bez znaczników",
])
def test_inline_konczy_sie_i_tokenizuje(tmp_path, tekst):
    src = (REPO / "wiedza" / "web" / "src" / "20-markdown.js").read_text(encoding="utf-8")
    skrypt = tmp_path / "t.js"
    skrypt.write_text(STUB % src, encoding="utf-8")
    r = subprocess.run([NODE, str(skrypt), tekst], capture_output=True, text=True, timeout=10)
    assert r.returncode == 0, r.stderr
    wynik = json.loads(r.stdout.strip())
    tekst_plaski = json.dumps(wynik, ensure_ascii=False)
    if "**" in tekst:
        assert "<strong" in tekst_plaski and "**" not in tekst_plaski.replace("**pogrubione", "")
    if "[[" in tekst:
        assert "twz-wikilink" in tekst_plaski
    if "`kod`" in tekst:
        assert "<code" in tekst_plaski
    if tekst == "bez znaczników":
        assert wynik == ["bez znaczników"]
