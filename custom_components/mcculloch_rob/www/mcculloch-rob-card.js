// Tarjeta de Lovelace del robot McCulloch / Husqvarna (integración mcculloch_rob).
// La sirve la propia integración: no hay que instalar nada aparte, solo añadir la tarjeta.
const BASE = new URL('.', import.meta.url).pathname;

const T = {
  es: {
    mowing: 'Cortando', homing: 'Volviendo a la base', leaving: 'Saliendo de la base', charging: 'Cargando',
    docked: 'En la base', paused: 'En pausa', idle: 'Parado', offline: 'Fuera de alcance', error: 'Avería',
    lifted: 'Levantado', upside: 'Volcado', start: 'Cortar', pause: 'Pausa', dock: 'A la base',
    mow1: 'Cortar 1 h', mow3: 'Cortar 3 h', parkNext: 'Aparcar hasta el próximo turno', resume: 'Volver al horario',
    next: 'Próximo corte', today: 'hoy', tomorrow: 'mañana', none: 'sin programación', battery: 'Batería',
    offlineMsg: 'El robot no está al alcance del Bluetooth. Se reconecta solo al volver cerca del receptor.',
    pick: 'Elige el robot (entidad lawn_mower)', name: 'Nombre (opcional)', noEntity: 'No encuentro la entidad',
    image: 'Foto propia (opcional): URL de un PNG/WebP transparente, p. ej. /local/robot.webp',
  },
  en: {
    mowing: 'Mowing', homing: 'Going home', leaving: 'Leaving the dock', charging: 'Charging',
    docked: 'Docked', paused: 'Paused', idle: 'Stopped', offline: 'Out of range', error: 'Error',
    lifted: 'Lifted', upside: 'Upside down', start: 'Mow', pause: 'Pause', dock: 'Dock',
    mow1: 'Mow 1 h', mow3: 'Mow 3 h', parkNext: 'Park until next run', resume: 'Resume schedule',
    next: 'Next run', today: 'today', tomorrow: 'tomorrow', none: 'no schedule', battery: 'Battery',
    offlineMsg: 'The mower is out of Bluetooth range. It reconnects by itself when it comes back near the receiver.',
    pick: 'Pick the mower (lawn_mower entity)', name: 'Name (optional)', noEntity: 'Entity not found',
    image: 'Own photo (optional): URL of a transparent PNG/WebP, e.g. /local/robot.webp',
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

const CSS = `
:host{display:block}
ha-card{overflow:hidden}
.scene{position:relative;height:190px;overflow:hidden;background:radial-gradient(90% 75% at 50% 30%,#3a3d40 0%,#232527 55%,#17191a 100%)}
.ground{position:absolute;left:-40%;right:-40%;bottom:-6%;height:64%;perspective:380px;perspective-origin:50% -30%;-webkit-mask:linear-gradient(to bottom,transparent,#000 38%);mask:linear-gradient(to bottom,transparent,#000 38%)}
.plane{position:absolute;inset:-40% 0 0;transform:rotateX(64deg);transform-origin:50% 100%;animation:roll 1.6s linear infinite paused;
  background:radial-gradient(circle at 30% 40%,rgba(200,245,150,.13) 0 .8px,transparent 1.3px) 0 0/5px 7px,
  radial-gradient(circle at 70% 60%,rgba(0,0,0,.22) 0 .9px,transparent 1.5px) 0 0/4px 5px,
  linear-gradient(90deg,#2b5126 0%,#376630 25%,#2b5126 50%,#376630 75%,#2b5126 100%) 0 0/360px 100%}
.ground::after{content:"";position:absolute;inset:0;background:linear-gradient(to bottom,rgba(23,25,26,.9),rgba(23,25,26,0) 55%)}
@keyframes roll{to{background-position:20px 0,20px 0,360px 0}}
.s-mowing .plane,.s-homing .plane{animation-play-state:running}
.s-leaving .plane{animation-play-state:running;animation-direction:reverse}
.bot{position:absolute;left:50%;bottom:10%;width:min(52%,250px);transform:translateX(-50%);transition:left .9s,bottom .6s,filter .4s,opacity .4s}
.bot img{display:block;width:100%;filter:drop-shadow(0 12px 14px rgba(0,0,0,.5));position:relative;z-index:1}
.bot .sh{position:absolute;left:4%;right:0;bottom:-1%;height:16%;border-radius:50%;background:radial-gradient(closest-side,rgba(0,0,0,.75),transparent);filter:blur(4px)}
.bot .glow{position:absolute;inset:-6% -6% 0;border-radius:50%;opacity:0;transition:opacity .4s}
.s-mowing .bot{animation:mow 6s ease-in-out infinite}
.s-mowing img,.s-homing img,.s-leaving img{animation:bump .3s ease-in-out infinite}
.s-homing .bot{animation:home 5s ease-in-out infinite}.s-leaving .bot{animation:home 5s ease-in-out infinite reverse}
@keyframes mow{0%,100%{left:47%}50%{left:53%}}
@keyframes home{0%{left:62%}100%{left:40%}}
@keyframes bump{50%{transform:translateY(-1.5px) rotate(-.5deg)}}
.s-charging .glow{opacity:1;background:radial-gradient(closest-side,rgba(63,169,255,.55),transparent);animation:breathe 2.4s infinite}
.s-error .glow,.s-upside .glow{opacity:1;background:radial-gradient(closest-side,rgba(255,59,48,.6),transparent);animation:breathe 1s infinite}
.s-upside img{transform:rotate(180deg)}
.s-lifted .bot{bottom:24%;animation:float 2.4s ease-in-out infinite}
.s-offline .bot{filter:grayscale(1) brightness(.75);opacity:.55}.s-offline .ground{filter:grayscale(.9) brightness(.6)}
@keyframes breathe{50%{opacity:.35}}
@keyframes float{50%{transform:translateX(-50%) translateY(-8px) rotate(2deg)}}
.fx b{position:absolute;bottom:14%;width:3px;height:7px;border-radius:2px;background:#8fdc6f;opacity:0;animation:clip 1s linear infinite}
.s-mowing .fx b{display:block}.fx b{display:none}
@keyframes clip{0%{opacity:0;transform:none}12%{opacity:1}100%{opacity:0;transform:translate(var(--dx),var(--dy)) rotate(260deg)}}
.pill{position:absolute;left:12px;top:10px;z-index:3;display:inline-flex;align-items:center;gap:7px;font:700 13px/1 system-ui,sans-serif;color:#fff;padding:7px 12px;border-radius:99px;background:rgba(0,0,0,.5);backdrop-filter:blur(6px);border-left:3px solid var(--c)}
.pill svg{width:15px;height:15px;fill:none;stroke:var(--c);stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}
.bat{position:absolute;right:12px;top:10px;z-index:3;display:flex;align-items:center;gap:6px;font:700 13px/1 system-ui,sans-serif;color:#fff;padding:7px 10px;border-radius:99px;background:rgba(0,0,0,.5)}
.bat i{position:relative;width:22px;height:11px;border:2px solid rgba(255,255,255,.8);border-radius:3px}
.bat i::after{content:"";position:absolute;right:-5px;top:2px;width:2px;height:4px;background:rgba(255,255,255,.8);border-radius:1px}
.bat i b{position:absolute;left:1px;top:1px;bottom:1px;border-radius:1px;background:var(--bc,#47d35a)}
.body{padding:12px 16px 4px}
.title{display:flex;flex-direction:column;gap:2px}[hidden]{display:none!important}
.title b{font-size:17px}.title span{color:var(--secondary-text-color);font-size:13px}
.alert{margin:10px 0 0;padding:8px 10px;border-radius:10px;font-size:13px;background:rgba(255,59,48,.12);color:var(--error-color,#ff3b30)}
.alert.warn{background:rgba(255,159,10,.12);color:var(--warning-color,#ff9f0a)}
.acts{display:grid;grid-template-columns:1.2fr 1fr 1fr;gap:8px;padding:12px 16px 8px}
.acts button,.chips button{font:600 14px system-ui,sans-serif;border:0;border-radius:12px;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:6px;color:var(--primary-text-color);background:var(--secondary-background-color,rgba(127,127,127,.15));padding:11px 6px;white-space:nowrap}
.acts button.main{background:#ffc20e;color:#111}
.acts button:disabled,.chips button:disabled{opacity:.45;cursor:default}
.acts svg{width:18px;height:18px}
.chips{display:flex;flex-wrap:wrap;gap:6px;padding:0 16px 14px}
.chips button{font-size:12.5px;padding:7px 11px;border-radius:99px}
.chips button[hidden]{display:none}
@media (prefers-reduced-motion:reduce){.scene *{animation:none!important}}
`;

const HTML = `
<ha-card>
  <div class="scene" id="scene">
    <div class="ground"><div class="plane"></div></div>
    <div class="bot"><div class="sh"></div><img alt="" draggable="false"><span class="glow"></span></div>
    <div class="fx" id="fx"></div>
    <span class="pill" id="pill"><svg viewBox="0 0 24 24"></svg><span></span></span>
    <span class="bat" id="bat"><i><b></b></i><span></span></span>
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
    <button data-b="park_next"></button><button data-b="resume_schedule"></button>
  </div>
</ha-card>`;

class McCullochRobCard extends HTMLElement {
  setConfig(config) {
    if (!config || !config.entity || !config.entity.startsWith('lawn_mower.')) throw new Error('entity: lawn_mower.xxx');
    this._config = config;
    this._ids = null;
  }

  static getConfigElement() { return document.createElement('mcculloch-rob-card-editor'); }

  static getStubConfig(hass) {
    const e = Object.values(hass.entities || {}).find(x => x.platform === 'mcculloch_rob' && x.entity_id.startsWith('lawn_mower.'))
      || {entity_id: Object.keys(hass.states).find(id => id.startsWith('lawn_mower.')) || 'lawn_mower.robot'};
    return {entity: e.entity_id};
  }

  getCardSize() { return 6; }
  getGridOptions() { return {columns: 12, min_columns: 6, rows: 'auto'}; }

  set hass(hass) {
    this._hass = hass;
    if (!this.shadowRoot) this._build();
    this._update();
  }

  _t(k) { const l = (this._hass?.locale?.language || this._hass?.language || 'en').slice(0, 2); return (T[l] || T.en)[k]; }

  _build() {
    const root = this.attachShadow({mode: 'open'});
    root.innerHTML = `<style>${CSS}</style>${HTML}`;
    // foto: la de la opción `image` (sobrevive a las actualizaciones), si no robot.webp junto a la tarjeta, y si no el dibujo
    const img = root.querySelector('img');
    const srcs = [this._config.image, BASE + 'robot.webp', BASE + 'robot.svg'].filter(Boolean);
    img.onerror = () => { srcs.shift(); if (srcs.length) img.src = srcs[0]; else img.onerror = null; };
    img.src = srcs[0];
    const fx = root.getElementById('fx');
    for (let i = 0; i < 14; i++) {
      const b = document.createElement('b');
      b.style.left = (54 + Math.random() * 16) + '%';
      b.style.setProperty('--dx', (20 + Math.random() * 60) + 'px');
      b.style.setProperty('--dy', -(25 + Math.random() * 50) + 'px');
      b.style.animationDelay = (Math.random()) + 's';
      fx.appendChild(b);
    }
    root.querySelector('.acts').addEventListener('click', e => {
      const b = e.target.closest('button'); if (!b) return;
      const svc = {start: 'start_mowing', pause: 'pause', dock: 'dock'}[b.dataset.a];
      this._hass.callService('lawn_mower', svc, {entity_id: this._config.entity});
    });
    root.querySelector('.chips').addEventListener('click', e => {
      const b = e.target.closest('button'); const id = b && this._ids[b.dataset.b];
      if (id) this._hass.callService('button', 'press', {entity_id: id});
    });
  }

  // Las entidades hermanas se buscan por dispositivo y clave, así funciona con cualquier nombre o idioma
  _resolve() {
    const ents = this._hass.entities || {}, me = ents[this._config.entity];
    const ids = {};
    const prefix = this._config.entity.split('.')[1] + '_';
    // entidades creadas antes de tener translation_key: se reconocen por su id en español
    const SLUG = {bateria: 'battery', actividad: 'activity', estado: 'state', error: 'error', proximo_arranque: 'next_start',
      cargando: 'charging', averia: 'problem', en_la_base: 'in_station', levantado: 'lifted', volcado: 'upside_down',
      cortar_1_hora: 'mow_1h', cortar_3_horas: 'mow_3h', aparcar_hasta_el_proximo_turno: 'park_next',
      volver_a_la_programacion: 'resume_schedule'};
    if (me && me.device_id) {
      for (const e of Object.values(ents)) {
        if (e.device_id !== me.device_id) continue;
        const key = e.translation_key || SLUG[e.entity_id.split('.')[1].replace(prefix, '')];
        if (key && !ids[key]) ids[key] = e.entity_id;
      }
    }
    this._ids = ids;
  }

  _st(key) { const id = this._ids[key]; return id ? this._hass.states[id] : undefined; }
  _on(key) { const s = this._st(key); return !!s && s.state === 'on'; }

  _update() {
    const c = this._config, h = this._hass, r = this.shadowRoot;
    if (!this._ids || !Object.keys(this._ids).length) this._resolve();
    const mower = h.states[c.entity];
    r.getElementById('name').textContent = c.name || (mower && mower.attributes.friendly_name) || this._t('noEntity');
    const act = this._st('activity')?.state, state = this._st('state')?.state;
    const bat = Number(this._st('battery')?.state);
    const offline = !mower || mower.state === 'unavailable';
    const charging = this._on('charging'), lifted = this._on('lifted'), upside = this._on('upside_down');
    const error = this._on('problem') || state === 'error' || state === 'fatal_error' || mower?.state === 'error';
    const moving = ['mowing', 'going_out', 'going_home'].includes(act) || (!act && mower?.state === 'mowing');
    const s = offline ? 'offline' : upside ? 'upside' : lifted ? 'lifted' : error ? 'error' : charging ? 'charging'
      : act === 'going_home' || mower?.state === 'returning' ? 'homing' : act === 'going_out' ? 'leaving'
      : moving ? 'mowing' : (this._on('in_station') || act === 'parked' || act === 'charging' || mower?.state === 'docked') ? 'docked'
      : state === 'paused' || mower?.state === 'paused' ? 'paused' : 'idle';
    const scene = r.getElementById('scene');
    if (scene.dataset.s !== s) { scene.className = 'scene s-' + s; scene.dataset.s = s; }
    const pill = r.getElementById('pill');
    pill.style.setProperty('--c', COLOR[s]);
    pill.firstChild.innerHTML = ICON[s];
    let label = this._t(s);
    if (s === 'error') { const e = this._st('error')?.state; if (e && e !== 'ninguno' && e !== 'none') label += ': ' + e.replace(/_/g, ' '); }
    pill.lastChild.textContent = label;
    const batEl = r.getElementById('bat');
    batEl.hidden = isNaN(bat);
    if (!isNaN(bat)) {
      batEl.lastChild.textContent = (charging ? '⚡ ' : '') + bat + '%';
      const fill = batEl.querySelector('b');
      fill.style.width = Math.max(4, bat * .17) + 'px';
      fill.style.setProperty('--bc', bat < 20 ? '#ff3b30' : bat < 40 ? '#ffc20e' : '#47d35a');
    }
    const nx = this._st('next_start');
    let nextTxt = this._t('none');
    if (nx && !['unknown', 'unavailable', ''].includes(nx.state)) {
      const d = new Date(nx.state), now = new Date(), tm = d.toLocaleTimeString(h.locale?.language, {hour: '2-digit', minute: '2-digit'});
      const dd = Math.round((new Date(d.toDateString()) - new Date(now.toDateString())) / 864e5);
      nextTxt = this._t('next') + ' · ' + (dd === 0 ? this._t('today') : dd === 1 ? this._t('tomorrow') : d.toLocaleDateString(h.locale?.language, {weekday: 'short', day: 'numeric'})) + ' ' + tm;
    }
    r.getElementById('next').textContent = nextTxt;
    const al = offline ? `<div class="alert warn">${this._t('offlineMsg')}</div>`
      : (upside || lifted || error) ? `<div class="alert">${label}</div>` : '';
    const alEl = r.getElementById('alert'); if (alEl.innerHTML !== al) alEl.innerHTML = al;
    r.querySelectorAll('.acts button').forEach(b => {
      b.lastChild.textContent = this._t(b.dataset.a);
      b.disabled = offline;
    });
    const chipText = {mow_1h: 'mow1', mow_3h: 'mow3', park_next: 'parkNext', resume_schedule: 'resume'};
    r.querySelectorAll('.chips button').forEach(b => {
      b.textContent = this._t(chipText[b.dataset.b]);
      b.hidden = !this._ids[b.dataset.b];
      b.disabled = offline;
    });
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
        return s.name === 'entity' ? t.pick : s.name === 'image' ? t.image : t.name;
      };
      this._form.schema = [
        {name: 'entity', required: true, selector: {entity: {domain: 'lawn_mower'}}},
        {name: 'name', selector: {text: {}}},
        {name: 'image', selector: {text: {}}},
      ];
      this._form.addEventListener('value-changed', e => {
        this.dispatchEvent(new CustomEvent('config-changed', {detail: {config: e.detail.value}, bubbles: true, composed: true}));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = this._config;
  }
}

if (!customElements.get('mcculloch-rob-card')) {
  customElements.define('mcculloch-rob-card', McCullochRobCard);
  customElements.define('mcculloch-rob-card-editor', McCullochRobCardEditor);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: 'mcculloch-rob-card', name: 'McCulloch / Husqvarna robot',
    description: 'Estado, batería, próximo corte y órdenes del robot cortacésped', preview: true,
    documentationURL: 'https://github.com/odegaard12/ha-mcculloch-husqvarna-ble',
  });
}
