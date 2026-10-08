// Tarjeta de Lovelace del robot McCulloch / Husqvarna (integración mcculloch_rob), y de un segundo robot
// (otro McCulloch o un Worx Landroid de la integración Landroid Cloud) en la misma tarjeta.
// La sirve la propia integración: no hay que instalar nada aparte, solo añadir la tarjeta.
const BASE = new URL('.', import.meta.url).pathname;
const VER = new URL(import.meta.url).search;  // ?v=<versión>: HA sirve www con caché larga, así cambia con cada versión

const T = {
  es: {
    mowing: 'Cortando', homing: 'Volviendo a la base', leaving: 'Saliendo de la base', charging: 'Cargando',
    docked: 'En la base', paused: 'En pausa', idle: 'Parado', offline: 'Fuera de alcance', error: 'Avería',
    lifted: 'Levantado', upside: 'Volcado', start: 'Cortar', pause: 'Pausa', dock: 'A la base',
    mow1: 'Cortar 1 h', mow3: 'Cortar 3 h', parkNext: 'Aparcar hasta el próximo turno', resume: 'Volver al horario', edgecut: 'Cortar solo los bordes',
    next: 'Próximo corte', today: 'hoy', tomorrow: 'mañana', none: 'sin programación', battery: 'Batería', lastData: 'último dato', lastSeen: 'Última conexión',
    offlineMsg: 'El robot no está al alcance del Bluetooth. Se reconecta solo al volver cerca del receptor.',
    offlineLd: 'No llega a la nube de Worx (sin Wi-Fi o apagado). Se reconecta solo.',
    rain: 'Llueve: espera a que se seque el césped', noLink: 'Sin conexión', noneOff: 'el horario se verá al conectar',
    pick: 'Robot (entidad lawn_mower)', name: 'Nombre que se ve (opcional)', noEntity: 'No encuentro la entidad',
    pick2: 'Segundo robot (opcional): otro McCulloch o un Landroid', name2: 'Nombre del segundo robot (opcional)',
    image: 'Foto propia del primer robot (opcional): URL de un PNG/WebP transparente',
    rename: 'Cambiar el nombre', renameFail: 'No se pudo cambiar el nombre (hace falta un usuario administrador)',
  },
  en: {
    mowing: 'Mowing', homing: 'Going home', leaving: 'Leaving the dock', charging: 'Charging',
    docked: 'Docked', paused: 'Paused', idle: 'Stopped', offline: 'Out of range', error: 'Error',
    lifted: 'Lifted', upside: 'Upside down', start: 'Mow', pause: 'Pause', dock: 'Dock',
    mow1: 'Mow 1 h', mow3: 'Mow 3 h', parkNext: 'Park until next run', resume: 'Resume schedule', edgecut: 'Cut edges only',
    next: 'Next run', today: 'today', tomorrow: 'tomorrow', none: 'no schedule', battery: 'Battery', lastData: 'last known', lastSeen: 'Last seen',
    offlineMsg: 'The mower is out of Bluetooth range. It reconnects by itself when it comes back near the receiver.',
    offlineLd: 'It cannot reach the Worx cloud (no Wi-Fi or switched off). It reconnects by itself.',
    rain: 'Raining: waiting for the lawn to dry', noLink: 'Offline', noneOff: 'schedule shows up once connected',
    pick: 'Mower (lawn_mower entity)', name: 'Display name (optional)', noEntity: 'Entity not found',
    pick2: 'Second mower (optional): another McCulloch or a Landroid', name2: 'Second mower name (optional)',
    image: 'Own photo of the first mower (optional): URL of a transparent PNG/WebP',
    rename: 'Rename', renameFail: 'Could not rename (an administrator user is needed)',
  },
};

const ICON = {
  mowing: '<path d="M3 20h18"/><path d="M6 20c0-4 1-7 3-9M12 20c0-5 0-8 1-11M18 20c0-4-1-6-3-8"/>',
  charging: '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>', docked: '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/>',
  homing: '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/>', leaving: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  paused: '<path d="M8 5v14M16 5v14"/>', error: '<path d="M12 3 2 21h20z"/><path d="M12 10v5M12 18v.5"/>',
  upside: '<path d="M12 3 2 21h20z"/><path d="M12 10v5M12 18v.5"/>', lifted: '<path d="M12 20V5M6 11l6-6 6 6"/>',
  offline: '<path d="M2 2l20 20"/><path d="M8.5 16.5a5 5 0 0 1 7 0M5 12.6a10 10 0 0 1 5-2.5M19 12.6a10 10 0 0 0-2.4-1.7M12 20h.01"/>',
  idle: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
};
const COLOR = {mowing: '#47d35a', homing: '#47d35a', leaving: '#47d35a', charging: '#3fa9ff', docked: '#ffc20e',
  paused: '#ffc20e', idle: '#ffc20e', error: '#ff3b30', upside: '#ff3b30', lifted: '#ff9f0a', offline: '#8a8f92'};

// textos de las averías (los mismos que el panel y la integración); se cargan una vez para todas las tarjetas
let ERRS = null;
const errsReady = fetch(BASE + 'errores_es.json' + VER).then(r => r.json()).then(j => { ERRS = j; }).catch(() => { ERRS = {}; });

