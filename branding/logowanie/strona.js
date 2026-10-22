/* Jarvo: data na stronie tytułowej i wejście kluczem jednorazowym (#klucz=JRV-… od instalatora albo `jarvo open`).
   Klucz jest tylko w części adresu po #: nie idzie do serwera z adresem i nie zostaje w historii (replaceState). */
(function () {
  var d = document.getElementById('j-data');
  if (d) {
    try { d.textContent = new Date().toLocaleDateString('pl-PL', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }); }
    catch (e) { d.textContent = ''; }
  }
  var m = /(?:^#|&)klucz=([A-Za-z0-9-]{10,40})(?:&|$)/.exec(location.hash || '');
  if (m || location.hash) { try { history.replaceState(null, '', location.pathname + location.search); } catch (e) {} }
  var form = document.querySelector('form.provider-form');
  if (!m || !form) return;
  var kod = m[1].toUpperCase();
  var user = form.querySelector('input[name=username]');
  var pass = form.querySelector('input[name=password]');
  var btn = form.querySelector('button[type=submit]');
  var err = form.querySelector('.form-error');
  var notka = document.getElementById('j-notka');
  var stempel = document.getElementById('j-pieczatka');
  if (!pass || !btn) return;
  var spokojnie = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  document.body.classList.add('j-klucz');
  var label = pass.closest('label') && pass.closest('label').querySelector('.field-label');
  if (label) label.textContent = 'Klucz jednorazowy';
  if (notka) notka.textContent = '* Wchodzisz bez hasła. Instalator dał Ci klucz jednorazowy.';
  var dymek = document.getElementById('j-dymek');
  if (dymek) dymek.textContent = 'Cześć! Klucz wpiszę za Ciebie.';
  var czcionki = document.createElement('div');
  czcionki.className = 'j-czcionki';
  czcionki.setAttribute('aria-live', 'polite');
  pass.style.display = 'none';
  pass.parentNode.insertBefore(czcionki, pass.nextSibling);
  btn.disabled = true;

  function wroc(tekst) {
    document.body.classList.remove('j-klucz');
    czcionki.remove();
    pass.style.display = '';
    pass.value = '';
    if (label) label.textContent = 'Hasło';
    if (notka) notka.textContent = '* Ten klucz już zadziałał albo wygasł. Wpisz hasło albo otwórz Jarvo jeszcze raz poleceniem jarvo open.';
    if (err) { err.textContent = tekst; err.hidden = false; }
    btn.disabled = false;
    btn.classList.remove('j-wcisniety');
    if (dymek) dymek.textContent = 'Ten klucz już nie działa. Wpisz hasło.';
    if (user) { user.placeholder = 'jarvo'; user.focus(); }
  }

  function wejdz() {
    btn.classList.add('j-wcisniety');
    var next = (form.querySelector('input[name=next]') || {}).value || '';
    fetch('/auth/password-login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin',
      body: JSON.stringify({ provider: form.getAttribute('data-provider') || '', username: (user && user.value) || 'klucz', password: kod, next: next })
    }).then(function (r) {
      if (!r.ok) { wroc(r.status === 429 ? 'Za dużo prób. Odczekaj chwilę.' : 'Klucz nie zadziałał.'); return; }
      return r.json().then(function (data) {
        if (stempel) stempel.classList.add('j-pokaz');
        if (dymek) dymek.textContent = 'Wchodzimy!';
        setTimeout(function () { window.location.assign((data && data.next) || '/'); }, spokojnie ? 150 : 900);
      });
    }).catch(function () { wroc('Błąd sieci. Spróbuj ponownie.'); });
  }

  var i = 0;
  function pisz() {
    if (i >= kod.length) { setTimeout(wejdz, spokojnie ? 0 : 380); return; }
    var s = document.createElement('span');
    s.textContent = kod[i];
    if (kod[i] === '-') s.className = 'j-kreska';
    czcionki.appendChild(s);
    i++;
    setTimeout(pisz, spokojnie ? 0 : 55);
  }
  setTimeout(pisz, spokojnie ? 0 : 1300);
})();
