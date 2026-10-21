/* Jarvo: skrypt powłoki w index.html dashboardu (branding/patch_dashboard.py wkleja go jako pierwsze dziecko <body>,
   po bootstrapie Hermesa z __HERMES_BASE_PATH__). Działa przed aplikacją: przepisuje "/" i "/base" na "/jarvo",
   daje przekierowaniom Hermesa cel (__JARVO_CEL__), stawia zasłonę startową na /jarvo z bezpiecznikiem 8 s,
   rozpoznaje osadzenie w ramce szuflady, nie pokazuje dashboardu w ramce obcej strony, a przy data-jarvo-app
   usypia (inert) wszystko poza korzeniem aplikacji. */
(function () {
  var d = document.documentElement, b = (window.__HERMES_BASE_PATH__ || "").replace(/\/+$/, "");
  var p = location.pathname.replace(/\/+$/, "") || "/";
  var wRamce = window.top !== window.self;
  // ?jarvo-embed=1 tylko w ramce (ręczne próby): w zwykłej karcie schowałby menu Hermesa bez wyjścia
  var emb = wRamce && /[?&]jarvo-embed=1(&|$)/.test(location.search);
  try { emb = emb || !!(window.frameElement && window.frameElement.hasAttribute("data-jarvo-embed")); } catch (e) {}
  // ramka z obcego pochodzenia (np. strona agenta na :9120) nie dostaje dashboardu: ochrona przed clickjackingiem
  try { if (wRamce && window.top.location.origin !== location.origin) throw 0; }
  catch (e) { d.setAttribute("data-jarvo-zablokuj", ""); }
  if (emb) d.setAttribute("data-jarvo-embed", "");
  var naJarvo = function (x) { return x === b + "/jarvo"; };
  var tu = function () { return location.pathname.replace(/\/+$/, "") || "/"; };
  window.__JARVO_CEL__ = function () {            // cel przekierowań Hermesa ("/" i nieznany adres)
    var z = tu(), na = naJarvo(z), c = emb || na ? "/sessions" : "/jarvo";   // na /jarvo bez pluginu: /sessions, bez pętli
    // Hermes opuszcza /jarvo (plugin się nie wczytał): zasłona startowa nie może zakryć /sessions
    if (na) { d.removeAttribute("data-jarvo-wstepnie"); d.removeAttribute("data-jarvo-app"); }
    // Hermes (ProfileProvider) w tej samej klatce dopisuje ?profile= do adresu sprzed przekierowania i cofa je
    // (np. /nieznane?profile=default, pusta strona). Wtedy przekierowanie powtarzamy sami, z zachowanym ?profile=.
    if (z !== b + c) [150, 1000].forEach(function (ms, i) {   // cel = obecny adres (np. "/" w ramce → /sessions): nic
      setTimeout(function () {
        if (tu() !== z) return;
        var u = b + c + location.search + location.hash;
        if (i) { location.replace(u); return; }        // ostatnia deska: pełne przejście zamiast pustej strony
        history.replaceState(history.state, "", u);
        window.dispatchEvent(new PopStateEvent("popstate", { state: history.state }));
      }, ms);
    });
    return c;
  };
  if (!emb && (p === (b || "/") || p === b + "/base")) {   // "/" i stare zakładki: zmiana adresu przed startem SPA
    history.replaceState(history.state, "", b + "/jarvo" + location.search + location.hash);
    p = b + "/jarvo";
  }
  if (!emb && naJarvo(p)) {
    d.setAttribute("data-jarvo-wstepnie", "");       // tylko zasłona; powłokę chowa dopiero aplikacja (wersja ≥ 2)
    setTimeout(function () {                          // bezpiecznik: bez gotowego widoku po 8 s wraca powłoka Hermesa
      if (!d.hasAttribute("data-jarvo-gotowe")) { d.removeAttribute("data-jarvo-wstepnie"); d.removeAttribute("data-jarvo-app"); }
    }, 8000);
  }
  // Aplikacja (wersja ≥ 2) ustawia data-jarvo-app i ma korzeń z atrybutem data-jarvo-korzen. Wszystko poza korzeniem
  // (powłoka i banery Hermesa pod warstwą aplikacji, okna dokładane obok) dostaje wtedy inert: Tab i czytnik ekranu
  // zostają w aplikacji. Bez data-jarvo-app atrybuty znikają; cudzego inert nie ruszamy.
  var uspione = [], straz = window.MutationObserver ? new MutationObserver(uspij) : null;
  function uspij() {
    straz.disconnect();
    uspione.forEach(function (e) { e.removeAttribute("inert"); });
    uspione = [];
    var k = d.hasAttribute("data-jarvo-app") && document.querySelector("[data-jarvo-korzen]");
    for (var e = k; e && e !== document.body && e.parentElement; e = e.parentElement) {
      [].forEach.call(e.parentElement.children, function (s) {
        if (s !== e && !s.hasAttribute("inert") && !/^(SCRIPT|STYLE|LINK)$/.test(s.tagName)) { s.setAttribute("inert", ""); uspione.push(s); }
      });
      straz.observe(e.parentElement, { childList: true });
    }
    straz.observe(d, { attributes: true, attributeFilter: ["data-jarvo-app"] });
  }
  if (straz) straz.observe(d, { attributes: true, attributeFilter: ["data-jarvo-app"] });
})();