const CSS = `
:host{display:block}
ha-card{overflow:hidden}
.rbar{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:10px 10px 8px}
.rbar[hidden]{display:none}
/* cada robot con su foto y su color de marca: el elegido, relleno; el otro, solo con el borde */
.rbar button{--k:#ffc20e;position:relative;display:flex;align-items:center;gap:8px;min-width:0;border:1.5px solid color-mix(in srgb,var(--k) 45%,transparent);border-radius:14px;padding:6px 8px;cursor:pointer;
  background:color-mix(in srgb,var(--k) 8%,transparent);color:var(--primary-text-color);font:650 13.5px/1.2 system-ui,sans-serif;text-align:left;transition:background .25s,border-color .25s,transform .15s,box-shadow .25s}
.rbar button.ld{--k:#f38a12}
.rbar button:active{transform:scale(.97)}
.rbar button.on{background:var(--k);border-color:var(--k);color:#1b1b1b;box-shadow:0 4px 14px color-mix(in srgb,var(--k) 40%,transparent)}
.rbar .th{width:38px;height:28px;flex:none;object-fit:contain;filter:drop-shadow(0 2px 3px rgba(0,0,0,.3))}
.rbar .rtx{display:flex;flex-direction:column;min-width:0;flex:1}
.rbar b{overflow-wrap:anywhere}
.rbar small{display:flex;align-items:center;gap:5px;opacity:.75;font-weight:550;font-size:11.5px}
.rbar button.on small{opacity:.8}
.rbar .pen{flex:none;width:28px;height:28px;display:grid;place-items:center;border-radius:9px;background:rgba(0,0,0,.12)}
.rbar .pen svg{width:15px;height:15px;fill:none;stroke:currentColor;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}
.rbar input{flex:1;min-width:0;border:0;border-radius:8px;padding:6px 8px;font:650 13.5px system-ui,sans-serif;background:rgba(255,255,255,.9);color:#1b1b1b}
.scene.swap .bot,.scene.swap .dockw{animation:swapin .35s cubic-bezier(.2,.7,.2,1)}
@keyframes swapin{from{opacity:0;transform:translateX(-50%) translateY(6px)}}
.rbar i{width:7px;height:7px;border-radius:50%;flex:none;background:var(--c,#8a8f92);box-shadow:0 0 0 1.5px rgba(255,255,255,.55)}
/* jardín: cielo, setos al fondo y césped con franjas anchas de corte (igual que la app) */
.scene{position:relative;height:190px;overflow:hidden;background:linear-gradient(to bottom,#26323d 0%,#2f3b41 34%,#3a4636 52%,#1c2617 78%,#141b11 100%)}
.scene::before{content:"";position:absolute;left:-4%;right:-4%;top:30%;height:24%;pointer-events:none;filter:blur(.6px);opacity:.95;
  background:radial-gradient(30px 26px at 50% 100%,#1d3519 64%,transparent 66%) 0 100%/46px 70% repeat-x,
    radial-gradient(40px 34px at 50% 100%,#24421f 64%,transparent 66%) 16px 100%/64px 88% repeat-x,
    linear-gradient(to top,#1a2f16 0 26%,transparent 26%)}
.ground{position:absolute;left:-40%;right:-40%;bottom:-6%;height:64%;perspective:380px;perspective-origin:50% -30%;-webkit-mask:linear-gradient(to bottom,transparent,#000 30%);mask:linear-gradient(to bottom,transparent,#000 30%)}
.plane{position:absolute;inset:-40% 0 0;transform:rotateX(64deg);transform-origin:50% 100%;animation:roll 1.6s linear infinite paused;
  background:radial-gradient(circle at 30% 40%,rgba(214,252,160,.16) 0 .8px,transparent 1.3px) 0 0/5px 7px,
  radial-gradient(circle at 70% 60%,rgba(0,0,0,.26) 0 .9px,transparent 1.5px) 0 0/4px 5px,
  repeating-linear-gradient(90deg,rgba(255,255,255,.035) 0 2px,transparent 2px 9px) 0 0/9px 100%,
  linear-gradient(90deg,#2d5627 0 50%,#3b7033 50% 100%) 0 0/150px 100%}
.ground::before{content:"";position:absolute;inset:0;z-index:1;background:radial-gradient(38% 62% at 50% 86%,rgba(255,244,206,.12),transparent 70%)}
.ground::after{content:"";position:absolute;inset:0;background:linear-gradient(to bottom,rgba(20,27,17,.85),rgba(20,27,17,0) 50%)}
@keyframes roll{to{background-position:20px 0,20px 0,18px 0,150px 0}}
.s-homing .plane{animation-play-state:running}
.s-leaving .plane{animation-play-state:running;animation-direction:reverse}
.bot{position:absolute;left:50%;bottom:10%;width:min(48%,230px);transform:translateX(-50%);transition:left .9s,bottom .6s,filter .4s,opacity .4s;perspective:700px}
.b3d{position:relative;transform-style:preserve-3d;transition:transform .9s cubic-bezier(.45,0,.25,1)}
.b3d .fx{position:absolute;inset:0;z-index:2;pointer-events:none}
.r3d.s-mowing .b3d{animation:none}            /* con renders el giro lo hacen los fotogramas */
.b3d.back .fx{transform:scaleX(-1)}           /* de espaldas: recortes al otro lado */
.r3d .bot img{filter:drop-shadow(0 10px 12px rgba(0,0,0,.35))}
/* Landroid sin renders propios: el modelo del McCulloch teñido de naranja */
.tint .bot img,.tint .dockw img{filter:hue-rotate(-24deg) saturate(1.35) drop-shadow(0 10px 12px rgba(0,0,0,.35))}
/* tamaño por la altura de la escena (190 px), no por el ancho: en tarjetas anchas no se sale por arriba */
/* el render trae su sombra y un margen transparente abajo (~30 %): bajado para que pise el centro del césped */
.r3d .bot{width:min(64%,240px);bottom:-14%}.r3d .bot .sh{display:none}
.r3d.s-lifted .bot{bottom:-2%}
.bot img{display:block;width:100%;filter:drop-shadow(0 12px 14px rgba(0,0,0,.5));position:relative;z-index:1}
.bot .sh{position:absolute;left:4%;right:0;bottom:-1%;height:16%;border-radius:50%;background:radial-gradient(closest-side,rgba(0,0,0,.75),transparent);filter:blur(4px)}
.bot .glow{position:absolute;inset:-6% -6% 0;border-radius:50%;opacity:0;transition:opacity .4s}
/* cortando: cruza, media vuelta en 3D y vuelve; posición y giro con la misma duración */
.s-mowing .bot{animation:mowpass 14s ease-in-out infinite}.s-mowing .b3d{animation:mowturn 14s ease-in-out infinite}
.s-mowing img,.s-homing img,.s-leaving img{animation:bump .3s ease-in-out infinite}
.s-homing .bot{animation:home 5s ease-in-out infinite}.s-leaving .bot{animation:home 5s ease-in-out infinite reverse}
@keyframes mowpass{0%{left:66%}40%{left:34%}50%{left:34%}90%{left:66%}100%{left:66%}}
@keyframes mowturn{0%,40%{transform:rotateY(0)}50%,90%{transform:rotateY(180deg)}100%{transform:rotateY(360deg)}}
.s-docked .b3d{transform:rotateY(-16deg)}.s-lifted .b3d{transform:rotateX(-14deg) rotateZ(5deg)}
@keyframes home{0%{left:62%}100%{left:40%}}
@keyframes bump{50%{transform:translateY(-1.5px) rotate(-.5deg)}}
.s-charging .glow{opacity:1;background:radial-gradient(closest-side,rgba(63,169,255,.55),transparent);animation:breathe 2.4s infinite}
.s-error .glow,.s-upside .glow{opacity:1;background:radial-gradient(closest-side,rgba(255,59,48,.6),transparent);animation:breathe 1s infinite}
.s-upside .b3d{transform:rotateX(180deg) translateY(-8%)}
/* volcado con render: al voltearlo, la sombra quedaría arriba y el robot bajo la hierba */
.r3d.s-upside .bot{bottom:-4%}.r3d.s-upside .bot img{filter:none}
/* base de carga (render con la misma cámara que el robot: mismo ancho = encajan) y su piloto */
.dockw{position:absolute;left:50%;bottom:4%;width:min(64%,240px);transform:translateX(-50%);opacity:0;transition:opacity .6s;pointer-events:none}
.dockw img{display:block;width:100%}
.led{position:absolute;width:7px;height:7px;margin:-3.5px 0 0 -3.5px;border-radius:50%;background:#46e07a;box-shadow:0 0 7px 3px rgba(70,224,122,.75);opacity:0;transition:opacity .4s}
.r3d.s-docked .dockw,.r3d.s-charging .dockw,.r3d.s-homing .dockw,.r3d.s-leaving .dockw{opacity:1}
.r3d.s-docked .led{opacity:.9}
.r3d.s-charging .led{opacity:1;animation:ledblink 1.3s ease-in-out infinite}
@keyframes ledblink{50%{opacity:.15}}
.r3d.s-docked .bot,.r3d.s-charging .bot{left:50%;bottom:5%}
.r3d.s-docked .b3d{transform:none}
/* llegar a la base: se acerca y se queda a medio entrar (aparcado solo lo dice «En la base»); salir: marcha atrás */
.r3d.s-homing .bot{animation:home3d 6s cubic-bezier(.3,.1,.25,1) infinite;bottom:5%}
.r3d.s-leaving .bot{animation:leave3d 6s cubic-bezier(.5,0,.7,.9) infinite;bottom:5%}
@keyframes home3d{0%{left:100%;opacity:0}14%{opacity:1}78%{left:65%;opacity:1}92%{left:64%;opacity:1}100%{left:64%;opacity:0}}
@keyframes leave3d{0%,18%{left:50%;opacity:1}85%{opacity:1}100%{left:100%;opacity:0}}
.s-lifted .bot{bottom:24%;animation:float 2.4s ease-in-out infinite}
.s-offline .bot{filter:grayscale(1) brightness(.85) contrast(.9)}
@keyframes breathe{50%{opacity:.35}}
@keyframes float{50%{transform:translateX(-50%) translateY(-8px) rotate(2deg)}}
.fx b{position:absolute;bottom:6%;width:3px;height:7px;border-radius:2px;background:#8fdc6f;opacity:0;animation:clip 1s linear infinite}
.s-mowing .fx b{display:block}.fx b{display:none}
@keyframes clip{0%{opacity:0;transform:none}12%{opacity:1}100%{opacity:0;transform:translate(var(--dx),var(--dy)) rotate(260deg)}}
/* etiqueta y batería en la misma fila: nunca se pisan (la etiqueta es corta; el detalle va en el aviso de abajo) */
.top{position:absolute;left:12px;right:12px;top:10px;z-index:3;display:flex;gap:8px;justify-content:space-between;align-items:flex-start;pointer-events:none}
.pill{display:inline-flex;align-items:center;gap:7px;min-width:0;font:700 13px/1.25 system-ui,sans-serif;color:#fff;padding:7px 12px;border-radius:16px;background:rgba(0,0,0,.5);backdrop-filter:blur(6px);border-left:3px solid var(--c);transition:border-color .4s}
.pill span{overflow-wrap:anywhere}
.pill.bump{animation:pillin .35s cubic-bezier(.2,.8,.2,1)}
@keyframes pillin{from{opacity:0;transform:translateY(-4px)}}
.pill svg{width:15px;height:15px;flex:none;fill:none;stroke:var(--c);stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}
.bat{flex:none;display:flex;align-items:center;gap:6px;font:700 13px/1 system-ui,sans-serif;color:#fff;padding:7px 10px;border-radius:99px;background:rgba(0,0,0,.5)}
.bat i{position:relative;width:22px;height:11px;border:2px solid rgba(255,255,255,.8);border-radius:3px}
.bat i::after{content:"";position:absolute;right:-5px;top:2px;width:2px;height:4px;background:rgba(255,255,255,.8);border-radius:1px}
.bat i b{position:absolute;left:1px;top:1px;bottom:1px;border-radius:1px;background:var(--bc,#47d35a)}
.body{padding:12px 16px 4px}
.title{display:flex;flex-direction:column;gap:2px}[hidden]{display:none!important}
.title b{font-size:17px}.title span{color:var(--secondary-text-color);font-size:13px}
.alert{margin:10px 0 0;padding:8px 10px;border-radius:10px;font-size:13px;background:rgba(255,59,48,.12);color:var(--error-color,#ff3b30)}
.alert.warn{background:rgba(255,159,10,.12);color:var(--warning-color,#ff9f0a)}
.alert.info{background:rgba(63,169,255,.12);color:var(--info-color,#3fa9ff)}
.acts{display:grid;grid-template-columns:1.2fr 1fr 1fr;gap:8px;padding:12px 16px 8px}
.acts button,.chips button{font:600 14px system-ui,sans-serif;border:0;border-radius:12px;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:6px;color:var(--primary-text-color);background:var(--secondary-background-color,rgba(127,127,127,.15));padding:11px 6px;white-space:nowrap}
.acts button.main{background:var(--accent,#ffc20e);color:#111}
.acts button:disabled,.chips button:disabled{opacity:.45;cursor:default}
.acts svg{width:18px;height:18px}
.chips{display:flex;flex-wrap:wrap;gap:6px;padding:0 16px 14px}
.chips button{font-size:12.5px;padding:7px 11px;border-radius:99px}
.chips button[hidden]{display:none}
@media (prefers-reduced-motion:reduce){.scene *{animation:none!important}}
`;

