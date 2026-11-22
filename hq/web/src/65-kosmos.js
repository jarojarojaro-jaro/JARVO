// Mapa wejścia Mózgu w motywie TARS (docs/HQ.md „Mózg”, pakiet „kosmos” ładowany dopiero na wejściu Mózgu): Gargantua,
// czyli czarna dziura z dyskiem akrecyjnym i soczewkowaniem (shader WebGL z makiety TARS, geodezyjne zakrzywienie
// promieni), a wokół niej części wiedzy na trzech orbitach z podpisami i liczbą notatek (klik = wejście w część).
// Ruch tylko celowy: dysk i orbity płyną przez 8 s po wejściu i przez chwilę po ruchu myszy nad mapą (ok. 9 klatek/s),
// potem stają, więc mapa w spoczynku nie zajmuje procesora; przy `prefers-reduced-motion` jedna nieruchoma klatka.
// Bez WebGL albo na zbyt wolnym sprzęcie (pierwsza klatka > 160 ms) zostaje Gargantua z samego CSS.

const KOSMOS_FS = `precision highp float;uniform vec2 R;uniform float T;
float hs(vec2 p){vec3 q=fract(vec3(p.xyx)*.1031);q+=dot(q,q.yzx+33.33);return fract((q.x+q.y)*q.z);}
float vn(vec2 p,float P){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);float a=mod(i.y,P),b=mod(i.y+1.,P);
 return mix(mix(hs(vec2(i.x,a)),hs(vec2(i.x+1.,a)),f.x),mix(hs(vec2(i.x,b)),hs(vec2(i.x+1.,b)),f.x),f.y);}
float pas(float r,float a){return(.38+.62*vn(vec2(r*11.,a*6.),6.))*(.54+.46*vn(vec2(r*2.4+9.,a*8.),8.));}
void main(){
 vec2 uv=(gl_FragCoord.xy-.5*R)/R.y;
 float el=.11;
 vec3 ro=40.*vec3(0.,sin(el),-cos(el));
 vec3 f=normalize(-ro),rt=normalize(cross(vec3(0.,1.,0.),f)),up=cross(f,rt);
 vec3 v=normalize(f*1.86+uv.x*rt+uv.y*up),p=ro;
 vec3 hv=cross(p,v);float h2=dot(hv,hv);
 vec3 col=vec3(0.);float a=1.;bool esc=true;
 float t1=mod(T,48.),t2=mod(T+24.,48.),m=abs(t1/24.-1.);
 if(h2>57.76){vec3 n=normalize(p-v*dot(p,v));v=normalize(v-n*(2./sqrt(h2)));}
 else for(int i=0;i<300;i++){
  float r2=dot(p,p);
  if(r2<1.){esc=false;break;}
  if(r2>196.&&dot(p,v)>0.)break;
  float dt=max(.016,.042*(sqrt(r2)-.7));
  v-=1.5*h2*p/(r2*r2*sqrt(r2))*dt;
  vec3 q=p+v*dt;
  if(p.y*q.y<0.){
   vec3 k=mix(p,q,p.y/(p.y-q.y));float rr=length(k.xz);
   if(rr>2.6&&rr<6.8){
    float an=atan(k.z,k.x)/6.2831853;
    float w=.021*pow(2.6/rr,1.5);
    float d=mix(pas(rr,an-w*t1),pas(rr+31.,an-w*t2),m);
    float e=pow(2.6/rr,2.1)*smoothstep(2.6,2.92,rr)*smoothstep(6.8,4.3,rr);
    float dop=1.-.42*k.x/rr;
    e*=d*dop*dop*1.66;
    vec3 w3=mix(vec3(1.,.68,.39),vec3(1.,.95,.87),clamp(e*1.25,0.,1.));
    col+=a*w3*e*1.75;a*=1.-clamp(e*1.35,0.,.97);
   }
  }
  p=q;
 }
 if(esc){
  vec3 d=normalize(v);vec2 s=vec2(atan(d.z,d.x),asin(d.y))*64.;vec2 g=floor(s);
  vec2 o=fract(s)-.5-(vec2(hs(g+3.),hs(g+9.))-.5)*.7;
  col+=a*step(.945,hs(g))*smoothstep(.065,0.,length(o))*(.12+.5*hs(g+5.));
 }
 col=1.-exp(-col*1.5);
 col+=(hs(gl_FragCoord.xy)-.5)/255.;
 gl_FragColor=vec4(col,1.);
}`;
// promienie orbit (przy wysokości mapy 688 px) i miejsca startu części: [orbita, kąt w stopniach]; dalsze części złotym kątem
const KOSMOS_ORBITY = [160, 205, 250];
const KOSMOS_START = [[0, 88], [0, 37], [2, 345], [2, 139], [1, 191], [2, 242], [1, 294]];
const kosmosStart = (i) => KOSMOS_START[i] || [i % 3, (i * 137.5) % 360];

