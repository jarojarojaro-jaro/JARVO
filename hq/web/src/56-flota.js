// Centrala → Jak działa usługa: flota jako klikalna figura izometryczna (wspólny skill `izometria`, iso.py flota).
// Wieża z fleet.json: Jarvo na mostku, pokoje agentów, demo = droga zlecenia (Ty → Jarvo → karty → ocena → raport).
// Strona ma własne skrypty, więc przychodzi z serwera podglądu (osobny port, sandbox) i ładuje się dopiero na klik.

function flotaUrl(r, query) {
  const base = r.url || `${location.protocol}//${location.hostname}:${r.port}${r.path}`;
  return query ? `${base}?${query}` : base;
}

function JakDziala() {
  const [adres, setAdres] = useState(null);     // {port, path} z /flota
  const [otwarte, setOtwarte] = useState(false);
  const [raz, setRaz] = useState(0);            // „Jeszcze raz”: nowa ramka = demo od początku
  const [blad, setBlad] = useState(null);
  async function pokaz() {
    setBlad(null);
    try {
      setAdres(adres || await api.flota());
      setOtwarte(true);
    } catch (e) {
      setBlad(e.message || String(e));
    }
  }
  return html`<section class="thq-flota" aria-label=${L("Jak działa usługa", "How the service works")}>
    <h2 class="thq-h2">${L("Jak działa usługa", "How the service works")}</h2>
    ${!otwarte && html`<button type="button" class="thq-konw-drop" onClick=${pokaz}>
      <strong>▶ ${L("Pokaż flotę jako figurę", "Show the fleet as a figure")}</strong>
      <span class="thq-muted">${L("Wieża z Jarvem na górze i pokojami agentów: zlecenie przechodzi przez flotę i wraca jako raport. Klikalna, dobra do pokazania klientowi.",
        "A tower with Jarvo on top and the agents' rooms: an order goes through the fleet and comes back as a report. Clickable, good for showing a client.")}</span>
    </button>`}
    ${otwarte && adres && html`<div class="thq-flota-ramka">
      <iframe key=${raz} class="thq-flota-fig" src=${flotaUrl(adres, "kadr&podpis&demo&motyw=ciemny")} sandbox="allow-scripts"
        title=${L("Flota Jarvo: kliknij pokój agenta albo terminal TY", "Jarvo fleet: click an agent's room or the TY terminal")}></iframe>
      <div class="thq-flota-akcje">
        <button type="button" class="thq-act-btn" onClick=${() => setRaz(raz + 1)}>↻ ${L("Jeszcze raz", "Replay")}</button>
        <button type="button" class="thq-act-btn" onClick=${() => window.open(flotaUrl(adres, "demo&motyw=ciemny"), "_blank", "noopener,noreferrer")}>↗ ${L("Pełny ekran", "Full screen")}</button>
        <button type="button" class="thq-act-btn" onClick=${() => setOtwarte(false)}>${L("Zwiń", "Collapse")}</button>
      </div>
      <p class="thq-muted">${L("Klik w pokój mówi, kto to; klik w terminal TY puszcza zlecenie. Grafikę albo film z tą figurą zrobi Studio albo Wideograf: napisz do Jarva.",
        "Click a room to see who it is; click the TY terminal to send an order. Studio or the Videographer can turn it into a graphic or a film: ask Jarvo.")}</p>
    </div>`}
    ${blad && html`<p class="thq-error" role="alert">${blad}</p>`}
  </section>`;
}