const HTML = `
<ha-card>
  <div class="rbar" id="rbar" hidden></div>
  <div class="scene" id="scene">
    <div class="ground"><div class="plane"></div></div>
    <div class="dockw"><img class="dock3d" alt="" draggable="false"><i class="led"></i></div>
    <div class="bot"><div class="sh"></div><div class="b3d"><img alt="" draggable="false"><div class="fx" id="fx"></div></div><span class="glow"></span></div>
    <div class="top">
      <span class="pill" id="pill"><svg viewBox="0 0 24 24"></svg><span></span></span>
      <span class="bat" id="bat"><i><b></b></i><span></span></span>
    </div>
  </div>
  <div class="body">
    <div class="title"><b id="name"></b><span id="next"></span></div>
    <div id="alert"></div>
  </div>
  <div class="acts">
    <button class="main" data-a="start"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg><span></span></button>
    <button data-a="pause"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 5h4v14H6zM14 5h4v14h-4z"/></svg><span></span></button>
    <button data-a="dock"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/></svg><span></span></button>
  </div>
  <div class="chips">
    <button data-b="mow_1h"></button><button data-b="mow_3h"></button>
    <button data-b="park_next"></button><button data-b="resume_schedule"></button><button data-b="edgecut"></button>
  </div>
</ha-card>`;