function kosmosShader(c) {
  const gl = c.getContext("webgl", { antialias: false, alpha: false, preserveDrawingBuffer: true });
  if (!gl) return null;
  const sh = (typ, src) => { const s = gl.createShader(typ); gl.shaderSource(s, src); gl.compileShader(s); return s; };
  const pr = gl.createProgram();
  gl.attachShader(pr, sh(gl.VERTEX_SHADER, "attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}"));
  gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, KOSMOS_FS));
  gl.bindAttribLocation(pr, 0, "p");
  gl.linkProgram(pr);
  if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) return null;
  gl.useProgram(pr);
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  gl.enableVertexAttribArray(0);
  gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
  const uR = gl.getUniformLocation(pr, "R"), uT = gl.getUniformLocation(pr, "T"), px = new Uint8Array(4);
  return {
    rozmiar(w, h) { gl.viewport(0, 0, w, h); gl.uniform2f(uR, w, h); },
    // czas klatki z odczytem piksela (czeka na GPU): mierzy prawdziwy koszt rysowania
    rysuj(t) { const t0 = performance.now(); gl.uniform1f(uT, t); gl.drawArrays(gl.TRIANGLES, 0, 3); gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px); return performance.now() - t0; },
    zwolnij() { const e = gl.getExtension("WEBGL_lose_context"); if (e) e.loseContext(); },
  };
}

function MozgKosmos({ czesci }) {
  const ref = useRef(null), plotno = useRef(null), siatka = useRef(null);
  const klucz = czesci.map((d) => `${d.k}:${d.ile}`).join("|");
  useEffect(() => {
    const el = ref.current, c = plotno.current;
    const cicho = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
    const pkt = [...el.querySelectorAll(".j-kos-p")];
    let W = 0, H = 0, k = 1, raf = 0, ost = 0, koniec = 0, t = 0;
    let gl = kosmosShader(c), ruch = !!gl && !cicho;
    const ustaw = () => pkt.forEach((p, i) => {
      const [o, kat] = kosmosStart(i), a = ((kat + t * 0.4) * Math.PI) / 180, r = KOSMOS_ORBITY[o] * k, s = Math.sin(a);
      p.style.transform = `translate(${(W / 2 + r * Math.cos(a)).toFixed(1)}px,${(H / 2 - r * s).toFixed(1)}px)`;
      const g = s > 0.03 ? true : s < -0.03 ? false : p._g;      // podpis po zewnętrznej stronie orbity
      if (g !== p._g) { p._g = g; p.classList.toggle("is-gora", !!g); }
    });
    const rozmiar = () => {
      W = el.clientWidth; H = el.clientHeight; k = Math.min(H / 688, W / 620);
      siatka.current.setAttribute("viewBox", `${-W / 2} ${-H / 2} ${W} ${H}`);
      [...siatka.current.querySelectorAll("circle")].forEach((o, i) => o.setAttribute("r", (KOSMOS_ORBITY[i] * k).toFixed(1)));
      if (gl) { c.width = Math.round(W); c.height = Math.round(H); gl.rozmiar(c.width, c.height); }
      ustaw();
      if (gl) gl.rysuj(t);
    };
    const klatka = (ms) => {
      raf = 0;
      if (ms - ost >= 110) { t += (ost ? Math.min(ms - ost, 200) : 0) / 1000; ost = ms; ustaw(); gl.rysuj(t); }
      if (ms < koniec && !document.hidden) raf = requestAnimationFrame(klatka); else ost = 0;
    };
    // ruch na kilka sekund (wejście, mysz nad mapą); poza tym mapa stoi i nie zużywa procesora
    const rusz = (s) => {
      if (!ruch) return;
      koniec = Math.max(koniec, performance.now() + s * 1000);
      if (!raf) raf = requestAnimationFrame(klatka);
    };
    rozmiar();
    if (gl) {
      const koszt = gl.rysuj(t);
      if (koszt > 160) ruch = false;              // za wolny sprzęt: ostra, nieruchoma klatka
    } else el.classList.add("is-css");
    rusz(8);
    const nad = () => rusz(4);
    el.addEventListener("pointermove", nad);
    const ro = new ResizeObserver(rozmiar);
    ro.observe(el);
    return () => { cancelAnimationFrame(raf); ro.disconnect(); el.removeEventListener("pointermove", nad); if (gl) gl.zwolnij(); gl = null; };
  }, [klucz]);
  const maks = Math.max(1, ...czesci.map((d) => d.ile));
  return html`<div class="j-kos" ref=${ref} data-kosmos="">
    <canvas ref=${plotno} aria-hidden="true"></canvas>
    <div class="j-kos-dz" aria-hidden="true"><i class="j-okr is-h"></i><i class="j-okr is-c"></i><i class="j-okr is-d"></i></div>
    <svg class="j-kos-siatka" ref=${siatka} aria-hidden="true">${KOSMOS_ORBITY.map((r) => html`<circle key=${r} cx="0" cy="0" r=${r}/>`)}</svg>
    ${czesci.map((d) => html`<a key=${d.k} class="j-kos-p" href=${d.href} style=${{ "--b": `${2 * Math.round(2.4 + Math.sqrt(d.ile) / 5)}px`, "--u": d.ile / maks }}>
      <i aria-hidden="true"></i><span>${d.nazwa}<em>${d.ile}</em></span></a>`)}
    <p class="j-kos-podp is-l" aria-hidden="true">${L("Kliknij część, żeby wejść.", "Click a part to go in.")}</p>
    <p class="j-kos-podp is-p" aria-hidden="true">${L("horyzont zdarzeń · tu nic nie ginie", "event horizon · nothing is lost here")}</p>
  </div>`;
}

if (typeof Zasoby !== "undefined" && Zasoby.daj) Zasoby.daj({ MozgKosmos });
