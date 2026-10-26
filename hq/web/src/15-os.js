// Oś czasu i reduktory zdarzeń (czyste, testy node w tests/test_hq_front.py): lista wątków, strony osi (scalanie po
// stałym `id` pozycji), przebiegi ze strumienia (delty i kroki tylko po kursorze migawki), przebiegi z odpowiedzi
// zapisów (bez gubienia tekstu ze strumienia), widok osi (kroki zwinięte w trybie Prosty, pozycje trwającej tury
// schowane w żywym dymku, wiadomości w drodze), „Nowe od tąd”, zgoda (ryzyko, wybory) i klasa błędu przebiegu.
// `Pisanie`: czyste pomocniki kompozytora (adresat wiadomości, podpowiedzi wzmianek, klucz wysyłki).

const Os = (() => {
  const KONCOWE = new Set(["gotowe", "blad", "zatrzymane", "przerwane", "zgubione", "anulowane", "wlaczony"]);
  const PONOWIALNE = new Set(["blad", "przerwane", "zgubione", "zatrzymane"]);
  // Stop: przebiegi z turą u bramy (i wysyłane: stop zaraz po przyjęciu); drugi Stop na „zatrzymywanie” ponawia
  const DO_ZATRZYMANIA = new Set(["wysylanie", "przyjety", "pracuje", "czeka_na_ture", "czeka_na_zgode", "zatrzymywanie"]);
  const czesci = (k) => { const s = String(k || ""), i = s.lastIndexOf("."); return i <= 0 ? null : [s.slice(0, i), Number(s.slice(i + 1))]; };
  // > 0: kursor `a` późniejszy niż `b`. Inna epoka (restart serwera) = późniejszy; brak `b` = późniejszy.
  function porownaj(a, b) {
    const x = czesci(a), y = czesci(b);
    if (!x) return -1;
    if (!y || x[0] !== y[0]) return 1;
    return x[1] - y[1];
  }

  // ------------------------------------------------------------------------------------------- lista wątków
  const FILTRY = {
    rozmowy: (w) => !w.usuniety_at && !w.archiwum && w.rodzaj !== "test",
    przypiete: (w) => !w.usuniety_at && !w.archiwum && !!w.przypiety,
    archiwum: (w) => !w.usuniety_at && !!w.archiwum,
    kosz: (w) => !!w.usuniety_at,
  };
  const klucz = (w) => `w:${w.id}`;
  function sortuj(lista) {
    const wg = lista.wg_klucza, przypiete = lista.filtr === "rozmowy";
    const porzadek = Object.keys(wg).sort((a, b) => {
      const x = wg[a].watek, y = wg[b].watek;
      return (przypiete ? (y.przypiety ? 1 : 0) - (x.przypiety ? 1 : 0) : 0)
        || (y.aktywnosc_at || 0) - (x.aktywnosc_at || 0) || (y.id > x.id ? 1 : y.id < x.id ? -1 : 0);
    });
    return { ...lista, porzadek };
  }
  // strona z GET /rozmowy: pierwsza zastępuje listę, następne (przed=dalej) dopisują
  function listaStrona(lista, odp, dopisz) {
    const wg = dopisz ? { ...lista.wg_klucza } : {};
    for (const w of odp.watki || []) wg[klucz(w)] = { typ: "watek", watek: w };
    return sortuj({ ...lista, wg_klucza: wg, dalej: odp.dalej || null, laduje: false, blad: null, wczytana: true });
  }
  // watek.zmiana: wstaw albo zaktualizuj, gdy pasuje do filtra; inaczej usuń. Przy wyszukiwaniu tylko aktualizacja.
  function listaZmiana(lista, w) {
    const k = klucz(w), jest = !!lista.wg_klucza[k];
    const pasuje = (FILTRY[lista.filtr] || FILTRY.rozmowy)(w);
    if (pasuje && (jest || !lista.q)) return sortuj({ ...lista, wg_klucza: { ...lista.wg_klucza, [k]: { typ: "watek", watek: w } } });
    return jest ? listaUsun(lista, w.id) : lista;
  }
  function listaUsun(lista, id) {
    const k = `w:${id}`;
    if (!lista.wg_klucza[k]) return lista;
    const wg = { ...lista.wg_klucza };
    delete wg[k];
    return { ...lista, wg_klucza: wg, porzadek: lista.porzadek.filter((x) => x !== k) };
  }

  // ------------------------------------------------------------------------------------------- oś wątku
  // strona osi: `kierunek` "przed" (starsze, na początek), "po" (nowsze, na koniec) albo brak (najnowsza strona).
  // Pozycje o znanym id podmieniane w miejscu; `pelny` (kompresja) zastępuje wszystko.
  function osStrona(os, odp, kierunek) {
    const stare = (os && !odp.pelny && kierunek) ? os.pozycje : [];
    const wgId = new Map(stare.map((p, i) => [p.id, i]));
    const pozycje = stare.slice(), nowe = [];
    for (const p of odp.pozycje || []) {
      if (wgId.has(p.id)) pozycje[wgId.get(p.id)] = p;
      else { wgId.set(p.id, -1); nowe.push(p); }
    }
    const out = kierunek === "przed" ? nowe.concat(pozycje) : pozycje.concat(nowe);
    return {
      pozycje: out, laduje: false,
      przed: kierunek === "po" && os ? os.przed : odp.przed || null,
      po: kierunek === "przed" && os ? os.po : odp.po || (os && os.po) || null,
      niedostepni: odp.niedostepni || [],
    };
  }
  const zWpisu = (wpis) => ({ id: wpis.id, rodzaj: wpis.rodzaj === "system" ? "system" : "wlasciciel", ts: wpis.utworzony_at,
    tekst: wpis.tekst, tryb: wpis.tryb, wpis });
  function osWpis(os, wpis) {
    if (!os) return os;
    const i = os.pozycje.findIndex((p) => p.id === wpis.id), p = zWpisu(wpis);
    const pozycje = os.pozycje.slice();
    if (i >= 0) pozycje[i] = { ...pozycje[i], ...p };
    else pozycje.push(p);
    return { ...os, pozycje };
  }

  // ------------------------------------------------------------------------------------------- przebiegi
  // migawka GET /przebiegi/{id}: tekst i kroki do chwili `seq`; późniejsze zdarzenia dochodzą po kursorze
  const zMigawki = (p) => {
    const { tekst_dotad, kroki_dotad, seq, ...reszta } = p;
    return { ...reszta, tekst: tekst_dotad || "", kroki: kroki_dotad || [], komentarze: [], mysli: [], _kursor: seq || null };
  };
  const swiezy = (p, kursor) => !p || !p._kursor || !kursor || porownaj(kursor, p._kursor) > 0;
  function krok(kroki, faza, k) {
    if (faza === "koniec") {
      for (let i = kroki.length - 1; i >= 0; i--) {
        const x = kroki[i];
        if (x.narzedzie === k.narzedzie && x.ts === k.ts && x.czas_ms == null) { const n = kroki.slice(); n[i] = k; return n; }
      }
    }
    return kroki.concat([k]);
  }
  const pusty = (id) => ({ id, tekst: "", kroki: [], komentarze: [], mysli: [] });
  function przebieg(przebiegi, typ, d, kursor) {
    const id = typ === "przebieg.stan" ? d.przebieg && d.przebieg.id : d.id;
    if (!id) return przebiegi;
    const p = przebiegi[id];
    if (typ !== "przebieg.stan" && typ !== "przebieg.koniec" && typ !== "przebieg.nadzor" && !swiezy(p, kursor)) return przebiegi;
    const b = p || { ...pusty(id), watek_id: d.watek_id, agent: d.agent };
    let n = b;
    switch (typ) {
      case "przebieg.stan": n = { ...b, ...d.przebieg }; break;
      case "przebieg.delta": n = { ...b, tekst: b.tekst + (d.tekst || "") }; break;
      case "przebieg.narzedzie": n = { ...b, kroki: krok(b.kroki, d.faza, d.krok || {}) }; break;
      case "przebieg.komentarz": n = { ...b, komentarze: b.komentarze.concat([{ tekst: d.tekst, typ: d.typ, przyjete: d.przyjete }]) }; break;
      case "przebieg.mysl": n = { ...b, mysli: b.mysli.concat([d.tekst]).slice(-20) }; break;
      case "przebieg.podagent": n = { ...b, podagenci: (b.podagenci || []).concat([{ faza: d.faza, opis: d.opis }]) }; break;
      // wygasła prośba zostaje w `zgoda_wygasla` także po końcu przebiegu („Czas minął” + „Poproś ponownie”)
      case "przebieg.zgoda": n = { ...b, zgoda: d.zgoda, ...(d.zgoda && d.zgoda.wygasla ? { zgoda_wygasla: d.zgoda } : {}) }; break;
      case "przebieg.koniec": n = { ...b, stan: d.stan, blad: d.blad || null }; break;
      case "przebieg.nadzor": n = { ...b, nadzor: d.nadzor, nadzor_zgoda: d.nadzor_zgoda }; break;
      default: return przebiegi;
    }
    return { ...przebiegi, [id]: n };
  }

  // przebiegi z odpowiedzi POST wysyłki (widok bez tekst_dotad): nowe dodane, znane zostają ze swoim tekstem i stanem
  // (strumień mógł być szybszy niż odpowiedź); brakujące pola uzupełnione
  function dodajPrzebiegi(przebiegi, lista) {
    let out = przebiegi;
    for (const p of lista || []) {
      if (!p || !p.id) continue;
      const { tekst_dotad, kroki_dotad, seq, ...reszta } = p;
      if (out === przebiegi) out = { ...przebiegi };
      out[p.id] = out[p.id] ? { ...reszta, ...out[p.id] } : { ...pusty(p.id), ...reszta };
    }
    return out;
  }
  // przebieg z odpowiedzi akcji (stop, zgoda, ponów): stan z serwera wygrywa, tekst i kroki ze strumienia zostają;
  // stan końcowy ze strumienia nie cofa się do wcześniejszego z odpowiedzi, która przyszła później
  function scalPrzebieg(przebiegi, p, dodatki) {
    if (!p || !p.id) return przebiegi;
    const { tekst_dotad, kroki_dotad, seq, ...reszta } = p;
    const jest = przebiegi[p.id] || pusty(p.id);
    const n = { ...jest, ...reszta, ...(dodatki || {}) };
    if (KONCOWE.has(jest.stan) && !KONCOWE.has(reszta.stan)) n.stan = jest.stan;
    return { ...przebiegi, [p.id]: n };
  }

  // ------------------------------------------------------------------------------------------- zdarzenie → stan
  function zastosujZdarzenie(s, typ, d, kursor) {
    if (!d) return s;
    if (typ.startsWith("przebieg.")) {
      const przebiegi = przebieg(s.przebiegi, typ, d, kursor);
      return przebiegi === s.przebiegi ? s : { ...s, przebiegi };
    }
    switch (typ) {
      case "watek.zmiana": {
        const w = d.watek;
        if (!w || !w.id) return s;
        const watki = s.watki[w.id] ? { ...s.watki, [w.id]: { ...s.watki[w.id], ...w } } : s.watki;
        return { ...s, lista: listaZmiana(s.lista, w), watki };
      }
      case "watek.usuniety": return { ...s, lista: listaUsun(s.lista, d.id) };
      case "watek.wpis": {
        const os = s.os[d.watek_id];
        return os && d.wpis ? { ...s, os: { ...s.os, [d.watek_id]: osWpis(os, d.wpis) } } : s;
      }
      case "hello": return { ...s, wersja: d.wersja || s.wersja, silnik: d.silnik || s.silnik };
      case "aktualizacja": return { ...s, aktualizacja: d };
      case "decyzje.zmiana": return { ...s, decyzje: { ...s.decyzje, liczba: d.liczba || 0 } };
      default: return s;
    }
  }

  // ------------------------------------------------------------------------------------------- widok osi
  // Pozycje do pokazania: w trybie Prosty kolejne grupy kroków jednego agenta sklejone w jedną, a kroki tuż przed
  // odpowiedzią tego agenta (ten sam przebieg) dołączone do niej (`kroki` pozycji agenta); pozycje trwającej
  // tury (w_toku) przebiegu z dymkiem schowane, bo pokazuje je żywy dymek ({rodzaj: "zywy", przebieg}) wstawiony za
  // wpisem właściciela, na który odpowiada (inaczej na końcu). Dymek zakończonego przebiegu znika, gdy oś ma już jego
  // odpowiedź (pozycję agenta z tym przebieg_id i bez w_toku).
  // Wiadomości w drodze (`oczekujace`, optymistyczne dymki właściciela) stoją za osią, a znikają, gdy oś ma wpis
  // z tym samym kluczem. Nieudany przebieg zostaje dymkiem z „Ponów”, dopóki nie ma odpowiedzi ani ponowienia.
  // Budzenia kart przekazanych w tym wątku pokazuje karta pracy (35-karty.js): ostatnie „completed” karty zostaje
  // jako `koniec` („<agent> · skończone”), reszta znika, a karta z taką wiadomością dostaje `koniec_nizej`. Karty stoją
  // pod wiadomością agenta, która je zapowiada (kroki tury idą do niej), a w trwającej turze od razu pod żywym dymkiem.
  // Zatrzymany przebieg (Stop właściciela), którego odpowiedź jest już na osi: ostatnia pozycja agenta z tym
  // przebiegiem dostaje `zatrzymany` (linia „Zatrzymane · Ponów” pod nią, spec §9.1), dopóki nie ma ponowienia;
  // zatrzymany przed pierwszym słowem (żadnej pozycji agenta) zostaje pustym dymkiem z tą linią.
  function widok(pozycje, przebiegiWatku, { szczegoly = false, oczekujace = null } = {}) {
    const maOdpowiedz = (p) => pozycje.some((x) => x.przebieg_id === p.id && !x.w_toku && x.rodzaj === "agent");
    const maSlad = (p) => pozycje.some((x) => x.przebieg_id === p.id && x.rodzaj === "agent");
    const lista = przebiegiWatku || [];
    const ponowione = new Set(lista.map((p) => p.ponowienie_z).filter(Boolean));
    const zywe = lista.filter((p) => p.zrodlo !== "nadzor" && p.stan !== "dopisany" && !ponowione.has(p.id)
      && (!KONCOWE.has(p.stan) || ((p.tekst || p.blad || (PONOWIALNE.has(p.stan) && (p.stan !== "zatrzymane" || !maSlad(p))))
        && !maOdpowiedz(p))));
    const ukryte = new Set(zywe.map((p) => p.id));
    const stop = new Map(lista.filter((p) => p.stan === "zatrzymane" && !ponowione.has(p.id) && !ukryte.has(p.id)).map((p) => [p.id, p]));
    // budzenia kart z tego wątku: stan pokazuje karta pracy, więc pośrednie (oddana do oceny, ponowienia) znikają,
    // a ostatnie „completed” każdej karty to wiadomość „<agent> · skończone” (rodzaj `koniec`)
    const karty = kartyWatku(pozycje);
    const ostatniKoniec = new Map();
    for (const x of pozycje) {
      const b = x.rodzaj === "budzenie" && x.budzenie;
      if (b && karty.has(b.task_id) && b.status === "completed") ostatniKoniec.set(b.task_id, x.id);
    }
    const out = [];
    for (const x of pozycje) {
      // karta pracy z trwającej tury stoi od razu pod żywym dymkiem; reszta tury jest w dymku
      if (x.w_toku && ukryte.has(x.przebieg_id) && !(x.rodzaj === "przekazanie" && x.karta && x.karta.task_id)) continue;
      if (x.rodzaj === "budzenie" && x.budzenie && karty.has(x.budzenie.task_id)) {
        if (ostatniKoniec.get(x.budzenie.task_id) === x.id) out.push({ ...x, rodzaj: "koniec" });
        continue;
      }
      if (x.rodzaj === "przekazanie" && x.karta && ostatniKoniec.has(x.karta.task_id)) {
        out.push({ ...x, koniec_nizej: true });          // wynik pokazuje wiadomość `koniec`, karta zostaje krótka
        continue;
      }
      // błąd tury przebiegu z dymkiem pokazuje sam dymek (z „Ponów”), nie drugi raz na osi
      if (x.rodzaj === "blad_tury" && x.przebieg_id && ukryte.has(x.przebieg_id)) continue;
      const pop = out[out.length - 1];
      if (!szczegoly && x.rodzaj === "kroki" && pop && pop.rodzaj === "kroki" && pop.agent === x.agent) {
        out[out.length - 1] = { ...pop, kroki: (pop.kroki || []).concat(x.kroki || []) };
        continue;
      }
      // kroki tuż przed odpowiedzią tego samego agenta i przebiegu idą do niej (linia kroków pod nagłówkiem wiadomości)
      if (x.rodzaj === "agent" && pop && pop.rodzaj === "kroki" && pop.agent === x.agent && (pop.przebieg_id || null) === (x.przebieg_id || null)) {
        out[out.length - 1] = { ...x, kroki: (pop.kroki || []).concat(x.kroki || []) };
        continue;
      }
      out.push(x);
    }
    // wiadomość, która zapowiada karty, nad nimi: [kroki?, przekazanie…, agent] tego agenta → [agent (+kroki), przekazanie…]
    for (let i = 0; i < out.length; i++) {
      const a = out[i];
      if (a.rodzaj !== "agent") continue;
      let j = i - 1;
      while (j >= 0 && out[j].rodzaj === "przekazanie" && out[j].agent === a.agent && !out[j].w_toku) j--;
      if (j === i - 1) continue;
      const kartyTury = out.slice(j + 1, i), k = j >= 0 ? out[j] : null;
      if (!szczegoly && k && k.rodzaj === "kroki" && k.agent === a.agent && (k.przebieg_id || null) === (a.przebieg_id || null)) {
        out.splice(j, i - j + 1, { ...a, kroki: (k.kroki || []).concat(a.kroki || []) }, ...kartyTury);
      } else out.splice(j + 1, i - j, a, ...kartyTury);
    }
    if (stop.size) {
      const ostatnia = new Map();
      out.forEach((x, i) => { if (x.rodzaj === "agent" && stop.has(x.przebieg_id)) ostatnia.set(x.przebieg_id, i); });
      for (const [pid, i] of ostatnia) out[i] = { ...out[i], zatrzymany: stop.get(pid) };
    }
    for (const o of oczekujaceWidoczne(pozycje, oczekujace)) out.push({ rodzaj: "wlasciciel", id: `o:${o.klucz}`, ts: o.ts, tekst: o.tekst, oczekuje: o });
    for (const p of zywe) {
      let i = out.findIndex((x) => x.id === p.wpis_id);
      if (i < 0) { out.push({ rodzaj: "zywy", id: `z:${p.id}`, przebieg: p }); continue; }
      while (i + 1 < out.length && out[i + 1].rodzaj === "zywy") i++;
      out.splice(i + 1, 0, { rodzaj: "zywy", id: `z:${p.id}`, przebieg: p });
    }
    return out;
  }

  // karty kanbana przekazane w wątku (pozycje `przekazanie` z task_id), w kolejności osi
  function kartyWatku(pozycje) {
    const ids = new Set();
    for (const x of pozycje || []) if (x.rodzaj === "przekazanie" && x.karta && x.karta.task_id) ids.add(x.karta.task_id);
    return ids;
  }

  function oczekujaceWidoczne(pozycje, oczekujace) {
    if (!oczekujace || !oczekujace.length) return [];
    const klucze = new Set();
    for (const x of pozycje) if (x.wpis && x.wpis.klucz) klucze.add(x.wpis.klucz);
    return oczekujace.filter((o) => !klucze.has(o.klucz));
  }

  // „Nowe od tąd”: przed n-tą od końca pozycją od agentów (n = nieprzeczytane przy otwarciu); nie dalej niż do
  // ostatniej wiadomości właściciela (po niej wszystko jest nowe). Kroki się nie liczą. Zwraca id pozycji albo null.
  const NOWE = new Set(["agent", "blad_tury", "obca", "budzenie", "dostawa", "przekazanie", "koniec"]);
  function noweOdTad(pozycje, n) {
    if (!(n > 0)) return null;
    let id = null, ile = 0;
    for (let i = pozycje.length - 1; i >= 0 && ile < n; i--) {
      const x = pozycje[i];
      if (x.rodzaj === "wlasciciel") break;
      if (NOWE.has(x.rodzaj)) { id = x.id; ile++; }
    }
    return id;
  }

  // zgoda: zdanie o ryzyku z klucza wzorca i opisu (jak przebiegi.ryzyko na serwerze), klucz tekstu `zgoda.r_*`;
  // natywnie także polecenia Windows i macOS oraz zapis pliku z wtyczki zgód (docs/NATYWNIE.md W17)
  const RYZYKA = [[/rm\b|(?<!reg )(?<!reg\.exe )delet|remov|unlink|rmdir|shred|\bdel\b|\berase\b|\brd\s+\/s/i, "usun"],
    [/sudo|root|chmod|chown|privileg|icacls|takeown|\breg(?:\.exe)?\s+(?:delete|add)\b|set-executionpolicy|runas|diskutil/i, "admin"],
    [/git.?push|force.?push|publish|deploy/i, "wysyla"], [/curl|wget|network|http|ssh|scp|invoke-webrequest|\biwr\b/i, "siec"],
    [/kill|shutdown|reboot|systemctl|stop-process|restart-computer|launchctl/i, "restart"],
    [/:write_file:|:patch:|write_file|\bpatch\b/i, "zapis"]];
  function ryzyko(zgoda) {
    const t = `${(zgoda && zgoda.klucz_wzorca) || ""} ${(zgoda && zgoda.opis) || ""}`;
    const r = RYZYKA.find(([w]) => w.test(t));
    return r ? r[1] : "inne";
  }
  // przyciski zgody: dokładnie wybory zdarzenia w ich kolejności; „always” tylko pod „Więcej”
  function wyboryZgody(wybory) {
    const w = (wybory && wybory.length) ? wybory : ["once", "deny"];
    return { widoczne: w.filter((x) => x !== "always"), wiecej: w.filter((x) => x === "always") };
  }

  // kroki: liczba, czas (suma czasów narzędzi, bez nich rozpiętość znaczników), błędy, ostatni krok
  function krokiPodsumowanie(kroki) {
    const k = kroki || [];
    let ms = 0, bledy = 0;
    for (const x of k) { if (x.czas_ms > 0) ms += x.czas_ms; if (x.blad) bledy++; }
    const rozpietosc = k.length > 1 ? Math.max(0, (k[k.length - 1].ts || 0) - (k[0].ts || 0)) : 0;
    return { n: k.length, sekundy: Math.round(ms ? ms / 1000 : rozpietosc), bledy, ostatni: k[k.length - 1] || null };
  }

  // przebiegi wątku, które Stop (i Esc Esc) zatrzymuje: także nadzór i wysyłane
  const doZatrzymania = (przebiegiWatku) => (przebiegiWatku || []).filter((p) => DO_ZATRZYMANIA.has(p.stan));

  // błąd przebiegu → co pokazać: brak klucza i model prowadzą do Połączeń, reszta do „Ponów”
  function klasaBledu(blad) {
    const kod = (blad && blad.kod) || "";
    if (kod === "klucz") return { rodzaj: "klucz", sekcja: "polaczenia", pod: "klucze", ponow: false };
    if (kod === "model") return { rodzaj: "model", sekcja: "polaczenia", pod: "modele", ponow: true };
    if (kod === "brama_niedostepna" || kod === "limit_bramy") return { rodzaj: "brama", ponow: true };
    return { rodzaj: "inny", ponow: true };
  }

  return { KONCOWE, PONOWIALNE, DO_ZATRZYMANIA, porownaj, FILTRY, listaStrona, listaZmiana, listaUsun, osStrona, osWpis,
    zWpisu, zMigawki, przebieg, dodajPrzebiegi, scalPrzebieg, zastosujZdarzenie, widok, kartyWatku, noweOdTad, ryzyko,
    wyboryZgody, krokiPodsumowanie, doZatrzymania, klasaBledu };
})();