// entidades del McCulloch creadas antes de tener translation_key: se reconocen por su id en español
const SLUG = {bateria: 'battery', actividad: 'activity', estado: 'state', error: 'error', proximo_arranque: 'next_start',
  cargando: 'charging', averia: 'problem', en_la_base: 'in_station', levantado: 'lifted', volcado: 'upside_down',
  cortar_1_hora: 'mow_1h', cortar_3_horas: 'mow_3h', aparcar_hasta_el_proximo_turno: 'park_next',
  volver_a_la_programacion: 'resume_schedule', programacion_tareas: 'schedule', ultima_conexion: 'last_seen'};

class McCullochRobCard extends HTMLElement {
  setConfig(config) {
    if (!config || !config.entity || !config.entity.startsWith('lawn_mower.')) throw new Error('entity: lawn_mower.xxx');
    if (config.entity_2 && !config.entity_2.startsWith('lawn_mower.')) throw new Error('entity_2: lawn_mower.xxx');
    const imageChanged = this._config && this._config.image !== config.image, prevSel = this._sel;
    this._config = config;
    this._idsBy = {};
    if (!this._robots().some(r => r.entity === this._sel)) {
      let saved = null;
      try { saved = localStorage.getItem('mcrob_sel_' + config.entity); } catch (e) { /* sin almacenamiento */ }
      this._sel = this._robots().some(r => r.entity === saved) ? saved : config.entity;
    }
    // el editor cambia la foto o el robot (p. ej. un McCulloch por un Landroid) sin recargar: fuera los
    // fotogramas y el tono del anterior
    if ((imageChanged || (prevSel && this._sel !== prevSel)) && this.shadowRoot) {
      this._fr = null;
      const scene = this.shadowRoot.getElementById('scene');
      if (scene) { scene.classList.remove('r3d', 'tint'); scene.dataset.s = ''; }
      this._setImage();
    }
  }

  _robots() {
    const c = this._config;
    return [{entity: c.entity, name: c.name}, c.entity_2 ? {entity: c.entity_2, name: c.name_2} : null].filter(Boolean);
  }

  // cambiar el nombre desde la barra: se guarda en el registro de entidades de HA (lo ve todo el mundo, en
  // cualquier móvil). Vacío = vuelve al nombre de siempre. Enter o salir del campo guarda; Esc cancela.
  _rename(btn) {
    if (!btn || this._renaming) return;
    const entity = btn.dataset.e, b = btn.querySelector('b');
    const inp = document.createElement('input');
    inp.value = b.textContent; inp.maxLength = 40; inp.setAttribute('aria-label', this._t('rename'));
    this._renaming = true;
    btn.querySelector('.rtx').replaceWith(inp); btn.querySelector('.pen')?.remove();
    inp.focus(); inp.select();
    let done = false;
    const finish = async save => {
      if (done) return; done = true;
      const v = inp.value.trim();
      if (save && v !== b.textContent) {
        try { await this._hass.callWS({type: 'config/entity_registry/update', entity_id: entity, name: v || null}); }
        catch (err) { alert(this._t('renameFail')); }
      }
      this._renaming = false;
      this.shadowRoot.getElementById('rbar').dataset.k = '';  // redibuja con el nombre nuevo
      this._update();
    };
    inp.addEventListener('keydown', e => { if (e.key === 'Enter') finish(true); if (e.key === 'Escape') finish(false); });
    inp.addEventListener('blur', () => finish(true));
  }

  _kind(entity) { return this._hass?.entities?.[entity]?.platform === 'landroid_cloud' ? 'landroid' : 'mcculloch'; }

  // foto: la de la opción `image` (solo primer robot), si no los renders 3D de su modelo, y si no el dibujo
  _setImage() {
    const img = this.shadowRoot.querySelector('.bot img');  // la del robot (antes en el HTML va la de la base)
    const ld = this._kind(this._sel) === 'landroid', own = this._sel === this._config.entity && this._config.image;
    const srcs = [own, BASE + (ld ? 'rob3d_landroid/' : 'rob3d/') + 'turn_00.webp' + VER, BASE + 'rob3d/turn_00.webp' + VER, BASE + 'robot.webp' + VER, BASE + 'robot.svg' + VER].filter(Boolean);
    img.onerror = () => { srcs.shift(); if (srcs.length) img.src = srcs[0]; else img.onerror = null; };
    img.src = srcs[0];
    if (!own) this._load3d(ld); else { this._fr = null; this.shadowRoot.getElementById('scene').classList.remove('r3d', 'tint'); }
  }

