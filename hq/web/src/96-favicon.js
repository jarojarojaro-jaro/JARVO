// Favicon Jarvo (ikona aplikacji z brand/ikona.svg) na każdej stronie dashboardu, zamiast ikony Hermesa.
(function favicon() {
  if (typeof document === "undefined") return;
  const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">\n\n<rect width="512" height="512" rx="80" fill="#D4213D"/><g transform="translate(68.0000 94.0000) scale(1.135952 1.135952)"><path fill="#10131C" fill-rule="evenodd" d="M259 1H306V9H311V44H306V53H295V108H292V117H306V126H314V134H323V143H331V214H323V223H314V231H306V240H292V251H285V260H276V268H268V276H250V284H83V276H64V268H56V260H49V251H40V240H26V231H17V223H9V214H0V143H9V134H17V126H26V117H40V91H49V82H56V74H64V65H86V56H250V65H268V53H259V44H254V9H259Z"/><path fill="#F2F1E8" fill-rule="evenodd" d="M276 44H286V82H276ZM86 65H250V74H267V82H276V91H282V251H276V259H267V267H250V276H83V267H65V259H57V251H50V91H57V82H65V74H86ZM86 98V106H80V112H71V231H80V236H86V244H244V236H250V231H259V112H250V106H244V98Z"/><path fill="#D4213D" fill-rule="evenodd" d="M26 126H50V231H26V223H18V214H9V143H18V134H26ZM282 126H306V134H314V143H323V214H314V223H306V231H282ZM306 161V191H314V161ZM18 161V191H26V161Z"/><path fill="#B8FF3D" fill-rule="evenodd" d="M264 9H301V44H264ZM101 146H122V210H101ZM189 146H211V158H223V170H235V187H223V199H211V210H189V194H200V187H211V170H200V162H189Z"/></g>\n</svg>';
  const href = "data:image/svg+xml," + encodeURIComponent(svg);
  function set() {
    let own = document.querySelector("link[data-jarvo-icon]");
    for (const l of document.querySelectorAll("link[rel~='icon']")) if (l !== own) l.remove();
    if (!own) {
      own = document.createElement("link");
      own.rel = "icon"; own.type = "image/svg+xml"; own.href = href; own.dataset.jarvoIcon = "1";
      document.head.appendChild(own);
    }
  }
  set();
  setInterval(set, 5000);   // Hermes może podmienić <head> przy nawigacji
})();