// ------------------------------------------------------------------------------------------------- kompozytor
const Pisanie = (() => {
  // Kto dostanie wiadomość. Wiodąca @wzmianka w tekście wygrywa z wyborem w kompozytorze (serwer czyta ją sam),
  // wybór idzie jako `adresaci` (jedna wiadomość), bez obu: koordynator wątku. `srodek`: wzmianki w środku zdania
  // (podpowiedź: wiadomość i tak trafi do koordynatora), `nieznany`: @słowo na początku, którego nie ma we flocie.
  function adresat(tekst, wybrany, aliasy, koordynator, nazwy) {
    const w = Wzmianki.parsuj(tekst, aliasy || {}, { koordynator, nazwy });
    const srodek = w.ostrzezenia.filter((o) => o.startsWith("srodek:")).map((o) => o.slice(7));
    const nieznany = (w.ostrzezenia.find((o) => o.startsWith("nieznany:")) || "").slice(9) || null;
    // wielu: powyżej WIELU (12-wzmianki.js) adresatów kompozytor pyta przed wysłaniem (ten sam próg co serwer)
    const wielu = w.ostrzezenia.some((o) => o.startsWith("wielu:"));
    if (w.wiodace) return { agenci: w.adresaci, zrodlo: "tekst", adresaci: null, srodek, nieznany, bezposrednio: w.bezposrednio.length > 0, wielu };
    if (wybrany && wybrany !== koordynator) return { agenci: [wybrany], zrodlo: "wybor", adresaci: [wybrany], srodek, nieznany, bezposrednio: true, wielu: false };
    return { agenci: [koordynator], zrodlo: null, adresaci: null, srodek, nieznany, bezposrednio: false, wielu: false };
  }

  // „@fra” tuż przed kursorem, na granicy słowa → {od, do, q}; inaczej null
  function wzmiankaPrzyKursorze(tekst, kursor) {
    const przed = String(tekst || "").slice(0, kursor);
    const m = /(^|[\s,(])@([\p{L}\p{N}_-]{0,24})$/u.exec(przed);
    return m ? { od: kursor - m[2].length - 1, do: kursor, q: m[2] } : null;
  }

  // agenci pasujący do początku uchwytu, aliasu albo nazwy (złożone: „lo” = Łowca); koordynator pierwszy, potem
  // kolejność floty; najwyżej `ile`
  function podpowiedzi(agenci, q, koordynator, ile = 8) {
    const z = Wzmianki.zloz(q);
    const pasuje = (a) => !z || [a.handle, a.name, a.nazwa, a.nazwa_en, ...(a.aliasy || [])]
      .some((x) => x && Wzmianki.zloz(x).startsWith(z));
    const out = (agenci || []).filter((a) => a && a.name && a.stan !== "archiwum" && pasuje(a));
    out.sort((a, b) => (b.name === koordynator) - (a.name === koordynator));
    return out.slice(0, ile);
  }

  // wstawienie wybranej wzmianki: „@fra” → „@uchwyt ” i kursor za spacją
  function wstawWzmianke(tekst, miejsce, uchwyt) {
    const t = String(tekst || ""), wstawka = `@${uchwyt} `;
    const reszta = t.slice(miejsce.do).replace(/^\s+/, "");
    return { tekst: t.slice(0, miejsce.od) + wstawka + reszta, kursor: miejsce.od + wstawka.length };
  }

  // klucz wysyłki dla serwera (^[A-Za-z0-9_-]{1,64}$): 16 losowych bajtów w base64url
  function klucz(losowe) {
    const b = losowe || new Uint8Array(16);
    let s = "";
    for (const x of b) s += "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"[x & 63];
    return s;
  }

  return { adresat, wzmiankaPrzyKursorze, podpowiedzi, wstawWzmianke, klucz };
})();