  // Robot renderizado en Blender: 24 vistas cada 15°. Al cortar, el giro del final de cada pasada es real.
  _load3d(ld) {
    const dirs = ld ? ['rob3d_landroid/', 'rob3d/'] : ['rob3d/'];
    const scene = this.shadowRoot.getElementById('scene');
    const tryDir = i => {
      const dir = BASE + dirs[i];
      const fr = Array.from({length: 24}, (_, k) => `${dir}turn_${String(k).padStart(2, '0')}.webp${VER}`);  // con versión: nada viejo de caché
      return Promise.all(fr.map(src => new Promise((ok, ko) => { const im = new Image(); im.onload = ok; im.onerror = ko; im.src = src; })))
        .then(() => ({fr, dir, tint: ld && i > 0}))
        .catch(() => (i + 1 < dirs.length ? tryDir(i + 1) : null));
    };
    const want = this._sel;
    tryDir(0).then(got => {
      if (!got || want !== this._sel) return;  // sin renders, o ya se cambió de robot
      this._fr = got.fr; this._cur = -1;
      scene.classList.add('r3d');
      scene.classList.toggle('tint', got.tint);
      this.shadowRoot.querySelector('.dock3d').src = got.dir + 'base_side.webp' + VER;
      const led = this.shadowRoot.querySelector('.led');
      fetch(got.dir + 'meta.json' + VER).then(r => r.json()).then(m => {
        if (m.led) { led.style.left = m.led[0] + '%'; led.style.top = m.led[1] + '%'; }
      }).catch(() => {});
      if (!this._raf) this._raf = requestAnimationFrame(() => this._tick());
    });
  }

  _tick() {
    if (!this.isConnected || !this._fr) { this._raf = null; return; }  // tarjeta fuera de la pantalla: se para
    const scene = this.shadowRoot.getElementById('scene'), bot = this.shadowRoot.querySelector('.bot');
    let f = 0;
    if (scene.dataset.s === 'mowing') {
      const an = bot.getAnimations().find(a => a.animationName === 'mowpass');
      const ph = an && an.currentTime != null ? (an.currentTime % 14000) / 14000 : 0;
      f = ph < .4 ? 0 : ph < .5 ? (ph - .4) / .1 * 12 : ph < .9 ? 12 : 12 + (ph - .9) / .1 * 12;
    }
    // girado con el dedo: manda eso (con inercia); a los 3 s vuelve solo por el camino corto
    const u = this._drag;
    if (u.ang != null) {
      if (!u.on) {
        u.ang += u.vel; u.vel *= .93; if (Math.abs(u.vel) < .01) u.vel = 0;
        if (!u.vel && performance.now() - u.rel > 3000) {
          const diff = ((f - u.ang) % 24 + 36) % 24 - 12;
          u.ang += diff * .08;
          if (Math.abs(diff) < .25) u.ang = null;
        }
      }
      if (u.ang != null) f = u.ang;
    }
    u.shown = f;
    f = ((Math.round(f) % 24) + 24) % 24;
    if (f !== this._cur) {
      this._cur = f;
      this.shadowRoot.querySelector('.bot img').src = this._fr[f];
      this.shadowRoot.querySelector('.b3d').classList.toggle('back', f > 6 && f < 18);
    }
    // solo se sigue animando si hace falta (cortando, arrastrando o volviendo del giro): quieto, el móvil descansa
    if (scene.dataset.s === 'mowing' || u.ang != null || u.on) this._raf = requestAnimationFrame(() => this._tick());
    else this._raf = null;
  }

  _wake() { if (this._fr && !this._raf && this.isConnected) this._raf = requestAnimationFrame(() => this._tick()); }

  connectedCallback() {
    // al volver a la pantalla, reanudar el bucle de fotogramas si estaba parado
    if (this.shadowRoot) this._wake();
  }

  static getConfigElement() { return document.createElement('mcculloch-rob-card-editor'); }

  static getStubConfig(hass) {
    const ents = Object.values(hass.entities || {});
    const e = ents.find(x => x.platform === 'mcculloch_rob' && x.entity_id.startsWith('lawn_mower.'))
      || {entity_id: Object.keys(hass.states).find(id => id.startsWith('lawn_mower.')) || 'lawn_mower.robot'};
    const ld = ents.find(x => x.platform === 'landroid_cloud' && x.entity_id.startsWith('lawn_mower.'));
    return ld && ld.entity_id !== e.entity_id ? {entity: e.entity_id, entity_2: ld.entity_id} : {entity: e.entity_id};
  }

  getCardSize() { return 6; }
  getGridOptions() { return {columns: 12, min_columns: 6, rows: 'auto'}; }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (!this.shadowRoot) this._build();
    else if (first) this._setImage();
    this._update();
  }

  _t(k) { const l = (this._hass?.locale?.language || this._hass?.language || 'en').slice(0, 2); return (T[l] || T.en)[k]; }

  _errText(kind, code) {
    if (!code || ['ninguno', 'none', 'no_error', 'unknown', 'unavailable'].includes(code)) return '';
    const es = (this._hass?.locale?.language || 'es').startsWith('es');
    const tx = es && ERRS ? (ERRS[kind] || {})[code] || (ERRS.mcculloch || {})[code] : null;
    return tx || code.replace(/_/g, ' ').replace(/^./, x => x.toUpperCase());
  }

  _build() {
    const root = this.attachShadow({mode: 'open'});
    root.innerHTML = `<style>${CSS}</style>${HTML}`;
    this._setImage();
    errsReady.then(() => this._hass && this._update());
    const fx = root.getElementById('fx');
    for (let i = 0; i < 14; i++) {
      const b = document.createElement('b');
      b.style.left = (70 + Math.random() * 20) + '%';  // detrás del robot; gira con él
      b.style.setProperty('--dx', (20 + Math.random() * 60) + 'px');
      b.style.setProperty('--dy', -(25 + Math.random() * 50) + 'px');
      b.style.animationDelay = (Math.random()) + 's';
      fx.appendChild(b);
    }
    // girar el robot con el dedo: 300 px de arrastre = una vuelta; lo vertical sigue siendo scroll
    const scene = root.getElementById('scene'), u = this._drag = {ang: null, on: false, vel: 0, rel: 0, shown: 0};
    scene.style.touchAction = 'pan-y';
    scene.addEventListener('pointerdown', e => {
      if (e.button > 0 || !this._fr) return;
      Object.assign(u, {on: true, x0: e.clientX, lx: e.clientX, lt: performance.now(), a0: u.ang ?? u.shown, vel: 0});
      scene.setPointerCapture?.(e.pointerId);
      this._wake();
    });
    scene.addEventListener('pointermove', e => {
      if (!u.on) return;
      const now = performance.now();
      u.ang = u.a0 + (e.clientX - u.x0) * 24 / 300;
      u.vel = (e.clientX - u.lx) * 24 / 300 / Math.max(1, now - u.lt) * 16;
      u.lx = e.clientX; u.lt = now;
    });
    const end = () => { if (!u.on) return; u.on = false; u.rel = performance.now(); if (performance.now() - u.lt > 80) u.vel = 0; };
    for (const ev of ['pointerup', 'pointercancel', 'lostpointercapture']) scene.addEventListener(ev, end);
    root.getElementById('rbar').addEventListener('click', e => {
      if (e.target.closest('input')) return;
      if (e.target.closest('[data-pen]')) { e.stopPropagation(); this._rename(e.target.closest('button')); return; }
      const b = e.target.closest('button'); if (!b || b.dataset.e === this._sel) return;
      this._sel = b.dataset.e;
      try { localStorage.setItem('mcrob_sel_' + this._config.entity, this._sel); } catch (err) { /* sin almacenamiento */ }
      this._fr = null; u.ang = null;
      scene.classList.remove('r3d', 'tint', 'swap'); void scene.offsetWidth; scene.classList.add('swap');
      setTimeout(() => scene.classList.remove('swap'), 400);
      root.getElementById('scene').dataset.s = '';
      this._setImage();
      this._update();
    });
    root.querySelector('.acts').addEventListener('click', e => {
      const b = e.target.closest('button'); if (!b) return;
      const svc = {start: 'start_mowing', pause: 'pause', dock: 'dock'}[b.dataset.a];
      this._call('lawn_mower', svc, this._sel);
    });
    root.querySelector('.chips').addEventListener('click', e => {
      const b = e.target.closest('button'); const id = b && this._ids(this._sel)[b.dataset.b];
      if (id) this._call('button', 'press', id);
    });
  }

  // una orden que falla (robot que dice que no, Bluetooth cortado) sale como aviso de HA, no se pierde en silencio
  _call(domain, service, entity_id) {
    this._hass.callService(domain, service, {entity_id}).catch(err => this.dispatchEvent(new CustomEvent('hass-notification', {
      detail: {message: err?.message || String(err)}, bubbles: true, composed: true})));
  }

  // Entidades hermanas del robot, por dispositivo: el McCulloch por su clave de traducción; el Landroid por
  // clase de dispositivo y por el final del id (Landroid Cloud no usa las mismas claves en todas las versiones)
  _ids(entity) {
    const h = this._hass;
    if (h.entities !== this._entsRef) { this._idsBy = {}; this._entsRef = h.entities; }
    if (this._idsBy[entity]) return this._idsBy[entity];
    const ents = h.entities || {}, me = ents[entity], ids = {};
    const ld = this._kind(entity) === 'landroid', prefix = entity.split('.')[1] + '_';
    if (me && me.device_id) {
      for (const e of Object.values(ents)) {
        if (e.device_id !== me.device_id) continue;
        const [dom, obj] = e.entity_id.split('.'), dc = h.states[e.entity_id]?.attributes?.device_class;
        let key;
        if (!ld) key = e.translation_key || SLUG[obj.replace(prefix, '')];
        else if (dom === 'sensor' && dc === 'battery') key = 'battery';
        else if (dom === 'binary_sensor' && dc === 'battery_charging') key = 'charging';
        else if (dom === 'binary_sensor' && dc === 'moisture') key = 'rain';
        else if (dom === 'sensor' && /(^|_)error$/.test(obj)) key = 'error';
        else if (dom === 'sensor' && /(proximo_horario|next_schedule)$/.test(obj)) key = 'next_start';
        else if (dom === 'sensor' && /(ultima_actualizacion|last_update)$/.test(obj)) key = 'last_seen';
        else if (dom === 'button' && /(corte_de_bordes|edge_?cut|border_?cut)$/.test(obj)) key = 'edgecut';
        if (key && !ids[key]) ids[key] = e.entity_id;
      }
    }
    return (this._idsBy[entity] = ids);
  }

  // estado resumido de un robot (el que se ve y los de la barra)
  _status(entity) {
    const h = this._hass, ids = this._ids(entity), st = k => (ids[k] ? h.states[ids[k]] : undefined);
    const on = k => st(k)?.state === 'on', mower = h.states[entity], kind = this._kind(entity);
    const val = k => { const s = st(k)?.state; return s && !['unknown', 'unavailable'].includes(s) ? s : null; };
    const act = val('activity'), state = val('state'), bat = val('battery') == null ? NaN : Number(val('battery'));
    const offline = !mower || mower.state === 'unavailable';
    const err = val('error');
    const ldErr = kind === 'landroid' && err && !['no_error', 'unknown', 'rain_delay'].includes(err);
    const charging = on('charging');
    const lifted = on('lifted') || (kind === 'landroid' && err === 'lifted');
    const upside = on('upside_down') || (kind === 'landroid' && err === 'upside_down');
    const error = on('problem') || state === 'error' || state === 'fatal_error' || mower?.state === 'error' || (ldErr && !lifted && !upside);
    const moving = ['mowing', 'going_out', 'going_home'].includes(act) || (!act && ['mowing', 'edgecut'].includes(mower?.state));
    const s = offline ? 'offline' : upside ? 'upside' : lifted ? 'lifted' : error ? 'error' : charging ? 'charging'
      : act === 'going_home' || mower?.state === 'returning' ? 'homing' : act === 'going_out' ? 'leaving'
      : moving ? 'mowing' : (on('in_station') || act === 'parked' || act === 'charging' || mower?.state === 'docked') ? 'docked'
      : state === 'paused' || mower?.state === 'paused' ? 'paused' : 'idle';
    const rain = kind === 'landroid' && (on('rain') || err === 'rain_delay');
    return {s, bat, charging, offline, err, kind, rain, mower, ids, st};
  }

  _update() {
    const c = this._config, h = this._hass, r = this.shadowRoot;
    if (!this._robots().some(x => x.entity === this._sel)) this._sel = c.entity;
    const robots = this._robots();
    // nombre: el que se le puso desde la tarjeta (registro de HA, igual en todos los móviles), si no el de la config
    const name = x => h.entities?.[x.entity]?.name || x.name || h.states[x.entity]?.attributes?.friendly_name || x.entity.split('.')[1];
    // barra de robots: solo con dos; cada uno con su foto, su color, su estado y su batería
    const bar = r.getElementById('rbar');
    bar.hidden = robots.length < 2;
    if (robots.length > 1 && !this._renaming) {
      const key = robots.map(x => { const q = this._status(x.entity); return [x.entity, q.s, q.bat, name(x), x.entity === this._sel].join('|'); }).join(';');
      if (bar.dataset.k !== key) {
        bar.dataset.k = key;
        bar.replaceChildren(...robots.map(x => {
          const q = this._status(x.entity), b = document.createElement('button'), on = x.entity === this._sel;
          b.dataset.e = x.entity;
          b.className = (on ? 'on ' : '') + (q.kind === 'landroid' ? 'ld' : '');
          b.innerHTML = `<img class="th" alt=""><span class="rtx"><b></b><small><i></i><span></span></small></span>`
            + (on ? `<span class="pen" data-pen title="${this._t('rename')}"><svg viewBox="0 0 24 24"><path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M14 6l4 4"/></svg></span>` : '');
          b.querySelector('.th').src = `${BASE}${q.kind === 'landroid' ? 'rob3d_landroid' : 'rob3d'}/icono.webp${VER}`;
          b.querySelector('i').style.setProperty('--c', COLOR[q.s]);
          b.querySelector('b').textContent = name(x);
          const st = q.s === 'offline' && q.kind === 'landroid' ? this._t('noLink') : this._t(q.s);
          b.querySelector('small span').textContent = isNaN(q.bat) ? st : `${st} · ${q.bat}%`;
          return b;
        }));
      }
    }
    const me = robots.find(x => x.entity === this._sel);
    const q = this._status(this._sel), {s, bat, charging, offline, kind, mower} = q;
    r.getElementById('name').textContent = mower ? name(me) : this._t('noEntity');
    const scene = r.getElementById('scene');
    if (scene.dataset.s !== s) {
      scene.classList.remove(...[...scene.classList].filter(k => k.startsWith('s-'))); scene.classList.add('s-' + s); scene.dataset.s = s;
      this._wake();  // pone la vista que toca al nuevo estado (y sigue animando si corta)
    }
    const pill = r.getElementById('pill');
    pill.style.setProperty('--c', COLOR[s]);
    pill.firstChild.innerHTML = ICON[s];
    const label = s === 'offline' && kind === 'landroid' ? this._t('noLink') : this._t(s);
    // la etiqueta, corta; la avería concreta, en el aviso de abajo
    let detail = label;
    if (s === 'error') { const e = this._errText(kind, q.err); if (e) detail = `${label}: ${e}`; }
    if (pill.lastChild.textContent !== label) {
      pill.lastChild.textContent = label;
      pill.classList.remove('bump'); void pill.offsetWidth; pill.classList.add('bump');
    }
    const batEl = r.getElementById('bat');
    batEl.hidden = isNaN(bat);
    if (!isNaN(bat)) {
      batEl.lastChild.textContent = (charging ? '⚡ ' : '') + bat + '%';
      const fill = batEl.querySelector('b');
      fill.style.width = Math.max(4, bat * .17) + 'px';
      fill.style.setProperty('--bc', bat < 20 ? '#ff3b30' : bat < 40 ? '#ffc20e' : '#47d35a');
    }
    const nx = q.st('next_start');
    // sin conexión y sin nada guardado no se sabe el horario: nunca se dice «sin programación» a ciegas
    let nextTxt = this._t(offline ? 'noneOff' : 'none');
    // horario: el de ahora si el robot está conectado; si no, el último guardado en este navegador.
    // Una lista vacía con tareas contadas es una lectura fallida: no vale ni borra la copia buena.
    const key = 'mcrob_tasks_' + this._sel;
    let tasks = q.st('schedule')?.attributes?.tareas, stale = false;
    if (Array.isArray(tasks) && !tasks.length && Number(q.st('schedule')?.state) > 0) tasks = undefined;
    try {
      if (Array.isArray(tasks)) {
        const txt = JSON.stringify(tasks);
        if (localStorage.getItem(key) !== txt) localStorage.setItem(key, txt);  // solo si cambió
      } else { tasks = JSON.parse(localStorage.getItem(key) || 'null'); stale = Array.isArray(tasks); }
    } catch (e) { /* almacenamiento bloqueado: sin respaldo */ }
    const fromSchedule = Array.isArray(tasks) ? this._nextFromTasks(tasks) : null;
    // el sensor guarda el último valor: si ya pasó (robot lejos), vale más el horario
    const nxOk = nx && !['unknown', 'unavailable', ''].includes(nx.state) && new Date(nx.state) > Date.now() - 6e4;
    if (!nxOk && fromSchedule) {
      nextTxt = this._t('next') + ' · ' + fromSchedule + (stale || offline ? ' · ' + this._t('lastData') : '');
    } else if (nxOk) {
      // en la zona horaria que use el perfil de HA (la del servidor salvo que el usuario pida la local)
      const tz = h.locale?.time_zone === 'local' ? undefined : h.config?.time_zone;
      const lang = h.locale?.language, d = new Date(nx.state);
      const day = x => new Date(x.toLocaleDateString('en-CA', {timeZone: tz}) + 'T00:00:00Z');
      const dd = Math.round((day(d) - day(new Date())) / 864e5);
      const tm = d.toLocaleTimeString(lang, {hour: '2-digit', minute: '2-digit', timeZone: tz});
      nextTxt = this._t('next') + ' · ' + (dd === 0 ? this._t('today') : dd === 1 ? this._t('tomorrow')
        : d.toLocaleDateString(lang, {weekday: 'short', day: 'numeric', timeZone: tz})) + ' ' + tm;
    }
    r.getElementById('next').textContent = nextTxt;
    // fuera de alcance: cuándo se supo de él por última vez (sensor siempre disponible)
    // sin la entidad (nombre mal escrito o integración quitada) no es un problema de Bluetooth ni de la nube
    let offTxt = !mower ? `${this._t('noEntity')}: ${this._sel}` : this._t(kind === 'landroid' ? 'offlineLd' : 'offlineMsg');
    const seen = new Date(q.st('last_seen')?.state);
    if (offline && !isNaN(seen)) {
      const mins = (seen - Date.now()) / 6e4;
      const rtf = new Intl.RelativeTimeFormat(h.locale?.language || 'es', {numeric: 'auto'});
      const rel = Math.abs(mins) < 120 ? rtf.format(Math.round(mins), 'minute') : Math.abs(mins) < 2880 ? rtf.format(Math.round(mins / 60), 'hour') : rtf.format(Math.round(mins / 1440), 'day');
      offTxt = `${this._t('lastSeen')}: ${rel}. ${offTxt}`;
    }
    const [alCls, alTxt] = offline ? ['alert warn', offTxt] : ['upside', 'lifted', 'error'].includes(s) ? ['alert', detail]
      : q.rain ? ['alert info', this._t('rain')] : ['', ''];
    const alEl = r.getElementById('alert');
    // el texto viene de un sensor: siempre como texto, nunca como HTML
    if (alEl.dataset.k !== alCls + alTxt) {
      alEl.dataset.k = alCls + alTxt;
      alEl.replaceChildren();
      if (alTxt) { const div = document.createElement('div'); div.className = alCls; div.textContent = alTxt; alEl.appendChild(div); }
    }
    r.querySelectorAll('.acts button').forEach(b => {
      b.lastChild.textContent = this._t(b.dataset.a);
      b.disabled = offline;
    });
    r.querySelector('.acts .main').style.setProperty('--accent', kind === 'landroid' ? '#f38a12' : '#ffc20e');
    // cada robot con sus órdenes: el McCulloch sus botones de horas/turno, el Landroid el corte de bordes
    const chipText = {mow_1h: 'mow1', mow_3h: 'mow3', park_next: 'parkNext', resume_schedule: 'resume', edgecut: 'edgecut'};
    r.querySelectorAll('.chips button').forEach(b => {
      b.textContent = this._t(chipText[b.dataset.b]);
      b.hidden = !q.ids[b.dataset.b];
      b.disabled = offline;
    });
  }

  // próximo arranque según las franjas del robot (lunes = 0), en la hora del navegador
  _nextFromTasks(tasks) {
    const DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
    const now = new Date(), nowMin = now.getHours() * 60 + now.getMinutes(), today = (now.getDay() + 6) % 7;
    for (let k = 0; k < 8; k++) {
      const d = (today + k) % 7;
      const m = tasks.filter(t => t['on_' + DAYS[d]]).map(t => t.start_time_in_minutes).filter(x => k > 0 || x > nowMin).sort((a, b) => a - b)[0];
      if (m == null) continue;
      const hm = String(Math.floor(m / 60)).padStart(2, '0') + ':' + String(m % 60).padStart(2, '0');
      const day = k === 0 ? this._t('today') : k === 1 ? this._t('tomorrow')
        : new Date(now.getTime() + k * 864e5).toLocaleDateString(this._hass.locale?.language, {weekday: 'short'});
      return day + ' ' + hm;
    }
    return null;
  }
}

class McCullochRobCardEditor extends HTMLElement {
  setConfig(config) { this._config = config; this._render(); }
  set hass(hass) { this._hass = hass; this._render(); }
  _render() {
    if (!this._hass || !this._config) return;
    if (!this._form) {
      this._form = document.createElement('ha-form');
      this._form.computeLabel = s => {
        const l = (this._hass.locale?.language || 'en').slice(0, 2), t = T[l] || T.en;
        return {entity: t.pick, name: t.name, entity_2: t.pick2, name_2: t.name2, image: t.image}[s.name];
      };
      this._form.schema = [
        {name: 'entity', required: true, selector: {entity: {domain: 'lawn_mower'}}},
        {name: 'name', selector: {text: {}}},
        {name: 'entity_2', selector: {entity: {domain: 'lawn_mower'}}},
        {name: 'name_2', selector: {text: {}}},
        {name: 'image', selector: {text: {}}},
      ];
      this._form.addEventListener('value-changed', e => {
        const cfg = {...e.detail.value};
        for (const k of ['entity_2', 'name', 'name_2', 'image']) if (!cfg[k]) delete cfg[k];
        this.dispatchEvent(new CustomEvent('config-changed', {detail: {config: cfg}, bubbles: true, composed: true}));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = this._config;
  }
}

// Algunas tarjetas de HACS cambian window.customElements por un polyfill de registros con ámbito después de que
// esta se haya registrado: el registro nuevo no la conoce y HA pinta «Custom element doesn't exist». Se vuelve a
// registrar (con una subclase, el mismo constructor no se puede definir dos veces) si desaparece.
function register(){
  for (const [tag, cls] of [['mcculloch-rob-card', McCullochRobCard], ['mcculloch-rob-card-editor', McCullochRobCardEditor]]) {
    if (customElements.get(tag)) continue;
    try { customElements.define(tag, class extends cls {}); } catch(e) { console.warn('mcculloch-rob-card:', e.message); }
  }
}
register();
[300, 1500, 5000, 15000].forEach(t => setTimeout(register, t));
if (!(window.customCards || []).some(c => c.type === 'mcculloch-rob-card')) {
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: 'mcculloch-rob-card', name: 'Robots cortacésped (McCulloch / Husqvarna / Landroid)',
    description: 'Uno o dos robots en una tarjeta: estado animado en 3D, batería, próximo corte, averías en español y sus órdenes', preview: true,
    documentationURL: 'https://github.com/odegaard12/ha-mcculloch-husqvarna-ble',
  });
}
