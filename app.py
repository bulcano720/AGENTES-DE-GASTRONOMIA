import hmac
import html
import io
import json
import math
import os
import sqlite3
import threading
import time
import unicodedata
import uuid
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st
import streamlit.components.v1 as components
from groq import Groq

# ==============================================================================
# CONFIGURACIÓN DE PÁGINA Y ESTILO
# ==============================================================================
NOMBRE_REST = "Sabor Digital"

st.set_page_config(
    page_title=f"{NOMBRE_REST} · Restaurante Multiagente",
    page_icon="🍽️",
    layout="wide"
)

st.markdown("""
<style>
    :root {
        --crema: #FFF8EE;
        --cafe: #3E2C23;
        --terracota: #B34A25;
        --oliva: #5E7B3A;
        --mostaza: #F2B84B;
        --borde: #E3CDB0;
    }
    h1, h2, h3, h4, .header-title {
        font-family: Georgia, 'Times New Roman', serif !important;
        color: var(--terracota) !important;
    }
    .header-box {
        background: linear-gradient(135deg, #FCE9D0 0%, #F7D9B5 100%);
        border: 1px solid #E3B98A;
        box-shadow: 0 4px 14px rgba(179, 74, 37, 0.12);
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 25px;
    }
    .header-title {
        font-weight: bold;
        font-size: 24px;
        letter-spacing: 1px;
        margin-bottom: 10px;
    }
    .header-info { color: var(--cafe); font-size: 14px; margin-bottom: 4px; }
    div.stButton > button, div.stFormSubmitButton > button {
        background: var(--terracota) !important;
        color: #FFFFFF !important;
        font-weight: 600 !important;
        border: 1px solid var(--terracota) !important;
        border-radius: 8px !important;
        box-shadow: 0 2px 6px rgba(179, 74, 37, 0.25) !important;
    }
    div.stButton > button:hover, div.stFormSubmitButton > button:hover {
        background: #963C1B !important;
        border-color: #963C1B !important;
        color: #FFFFFF !important;
    }
    div.stButton > button:disabled, div.stFormSubmitButton > button:disabled {
        background: #E8DCCB !important;
        color: #8A7766 !important;
        border-color: #E8DCCB !important;
        box-shadow: none !important;
    }
    .stTextInput input, .stTextArea textarea {
        background-color: #FFFFFF !important;
        color: var(--cafe) !important;
        border: 1px solid var(--borde) !important;
        border-radius: 8px !important;
    }
    .pedido-card {
        background: #FFFFFF;
        border: 1px solid var(--borde);
        border-left: 5px solid var(--terracota);
        padding: 12px 16px;
        margin: 8px 0;
        border-radius: 8px;
        color: var(--cafe);
        font-size: 14px;
        box-shadow: 0 2px 8px rgba(62, 44, 35, 0.06);
    }
    .pedido-alerta { background: #FDECEA; border-left-color: #B3261E; color: #7A1C16; }
    .estado-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 12px;
        margin-left: 8px;
    }
    .estado-recibido { background: #7A6655; color: #FFFFFF; }
    .estado-en_preparacion { background: var(--mostaza); color: var(--cafe); }
    .estado-listo { background: var(--oliva); color: #FFFFFF; }
    .estado-en_camino { background: #3F6C8C; color: #FFFFFF; }
    .estado-entregado { background: #6B6259; color: #FFFFFF; }
    .plato-card {
        background: #FFFFFF;
        border: 1px solid var(--borde);
        border-radius: 10px;
        padding: 12px 16px;
        margin: 8px 0;
        color: var(--cafe);
        box-shadow: 0 2px 8px rgba(62, 44, 35, 0.06);
    }
    .plato-fila { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; }
    .plato-nombre { font-weight: 600; font-size: 16px; }
    .plato-precio { font-weight: 700; color: var(--terracota); white-space: nowrap; }
    .plato-meta { font-size: 13px; opacity: 0.8; margin-top: 4px; }
    .plato-agotado { opacity: 0.55; }
    .plato-agotado .plato-nombre { text-decoration: line-through; }
</style>
""", unsafe_allow_html=True)

esc = html.escape
TZ = ZoneInfo("America/Bogota")
MODELO = "openai/gpt-oss-120b"

INTEGRANTES = "Daniel Andres Jara Olivera | Daniel Felipe Escobar Ramirez | Diana Carolina León Ocampo | Michel Harold Silva Romero"
DOCENTE = "Ricardo Alberto Jimenez"

MAX_PEDIDOS_ACTIVOS = 3
VENTANA_DUPLICADO_S = 60
MAX_MENSAJES_CONTEXTO = 12
MAX_INTENTOS_LOGIN = 5


# ==============================================================================
# 🔐 SECRETOS Y CREDENCIALES
# ==============================================================================
def _secret(nombre):
    try:
        return str(st.secrets[nombre])
    except Exception:
        return os.getenv(nombre, "")


COCINA_USER = _secret("COCINA_USER") or "cocina"
COCINA_PASS = _secret("COCINA_PASS") or "cocina123"

APP_URL = (_secret("APP_URL") or "https://agentes-de-gastronomia-gxnkbxhu49jfw359zy4j6t.streamlit.app").rstrip("/")
MENU_URL = f"{APP_URL}/?menu=1"


@st.cache_resource
def get_client():
    key = _secret("GROQ_API_KEY")
    return Groq(api_key=key) if key else None


def credenciales_ok(usuario, contrasena):
    if not COCINA_PASS:
        return False
    return (hmac.compare_digest(usuario.encode(), COCINA_USER.encode())
            & hmac.compare_digest(contrasena.encode(), COCINA_PASS.encode()))


for k, v in (("cocina_autenticado", False), ("mis_pedidos", []), ("carrito", []),
             ("intentos_login", 0), ("sofia_pendiente", False),
             ("confirmar_del", None), ("reporte_ia", None),
             ("vista_cliente", "🍽️ Ver menú y pedir")):
    st.session_state.setdefault(k, v)


# ==============================================================================
# 📋 MENÚ DEL RESTAURANTE
# ==============================================================================
MENU = {
    "🥗 Entradas": {
        "Ensalada César": {"precio": 12000, "alergenos": ["lácteos", "gluten"], "tiempo": 8},
        "Sopa de Tomate": {"precio": 9000, "alergenos": [], "tiempo": 6},
        "Nachos con Queso": {"precio": 14000, "alergenos": ["lácteos"], "tiempo": 7},
        "Alitas BBQ": {"precio": 18000, "alergenos": [], "tiempo": 12},
    },
    "🍝 Fuertes": {
        "Pasta Alfredo": {"precio": 28000, "alergenos": ["gluten", "lácteos"], "tiempo": 15},
        "Pizza Margarita": {"precio": 32000, "alergenos": ["gluten", "lácteos"], "tiempo": 18},
        "Pizza Pepperoni": {"precio": 36000, "alergenos": ["gluten", "lácteos"], "tiempo": 18},
        "Hamburguesa Clásica": {"precio": 26000, "alergenos": ["gluten"], "tiempo": 14},
        "Pollo a la Plancha": {"precio": 24000, "alergenos": [], "tiempo": 16},
        "Salmón Grill": {"precio": 38000, "alergenos": ["pescado"], "tiempo": 20},
        "Tacos de Carne": {"precio": 22000, "alergenos": ["gluten"], "tiempo": 12},
    },
    "🍰 Postres": {
        "Cheesecake": {"precio": 12000, "alergenos": ["lácteos", "gluten"], "tiempo": 3},
        "Brownie con Helado": {"precio": 14000, "alergenos": ["lácteos", "gluten", "huevo"], "tiempo": 5},
        "Fruta Fresca": {"precio": 8000, "alergenos": [], "tiempo": 2},
    },
    "🥤 Bebidas": {
        "Limonada Natural": {"precio": 6000, "alergenos": [], "tiempo": 2},
        "Gaseosa": {"precio": 5000, "alergenos": [], "tiempo": 1},
        "Cerveza Artesanal": {"precio": 12000, "alergenos": ["gluten"], "tiempo": 2},
        "Café Espresso": {"precio": 4500, "alergenos": [], "tiempo": 3},
    },
}


def norm(s):
    s = unicodedata.normalize("NFD", str(s).strip().lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def cop(n):
    return "$" + f"{int(n):,}".replace(",", ".")


PLATOS = {norm(p): (cat, p) for cat, ps in MENU.items() for p in ps}
ALERGENOS = {norm(a): a for ps in MENU.values() for info in ps.values() for a in info["alergenos"]}
ALIAS = {"lactosa": "lacteos", "leche": "lacteos", "queso": "lacteos", "trigo": "gluten",
         "harina": "gluten", "huevos": "huevo", "pescados": "pescado", "salmon": "pescado"}


def precio_plato(categoria, plato):
    return MENU[categoria][plato]["precio"]


# ==============================================================================
# 🛡️ AGENTE DE ALERGIAS
# ==============================================================================
def revisar_alergias(items, alergias):
    avisos = []
    for a in alergias:
        clave = ALIAS.get(norm(a), norm(a))
        if clave not in ALERGENOS:
            avisos.append(f"ℹ️ '{a}' no está en nuestro catálogo de alérgenos: confirma con cocina.")
            continue
        for it in items:
            if ALERGENOS[clave] in MENU[it["categoria"]][it["plato"]]["alergenos"]:
                avisos.append(f"⚠️ {it['plato']} contiene {ALERGENOS[clave]} (alergia declarada: {a}).")
    return avisos


# ==============================================================================
# 🗂️ PERSISTENCIA (SQLite)
# ==============================================================================
DB_PATH = _secret("DB_PATH") or "pedidos.db"


def _abrir_db(ruta):
    conn = sqlite3.connect(ruta, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE IF NOT EXISTS pedidos ("
                 "seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE, data TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS agotados (plato TEXT PRIMARY KEY)")
    conn.commit()
    return conn


@st.cache_resource
def get_db():
    try:
        conn = _abrir_db(DB_PATH)
    except sqlite3.Error:
        conn = _abrir_db(":memory:")
    return {"conn": conn, "lock": threading.Lock()}


DB = get_db()


def normalizar_items(items):
    agotados = get_agotados()
    acumulado = {}
    for it in items or []:
        hit = PLATOS.get(norm(it.get("plato", "")))
        if not hit:
            raise ValueError(f"El plato '{it.get('plato')}' no existe en el menú.")
        if hit[1] in agotados:
            raise ValueError(f"'{hit[1]}' está agotado por hoy.")
        try:
            cant = int(it.get("cantidad", 1))
        except (TypeError, ValueError):
            raise ValueError("Cantidad inválida.")
        acumulado[hit] = acumulado.get(hit, 0) + cant
    out = []
    for (cat, plato), cant in acumulado.items():
        if not 1 <= cant <= 10:
            raise ValueError(f"La cantidad de '{plato}' debe estar entre 1 y 10.")
        out.append({"categoria": cat, "plato": plato, "cantidad": cant})
    if not out:
        raise ValueError("El pedido está vacío.")
    return out


def normalizar_telefono(t):
    d = "".join(c for c in str(t or "") if c.isdigit())
    if len(d) == 12 and d.startswith("57"):
        d = d[2:]
    return d if len(d) == 10 else None


def estimar_tiempo_cocina(items):
    tiempos = [MENU[i["categoria"]][i["plato"]]["tiempo"] * (1 + 0.3 * (i["cantidad"] - 1)) for i in items]
    mayor = max(tiempos)
    return math.ceil(mayor + 0.3 * (sum(tiempos) - mayor))


def total_items(items):
    return sum(precio_plato(i["categoria"], i["plato"]) * i["cantidad"] for i in items)


def crear_pedido(tipo_entrega, mesa=None, direccion=None, telefono=None,
                 cliente="Cliente", items=None, alergias=None):
    items = normalizar_items(items)
    alergias = [str(a).strip() for a in (alergias or []) if str(a).strip()][:10]
    mesa = str(mesa or "").strip()[:10]
    direccion = str(direccion or "").strip()[:120]
    cliente = (str(cliente or "").strip() or "Cliente")[:40]

    if tipo_entrega == "mesa":
        if not mesa:
            raise ValueError("Falta el número de mesa.")
        direccion, telefono = None, None
    elif tipo_entrega == "domicilio":
        tel = normalizar_telefono(telefono)
        if not direccion or not tel:
            raise ValueError("Para domicilio se necesita dirección y un celular válido de 10 dígitos.")
        telefono, mesa = tel, None
    else:
        raise ValueError("Tipo de entrega inválido (mesa o domicilio).")

    ahora = time.time()
    firma = json.dumps([tipo_entrega, (mesa or direccion).lower(),
                        sorted((i["plato"], i["cantidad"]) for i in items)], ensure_ascii=False)
    previos = pedidos_de_sesion()
    if sum(1 for p in previos if p["estado"] != "entregado") >= MAX_PEDIDOS_ACTIVOS:
        raise ValueError(f"Ya tienes {MAX_PEDIDOS_ACTIVOS} pedidos en curso. "
                         "Espera a que se entregue alguno antes de pedir más.")
    if any(p.get("firma") == firma and ahora - p.get("ts", 0) < VENTANA_DUPLICADO_S for p in previos):
        raise ValueError("Ya registraste un pedido idéntico hace un momento. "
                         "Si quieres repetirlo, espera un minuto.")

    data = {
        "tipo": tipo_entrega, "mesa": mesa or None, "direccion": direccion or None,
        "telefono": telefono, "cliente": cliente, "items": items, "alergias": alergias,
        "avisos": revisar_alergias(items, alergias), "estado": "recibido",
        "tiempo_cocina": estimar_tiempo_cocina(items),
        "tiempo_entrega": 20 if tipo_entrega == "domicilio" else 0,
        "total": total_items(items), "firma": firma, "ts": ahora,
        "fecha": datetime.now(TZ).strftime("%Y-%m-%d"),
        "hora": datetime.now(TZ).strftime("%H:%M:%S"),
    }
    with DB["lock"]:
        cur = DB["conn"].execute("INSERT INTO pedidos (id, data) VALUES (?, ?)", (f"tmp-{uuid.uuid4()}", "{}"))
        pid = f"PED-{cur.lastrowid:04d}"
        data["id"] = pid
        DB["conn"].execute("UPDATE pedidos SET id=?, data=? WHERE seq=?",
                           (pid, json.dumps(data, ensure_ascii=False), cur.lastrowid))
        DB["conn"].commit()
    st.session_state["mis_pedidos"].append(pid)
    return pid


def get_pedido(pid):
    with DB["lock"]:
        row = DB["conn"].execute("SELECT data FROM pedidos WHERE id=?", (pid,)).fetchone()
    return json.loads(row[0]) if row else None


def pedidos_de_sesion():
    return [p for p in map(get_pedido, st.session_state["mis_pedidos"]) if p]


def todos_los_pedidos():
    with DB["lock"]:
        rows = DB["conn"].execute("SELECT data FROM pedidos ORDER BY seq").fetchall()
    return [json.loads(r[0]) for r in rows]


def cambiar_estado(pid, nuevo_estado):
    with DB["lock"]:
        row = DB["conn"].execute("SELECT data FROM pedidos WHERE id=?", (pid,)).fetchone()
        if row:
            data = json.loads(row[0])
            data["estado"] = nuevo_estado
            DB["conn"].execute("UPDATE pedidos SET data=? WHERE id=?",
                               (json.dumps(data, ensure_ascii=False), pid))
            DB["conn"].commit()


def eliminar_pedido(pid):
    with DB["lock"]:
        DB["conn"].execute("DELETE FROM pedidos WHERE id=?", (pid,))
        DB["conn"].commit()


# ------------------------- 📦 AGENTE DE INVENTARIO -------------------------
def get_agotados():
    with DB["lock"]:
        rows = DB["conn"].execute("SELECT plato FROM agotados").fetchall()
    return {r[0] for r in rows if r[0] in {p for _, p in PLATOS.values()}}


def guardar_agotados(platos):
    with DB["lock"]:
        DB["conn"].execute("DELETE FROM agotados")
        DB["conn"].executemany("INSERT INTO agotados (plato) VALUES (?)", [(p,) for p in platos])
        DB["conn"].commit()


def badge_estado(estado):
    return f'<span class="estado-badge estado-{estado}">{esc(estado.upper().replace("_", " "))}</span>'


def items_txt(p):
    return ", ".join(f"{i['cantidad']}x {i['plato']}" for i in p["items"]) or "—"


# ==============================================================================
# 🎮 JUEGOS PARA LA ESPERA
# ==============================================================================
def juego_flappy():
    components.html("""
    <!DOCTYPE html><html><head><style>
        body { margin: 0; background: #FFF8EE; font-family: Georgia, serif; }
        canvas { display: block; margin: 0 auto; background: #FFE4B5;
                 border: 2px solid #B34A25; border-radius: 8px;
                 touch-action: manipulation; }
        #info { text-align: center; color: #3E2C23; font-size: 16px; margin-top: 8px; }
        #info b { color: #B34A25; }
    </style></head><body>
    <canvas id="game" width="400" height="500"></canvas>
    <div id="info">Puntos: <b id="score">0</b> · Récord: <b id="best">0</b> · <span id="msg">Toca o presiona ESPACIO para saltar</span></div>
    <script>
        const c = document.getElementById('game');
        const ctx = c.getContext('2d');
        const scoreEl = document.getElementById('score');
        const bestEl = document.getElementById('best');
        const msgEl = document.getElementById('msg');

        const GRAVEDAD = 0.45;
        const IMPULSO = -7.2;
        const SALTO_COOLDOWN_MS = 90;  // evita saltos duplicados en el mismo frame

        let bird, pipes, score, best, gameOver, frame, started;
        let ultimoSalto = 0;

        function reset() {
            bird = { x: 80, y: 250, v: 0, r: 15 };
            pipes = []; score = 0; gameOver = false; frame = 0; started = false;
            ultimoSalto = 0;
            scoreEl.textContent = 0;
            msgEl.textContent = 'Toca o presiona ESPACIO para saltar';
        }
        best = parseInt(localStorage.getItem('flappy_best') || '0');
        bestEl.textContent = best;
        reset();

        function jump() {
            const ahora = performance.now();
            if (gameOver) { reset(); return; }
            // Cooldown: ignora saltos demasiado seguidos
            if (ahora - ultimoSalto < SALTO_COOLDOWN_MS) return;
            ultimoSalto = ahora;
            if (!started) started = true;
            bird.v = IMPULSO;   // aplica SIEMPRE el impulso completo
        }

        document.addEventListener('keydown', e => {
            if (e.code === 'Space' || e.code === 'ArrowUp') {
                e.preventDefault();
                if (!e.repeat) jump();   // ignora auto-repeat del teclado
            }
        });
        document.addEventListener('keyup', e => {
            // opcional: nada, ya ignoramos el auto-repeat
        });

        // Click y touch con preventDefault para evitar scroll en móvil
        c.addEventListener('mousedown', e => { e.preventDefault(); jump(); });
        c.addEventListener('touchstart', e => { e.preventDefault(); jump(); }, { passive: false });

        function loop() {
            ctx.clearRect(0, 0, c.width, c.height);
            ctx.fillStyle = '#FFE4B5'; ctx.fillRect(0, 0, c.width, c.height);
            ctx.fillStyle = '#E3CDB0'; ctx.fillRect(0, c.height - 40, c.width, 40);

            if (started && !gameOver) {
                bird.v += GRAVEDAD;
                bird.y += bird.v;

                if (frame % 90 === 0) {
                    const gap = 140;
                    const topH = 60 + Math.random() * (c.height - 40 - gap - 120);
                    pipes.push({ x: c.width, topH: topH, gap: gap, w: 60 });
                }
                pipes.forEach(p => p.x -= 2.5);
                pipes = pipes.filter(p => p.x + p.w > 0);

                for (const p of pipes) {
                    if (bird.x + bird.r > p.x && bird.x - bird.r < p.x + p.w) {
                        if (bird.y - bird.r < p.topH || bird.y + bird.r > p.topH + p.gap) {
                            gameOver = true;
                            if (score > best) { best = score; bestEl.textContent = best; localStorage.setItem('flappy_best', best); }
                            msgEl.textContent = '💥 ¡Chocaste! Toca para reiniciar';
                        }
                    }
                }
                if (bird.y + bird.r > c.height - 40 || bird.y - bird.r < 0) {
                    gameOver = true;
                    if (score > best) { best = score; bestEl.textContent = best; localStorage.setItem('flappy_best', best); }
                    msgEl.textContent = '💥 ¡Chocaste! Toca para reiniciar';
                }
                for (const p of pipes) {
                    if (!p.passed && p.x + p.w < bird.x) { p.passed = true; score++; scoreEl.textContent = score; }
                }
                frame++;
            }

            pipes.forEach(p => {
                ctx.fillStyle = '#5E7B3A';
                ctx.fillRect(p.x, 0, p.w, p.topH);
                ctx.fillRect(p.x, p.topH + p.gap, p.w, c.height - p.topH - p.gap);
                ctx.strokeStyle = '#3E2C23'; ctx.lineWidth = 2;
                ctx.strokeRect(p.x, 0, p.w, p.topH);
                ctx.strokeRect(p.x, p.topH + p.gap, p.w, c.height - p.topH - p.gap);
            });

            ctx.beginPath(); ctx.arc(bird.x, bird.y, bird.r, 0, Math.PI * 2);
            ctx.fillStyle = '#F2B84B'; ctx.fill();
            ctx.strokeStyle = '#B34A25'; ctx.lineWidth = 2; ctx.stroke();
            ctx.beginPath(); ctx.arc(bird.x + 5, bird.y - 4, 3, 0, Math.PI * 2);
            ctx.fillStyle = '#3E2C23'; ctx.fill();

            requestAnimationFrame(loop);
        }
        loop();
    </script></body></html>
    """, height=580)

def juego_tetris():
    components.html("""
    <!DOCTYPE html><html><head><style>
        body { margin: 0; background: #FFF8EE; font-family: Georgia, serif; }
        #wrap { display: flex; justify-content: center; gap: 20px; padding: 10px; flex-wrap: wrap; }
        canvas { background: #FFE4B5; border: 2px solid #B34A25; border-radius: 8px; touch-action: none; }
        #info { color: #3E2C23; font-size: 15px; }
        #info b { color: #B34A25; }
        .key { display: inline-block; padding: 2px 8px; background: #F6E7D2;
               border: 1px solid #E3CDB0; border-radius: 4px; font-family: monospace; }
        #controles { display: flex; justify-content: center; gap: 10px;
                     margin-top: 14px; flex-wrap: wrap; }
        .btn-touch {
            background: #B34A25; color: #FFFFFF; border: none;
            border-radius: 10px; padding: 16px 22px; font-size: 22px;
            font-weight: bold; cursor: pointer; user-select: none;
            min-width: 64px; min-height: 64px;
            box-shadow: 0 3px 0 #7A2E14;
            transition: transform 0.05s;
            touch-action: manipulation;
        }
        .btn-touch:active { transform: translateY(3px); box-shadow: 0 0 0 #7A2E14; }
        #hint { text-align: center; color: #3E2C23; font-size: 13px; margin-top: 8px; opacity: 0.75; }
    </style></head><body>
    <div id="wrap">
        <canvas id="board" width="240" height="480"></canvas>
        <div id="info">
            <p><b>Puntos:</b> <span id="score">0</span></p>
            <p><b>Líneas:</b> <span id="lines">0</span></p>
            <p><b>Récord:</b> <span id="best">0</span></p>
            <hr>
            <p><span class="key">←</span> <span class="key">→</span> mover</p>
            <p><span class="key">↓</span> bajar</p>
            <p><span class="key">↑</span> rotar</p>
            <p><span class="key">Espacio</span> caída rápida</p>
        </div>
    </div>

    <!-- Controles táctiles para móvil -->
    <div id="controles">
        <button class="btn-touch" id="btn-left">◀</button>
        <button class="btn-touch" id="btn-rotate">⟳</button>
        <button class="btn-touch" id="btn-right">▶</button>
        <button class="btn-touch" id="btn-down">▼</button>
        <button class="btn-touch" id="btn-drop" style="padding: 16px 18px; font-size: 15px;">DROP</button>
    </div>
    <div id="hint">Puedes usar las flechas del teclado o tocar los botones</div>

    <script>
        const canvas = document.getElementById('board');
        const ctx = canvas.getContext('2d');
        const COLS = 10, ROWS = 20, SIZE = 24;
        const scoreEl = document.getElementById('score');
        const linesEl = document.getElementById('lines');
        const bestEl = document.getElementById('best');
        const PIECES = {
            I: { color: '#5E7B3A', shape: [[1,1,1,1]] },
            O: { color: '#F2B84B', shape: [[1,1],[1,1]] },
            T: { color: '#B34A25', shape: [[0,1,0],[1,1,1]] },
            S: { color: '#3F6C8C', shape: [[0,1,1],[1,1,0]] },
            Z: { color: '#963C1B', shape: [[1,1,0],[0,1,1]] },
            J: { color: '#7A6655', shape: [[1,0,0],[1,1,1]] },
            L: { color: '#6B6259', shape: [[0,0,1],[1,1,1]] },
        };
        let board, piece, pos, score, lines, best, dropCounter, dropInterval, gameOver;
        let currentColor = '#B34A25';
        best = parseInt(localStorage.getItem('tetris_best') || '0');
        bestEl.textContent = best;

        function reset() {
            board = Array.from({length: ROWS}, () => Array(COLS).fill(null));
            score = 0; lines = 0; gameOver = false;
            dropCounter = 0; dropInterval = 700;
            scoreEl.textContent = 0; linesEl.textContent = 0;
            nuevaPiezaConColor();
        }
        function nuevaPiezaConColor() {
            const keys = Object.keys(PIECES);
            const k = keys[Math.floor(Math.random() * keys.length)];
            currentColor = PIECES[k].color;
            piece = PIECES[k].shape.map(r => [...r]);
            pos = { x: Math.floor((COLS - piece[0].length) / 2), y: 0 };
            if (colision()) {
                gameOver = true;
                if (score > best) { best = score; bestEl.textContent = best; localStorage.setItem('tetris_best', best); }
            }
        }
        function colision() {
            for (let y = 0; y < piece.length; y++)
                for (let x = 0; x < piece[y].length; x++)
                    if (piece[y][x]) {
                        const nx = pos.x + x, ny = pos.y + y;
                        if (nx < 0 || nx >= COLS || ny >= ROWS) return true;
                        if (ny >= 0 && board[ny][nx]) return true;
                    }
            return false;
        }
        function merge() {
            piece.forEach((row, y) => row.forEach((v, x) => {
                if (v && pos.y + y >= 0) board[pos.y + y][pos.x + x] = currentColor;
            }));
        }
        function limpiarLineas() {
            let cleared = 0;
            for (let y = ROWS - 1; y >= 0; y--) {
                if (board[y].every(c => c)) {
                    board.splice(y, 1);
                    board.unshift(Array(COLS).fill(null));
                    cleared++; y++;
                }
            }
            if (cleared) {
                lines += cleared;
                score += [0, 40, 100, 300, 1200][cleared];
                scoreEl.textContent = score; linesEl.textContent = lines;
                dropInterval = Math.max(120, 700 - lines * 15);
            }
        }
        function rotate() {
            if (gameOver) return;
            const N = piece.length, M = piece[0].length;
            const rot = Array.from({length: M}, () => Array(N).fill(0));
            for (let y = 0; y < N; y++)
                for (let x = 0; x < M; x++)
                    rot[x][N - 1 - y] = piece[y][x];
            const backup = piece; piece = rot;
            if (colision()) piece = backup;
        }
        function mover(dir) {
            if (gameOver) return;
            pos.x += dir;
            if (colision()) pos.x -= dir;
        }
        function drop() {
            if (gameOver) return;
            pos.y++;
            if (colision()) {
                pos.y--; merge(); limpiarLineas(); nuevaPiezaConColor();
            }
            dropCounter = 0;
        }
        function hardDrop() { if (gameOver) return; while (!colision()) pos.y++; pos.y--; drop(); }

        document.addEventListener('keydown', e => {
            if (gameOver && e.code === 'Space') { reset(); return; }
            if (e.code === 'ArrowLeft') { e.preventDefault(); mover(-1); }
            else if (e.code === 'ArrowRight') { e.preventDefault(); mover(1); }
            else if (e.code === 'ArrowDown') { e.preventDefault(); drop(); }
            else if (e.code === 'ArrowUp') { e.preventDefault(); rotate(); }
            else if (e.code === 'Space') { e.preventDefault(); hardDrop(); }
        });

        // --- BOTONES TÁCTILES ---
        function bindHold(btnId, action, repeatDelay = 180) {
            const btn = document.getElementById(btnId);
            let timer = null;
            const start = (e) => {
                e.preventDefault();
                if (gameOver && btnId === 'btn-drop') { reset(); return; }
                action();
                timer = setInterval(action, repeatDelay);
            };
            const stop = (e) => {
                if (e) e.preventDefault();
                if (timer) { clearInterval(timer); timer = null; }
            };
            btn.addEventListener('mousedown', start);
            btn.addEventListener('touchstart', start, { passive: false });
            btn.addEventListener('mouseup', stop);
            btn.addEventListener('mouseleave', stop);
            btn.addEventListener('touchend', stop);
            btn.addEventListener('touchcancel', stop);
            // Doble clic evita zoom accidental en móviles
            btn.addEventListener('dblclick', e => e.preventDefault());
        }

        // Mantener presionado mueve repetidamente
        bindHold('btn-left', () => mover(-1));
        bindHold('btn-right', () => mover(1));
        bindHold('btn-down', () => drop(), 80);   // bajar más rápido al mantener

        // Estos son de un solo uso
        document.getElementById('btn-rotate').addEventListener('click', e => {
            e.preventDefault();
            if (gameOver) { reset(); return; }
            rotate();
        });
        document.getElementById('btn-drop').addEventListener('click', e => {
            e.preventDefault();
            if (gameOver) { reset(); return; }
            hardDrop();
        });

        let lastTime = 0;
        function update(time = 0) {
            const delta = time - lastTime; lastTime = time;
            if (!gameOver) { dropCounter += delta; if (dropCounter > dropInterval) drop(); }
            draw(); requestAnimationFrame(update);
        }
        function draw() {
            ctx.fillStyle = '#FFE4B5'; ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.strokeStyle = 'rgba(179,74,37,0.15)';
            for (let x = 0; x <= COLS; x++) { ctx.beginPath(); ctx.moveTo(x*SIZE,0); ctx.lineTo(x*SIZE,ROWS*SIZE); ctx.stroke(); }
            for (let y = 0; y <= ROWS; y++) { ctx.beginPath(); ctx.moveTo(0,y*SIZE); ctx.lineTo(COLS*SIZE,y*SIZE); ctx.stroke(); }
            board.forEach((row, y) => row.forEach((c, x) => {
                if (c) { ctx.fillStyle = c; ctx.fillRect(x*SIZE,y*SIZE,SIZE-1,SIZE-1); ctx.strokeStyle='#3E2C23'; ctx.strokeRect(x*SIZE,y*SIZE,SIZE-1,SIZE-1); }
            }));
            piece.forEach((row, y) => row.forEach((v, x) => {
                if (v && pos.y + y >= 0) {
                    ctx.fillStyle = currentColor;
                    ctx.fillRect((pos.x+x)*SIZE,(pos.y+y)*SIZE,SIZE-1,SIZE-1);
                    ctx.strokeStyle = '#3E2C23';
                    ctx.strokeRect((pos.x+x)*SIZE,(pos.y+y)*SIZE,SIZE-1,SIZE-1);
                }
            }));
            if (gameOver) {
                ctx.fillStyle = 'rgba(62,44,35,0.75)'; ctx.fillRect(0,200,canvas.width,80);
                ctx.fillStyle = '#FFF8EE'; ctx.font = 'bold 22px Georgia'; ctx.textAlign = 'center';
                ctx.fillText('GAME OVER', canvas.width/2, 235);
                ctx.font = '14px Georgia'; ctx.fillText('Toca DROP para reiniciar', canvas.width/2, 260);
            }
        }
        reset(); update();
    </script></body></html>
    """, height=720)


def juego_carreritas():
    components.html("""
    <!DOCTYPE html><html><head><style>
        body { margin: 0; background: #FFF8EE; font-family: Georgia, serif; }
        canvas { display: block; margin: 0 auto; background: #4A5568;
                 border: 2px solid #B34A25; border-radius: 8px; }
        #info { text-align: center; color: #3E2C23; margin-top: 8px; font-size: 15px; }
        #info b { color: #B34A25; }
    </style></head><body>
    <canvas id="game" width="360" height="520"></canvas>
    <div id="info">Puntos: <b id="score">0</b> · Récord: <b id="best">0</b> · <span id="msg">Usa ← → para moverte</span></div>
    <script>
        const c = document.getElementById('game');
        const ctx = c.getContext('2d');
        const scoreEl = document.getElementById('score');
        const bestEl = document.getElementById('best');
        const msgEl = document.getElementById('msg');
        const ROAD_LEFT = 40, ROAD_RIGHT = 320;
        const LANES = 3;
        const LANE_W = (ROAD_RIGHT - ROAD_LEFT) / LANES;
        let car, obstacles, score, best, gameOver, frame, speed, started;
        best = parseInt(localStorage.getItem('race_best') || '0');
        bestEl.textContent = best;
        function reset() {
            car = { x: (ROAD_LEFT + ROAD_RIGHT)/2 - 18, y: c.height - 90, w: 36, h: 60, lane: 1 };
            obstacles = []; score = 0; frame = 0; speed = 3; gameOver = false; started = false;
            scoreEl.textContent = 0; msgEl.textContent = 'Usa ← → para moverte';
        }
        reset();
        function moveLane(dir) {
            if (gameOver) { reset(); return; }
            started = true;
            car.lane = Math.max(0, Math.min(LANES - 1, car.lane + dir));
            car.x = ROAD_LEFT + car.lane * LANE_W + LANE_W/2 - car.w/2;
        }
        document.addEventListener('keydown', e => {
            if (e.code === 'ArrowLeft') { e.preventDefault(); moveLane(-1); }
            if (e.code === 'ArrowRight') { e.preventDefault(); moveLane(1); }
        });
        c.addEventListener('click', e => {
            const rect = c.getBoundingClientRect();
            const clickX = e.clientX - rect.left;
            moveLane(clickX < car.x + car.w/2 ? -1 : 1);
        });
        function loop() {
            ctx.fillStyle = '#FFF8EE'; ctx.fillRect(0, 0, c.width, c.height);
            ctx.fillStyle = '#5E7B3A';
            ctx.fillRect(0, 0, ROAD_LEFT, c.height);
            ctx.fillRect(ROAD_RIGHT, 0, c.width - ROAD_RIGHT, c.height);
            ctx.fillStyle = '#4A5568';
            ctx.fillRect(ROAD_LEFT, 0, ROAD_RIGHT - ROAD_LEFT, c.height);
            ctx.strokeStyle = '#F2B84B'; ctx.lineWidth = 3;
            ctx.setLineDash([20, 20]);
            ctx.lineDashOffset = -(frame * speed) % 40;
            for (let i = 1; i < LANES; i++) {
                const x = ROAD_LEFT + i * LANE_W;
                ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, c.height); ctx.stroke();
            }
            ctx.setLineDash([]);
            ctx.strokeStyle = '#B34A25'; ctx.lineWidth = 4;
            ctx.beginPath();
            ctx.moveTo(ROAD_LEFT, 0); ctx.lineTo(ROAD_LEFT, c.height);
            ctx.moveTo(ROAD_RIGHT, 0); ctx.lineTo(ROAD_RIGHT, c.height);
            ctx.stroke();
            if (started && !gameOver) {
                if (frame % 45 === 0) {
                    const lane = Math.floor(Math.random() * LANES);
                    const x = ROAD_LEFT + lane * LANE_W + LANE_W/2 - 18;
                    const colors = ['#B34A25', '#3F6C8C', '#7A6655', '#963C1B'];
                    obstacles.push({ x: x, y: -70, w: 36, h: 60, color: colors[Math.floor(Math.random()*colors.length)] });
                }
                obstacles.forEach(o => o.y += speed);
                obstacles = obstacles.filter(o => o.y < c.height + 80);
                for (const o of obstacles) {
                    if (car.x < o.x + o.w && car.x + car.w > o.x &&
                        car.y < o.y + o.h && car.y + car.h > o.y) {
                        gameOver = true;
                        if (score > best) { best = score; bestEl.textContent = best; localStorage.setItem('race_best', best); }
                        msgEl.textContent = '💥 ¡Chocaste! Toca para reiniciar';
                        break;
                    }
                }
                if (frame % 15 === 0) {
                    score++; scoreEl.textContent = score;
                    speed = 3 + Math.min(4, Math.floor(score / 20));
                }
                frame++;
            }
            obstacles.forEach(o => {
                ctx.fillStyle = o.color; ctx.fillRect(o.x, o.y, o.w, o.h);
                ctx.strokeStyle = '#3E2C23'; ctx.lineWidth = 2; ctx.strokeRect(o.x, o.y, o.w, o.h);
                ctx.fillStyle = '#FFF8EE';
                ctx.fillRect(o.x + 6, o.y + 10, 8, 10);
                ctx.fillRect(o.x + 22, o.y + 10, 8, 10);
            });
            ctx.fillStyle = '#F2B84B'; ctx.fillRect(car.x, car.y, car.w, car.h);
            ctx.strokeStyle = '#B34A25'; ctx.lineWidth = 2; ctx.strokeRect(car.x, car.y, car.w, car.h);
            ctx.fillStyle = '#3E2C23';
            ctx.fillRect(car.x + 6, car.y + 10, car.w - 12, 12);
            ctx.fillRect(car.x + 6, car.y + car.h - 20, car.w - 12, 10);
            requestAnimationFrame(loop);
        }
        loop();
    </script></body></html>
    """, height=600)


# ==============================================================================
# 🤖 AGENTE SOFÍA
# ==============================================================================
PROMPT_CLIENTE = (
    f"Eres Sofía, la asistente IA del restaurante '{NOMBRE_REST}'. Eres cálida, "
    "cordial y eficiente. Ayudas al cliente a elegir platos del menú, preguntas por "
    "alergias, sugieres entradas/bebidas/postres y registras el pedido. "
    "Responde siempre en español, con calidez y de forma breve."
)

SALUDO_CLIENTE = (
    "¡Hola! 👋 Soy **Sofía**, tu asistente IA del restaurante 🍽️. "
    "Puedo mostrarte el menú, tomar tu pedido y avisarte cuando esté listo. "
    "¿Qué se te antoja hoy?"
)


def texto_menu_para_prompt():
    lineas = []
    for cat, platos in MENU.items():
        lineas.append(f"\n{cat}:")
        for nombre, info in platos.items():
            alerg = ", ".join(info["alergenos"]) if info["alergenos"] else "ninguno"
            lineas.append(f"  - {nombre} ({cop(info['precio'])} | {info['tiempo']} min | alérgenos: {alerg})")
    return "\n".join(lineas)


MENU_TEXTO = texto_menu_para_prompt()

TOOLS = [{
    "type": "function",
    "function": {
        "name": "crear_pedido",
        "description": "Registra el pedido en cocina. Úsala SOLO cuando el cliente haya confirmado "
                       "explícitamente platos, cantidades, datos de entrega y alergias. "
                       "Llámala UNA sola vez por pedido.",
        "parameters": {
            "type": "object",
            "properties": {
                "items": {"type": "array", "items": {"type": "object", "properties": {
                    "plato": {"type": "string", "description": "Nombre exacto del plato del menú"},
                    "cantidad": {"type": "integer", "minimum": 1, "maximum": 10}},
                    "required": ["plato", "cantidad"]}},
                "tipo_entrega": {"type": "string", "enum": ["mesa", "domicilio"]},
                "cliente": {"type": "string"},
                "mesa": {"type": "string", "description": "Número de mesa (si es mesa)"},
                "direccion": {"type": "string"},
                "telefono": {"type": "string", "description": "Celular de 10 dígitos (si es domicilio)"},
                "alergias": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["items", "tipo_entrega"],
        },
    },
}]


def tool_crear_pedido(args):
    try:
        pid = crear_pedido(
            tipo_entrega=args.get("tipo_entrega"), mesa=args.get("mesa"),
            direccion=args.get("direccion"), telefono=args.get("telefono"),
            cliente=args.get("cliente") or "Cliente", items=args.get("items"),
            alergias=args.get("alergias") or [],
        )
        p = get_pedido(pid)
        return {"ok": True, "pedido": pid, "total": cop(p["total"]),
                "tiempo_cocina_min": p["tiempo_cocina"], "tiempo_entrega_min": p["tiempo_entrega"],
                "avisos_alergias": p["avisos"]}
    except ValueError as e:
        return {"ok": False, "error": str(e)}


TOOL_FUNCS = {"crear_pedido": tool_crear_pedido}


def resumen_pedidos_texto():
    mios = pedidos_de_sesion()
    if not mios:
        return "Este cliente no tiene pedidos."
    return "\n".join(
        f"- {p['id']} | {p['estado']} | {p['mesa'] or p['direccion'] or '—'} | {items_txt(p)} | {cop(p['total'])}"
        for p in mios
    )


def _recortar_historial(historial):
    recientes = list(historial[-MAX_MENSAJES_CONTEXTO:])
    while recientes and recientes[0]["role"] != "user":
        recientes.pop(0)
    return recientes


def sofia_responder(historial):
    client = get_client()
    if client is None:
        raise RuntimeError("Falta GROQ_API_KEY")
    agotados = sorted(get_agotados())
    system_prompt = (
        f"{PROMPT_CLIENTE}\n\n📋 MENÚ:\n{MENU_TEXTO}\n\n"
        f"🚫 PLATOS AGOTADOS HOY: {', '.join(agotados) if agotados else 'ninguno'}\n\n"
        f"📦 PEDIDOS DE ESTE CLIENTE:\n{resumen_pedidos_texto()}\n\n"
        "INSTRUCCIONES:\n"
        "- Antes de llamar a crear_pedido confirma platos, cantidades, tipo de entrega "
        "(mesa, o domicilio con dirección y celular de 10 dígitos) y alergias.\n"
        "- Tras crear el pedido informa su número, el total, el tiempo estimado y los avisos de alergias.\n"
        "- Nunca ofrezcas ni registres platos que no estén en el menú o estén agotados.\n"
        "- ALERGIAS: nunca afirmes que un plato es 'seguro' o 'libre de' algo más allá de los "
        "alérgenos listados en el menú. Ante alergias graves o riesgo de contaminación cruzada, "
        "recomienda confirmar con cocina.\n"
        "- Si pregunta por el estado de su pedido, respóndelo según los pedidos listados.\n"
        "- Si no sabes algo, dilo; no inventes información del restaurante."
    )
    mensajes = [{"role": "system", "content": system_prompt}] + _recortar_historial(historial)
    for _ in range(4):
        r = client.chat.completions.create(
            messages=mensajes, model=MODELO, max_tokens=1500, temperature=0.3,
            tools=TOOLS, tool_choice="auto",
            extra_body={"reasoning_effort": "low"},
        )
        msg = r.choices[0].message
        if not msg.tool_calls:
            return (msg.content or "").strip() or \
                "Disculpa, no logré generar una respuesta. ¿Puedes repetir tu mensaje?"
        mensajes.append({
            "role": "assistant", "content": msg.content or "",
            "tool_calls": [{"id": tc.id, "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                           for tc in msg.tool_calls],
        })
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
                fn = TOOL_FUNCS.get(tc.function.name)
                res = fn(args) if fn else {"ok": False, "error": "Herramienta desconocida"}
            except (json.JSONDecodeError, AttributeError):
                res = {"ok": False, "error": "Argumentos inválidos"}
            mensajes.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(res, ensure_ascii=False)})
    return "Tuve un problema registrando tu pedido. ¿Podemos intentarlo de nuevo?"


# ------------------------- 📊 AGENTE DE REPORTES -------------------------
def resumen_ventas(pedidos):
    platos = Counter()
    for p in pedidos:
        for i in p["items"]:
            platos[i["plato"]] += i["cantidad"]
    total = sum(p["total"] for p in pedidos)
    return {
        "pedidos": len(pedidos),
        "ventas": total,
        "ticket_promedio": total / len(pedidos) if pedidos else 0,
        "domicilios": sum(1 for p in pedidos if p["tipo"] == "domicilio"),
        "con_alergias": sum(1 for p in pedidos if p["alergias"]),
        "top_platos": platos.most_common(5),
    }


def reporte_ia(resumen):
    client = get_client()
    if client is None:
        raise RuntimeError("Falta GROQ_API_KEY")
    datos = json.dumps({**resumen, "ventas": cop(resumen["ventas"]),
                        "ticket_promedio": cop(resumen["ticket_promedio"])}, ensure_ascii=False)
    r = client.chat.completions.create(
        model=MODELO, max_tokens=1500, temperature=0.3,
        extra_body={"reasoning_effort": "low"},
        messages=[
            {"role": "system", "content": f"Eres el analista del restaurante '{NOMBRE_REST}'. "
             "Con los datos del día escribe un resumen breve (máx. 6 líneas) en español, con una "
             "observación útil y una recomendación para mañana. No inventes cifras."},
            {"role": "user", "content": datos},
        ],
    )
    return (r.choices[0].message.content or "").strip()


# ==============================================================================
# 📱 CÓDIGO QR DEL MENÚ + MENÚ PÚBLICO
# ==============================================================================
@st.cache_data(show_spinner=False)
def generar_qr_png(url):
    try:
        import segno
    except ImportError:
        return None
    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="png", scale=10, border=2,
                                    dark="#3E2C23", light="#FFFFFF")
    return buf.getvalue()


def mostrar_qr(clave):
    png = generar_qr_png(MENU_URL)
    if png is None:
        st.warning("No se pudo generar el QR (falta la librería 'segno' en requirements.txt). "
                   "Puedes compartir el enlace de abajo.")
    else:
        st.image(png, width=240, caption="Escanéalo para ver el menú en tu celular")
        st.download_button("⬇️ Descargar QR (PNG)", png, file_name="qr_menu.png",
                           mime="image/png", key=f"dl_qr_{clave}")
    st.code(MENU_URL, language=None)
    st.link_button("👀 Abrir menú móvil", MENU_URL)


def menu_publico():
    st.markdown(f"""
    <div class="header-box">
        <div class="header-title">🍽️ {esc(NOMBRE_REST)} — Menú</div>
        <div class="header-info">Precios en pesos colombianos · Alérgenos indicados en cada plato</div>
    </div>
    """, unsafe_allow_html=True)
    agotados = get_agotados()
    for cat, platos in MENU.items():
        st.subheader(cat)
        for nombre, info in platos.items():
            alerg = ", ".join(info["alergenos"]) if info["alergenos"] else "sin alérgenos"
            agotado = nombre in agotados
            clase = "plato-card plato-agotado" if agotado else "plato-card"
            precio = "AGOTADO" if agotado else cop(info["precio"])
            st.markdown(
                f"<div class='{clase}'>"
                f"<div class='plato-fila'><span class='plato-nombre'>{esc(nombre)}</span>"
                f"<span class='plato-precio'>{esc(precio)}</span></div>"
                f"<div class='plato-meta'>⏱️ {info['tiempo']} min · ⚠️ {esc(alerg)}</div>"
                f"</div>",
                unsafe_allow_html=True
            )
    st.info("⚠️ Si tienes alguna alergia, avísanos al pedir y confirma siempre con tu mesero.")
    st.link_button("🛒 Hacer un pedido", APP_URL)


if str(st.query_params.get("menu", "")).lower() in ("1", "true", "si"):
    menu_publico()
    st.stop()


# ==============================================================================
# ENCABEZADO
# ==============================================================================
st.markdown(f"""
<div class="header-box">
    <div class="header-title">🍽️ SISTEMA MULTIAGENTE - RESTAURANTE "{esc(NOMBRE_REST.upper())}"</div>
    <div class="header-info"><b>👨‍🏫 DOCENTE:</b> {esc(DOCENTE)}</div>
    <div class="header-info"><b>👥 INTEGRANTES:</b> {esc(INTEGRANTES)}</div>
</div>
""", unsafe_allow_html=True)

vista = st.radio(
    "🧭 SELECCIONA LA VISTA:",
    ["👤 Vista Cliente (Usuario)", "👨‍🍳 Vista Cocina / Operación"],
    horizontal=True
)
st.divider()

# ----------------------- LOGIN OBLIGATORIO PARA COCINA -----------------------
if vista == "👨‍🍳 Vista Cocina / Operación" and not st.session_state["cocina_autenticado"]:
    st.warning("🔒 Acceso restringido. Ingresa tus credenciales de cocina.")
    if not COCINA_PASS:
        st.error("⚙️ El acceso a cocina no está configurado: falta el secreto COCINA_PASS.")
        st.stop()
    if st.session_state["intentos_login"] >= MAX_INTENTOS_LOGIN:
        st.error("⛔ Demasiados intentos fallidos en esta sesión. Recarga la página para intentar de nuevo.")
        st.stop()
    with st.form("login_cocina"):
        usuario = st.text_input("Usuario:")
        contrasena = st.text_input("Contraseña:", type="password")
        entrar = st.form_submit_button("🔓 Ingresar")
    if entrar:
        if credenciales_ok(usuario, contrasena):
            st.session_state["cocina_autenticado"] = True
            st.session_state["intentos_login"] = 0
            st.rerun()
        else:
            st.session_state["intentos_login"] += 1
            restantes = MAX_INTENTOS_LOGIN - st.session_state["intentos_login"]
            st.error(f"❌ Usuario o contraseña incorrectos. Intentos restantes: {restantes}.")
    st.stop()

if vista == "👨‍🍳 Vista Cocina / Operación":
    if st.button("🔒 Cerrar sesión de cocina"):
        st.session_state["cocina_autenticado"] = False
        st.rerun()


# ==============================================================================
# 👤 VISTA CLIENTE
# ==============================================================================
@st.fragment(run_every=10)
def panel_estado_cliente():
    mios = pedidos_de_sesion()
    if not mios:
        st.info("Aún no tienes pedidos registrados.")
        return
    st.markdown("### 📦 Estado de tus pedidos")
    for p in reversed(mios[-5:]):
        avisos = "".join(f"<br>{esc(a)}" for a in p["avisos"])
        st.markdown(
            f"<div class='pedido-card'><b>{esc(p['id'])}</b> {badge_estado(p['estado'])}<br>"
            f"Items: {esc(items_txt(p))}<br>"
            f"<b>Total: {esc(cop(p['total']))}</b><br>"
            f"Hora: {esc(p['hora'])} | Tiempo cocina: {p['tiempo_cocina']} min{avisos}</div>",
            unsafe_allow_html=True
        )


if vista == "👤 Vista Cliente (Usuario)":

    subvista = st.radio(
        "🧭 ¿Qué quieres hacer?",
        ["🍽️ Ver menú y pedir", "🎮 Jugar mientras espero"],
        horizontal=True,
        key="vista_cliente"
    )
    st.divider()

    if subvista == "🎮 Jugar mientras espero":
        st.subheader("🎮 Entretente mientras preparamos tu pedido")
        st.caption("Tus pedidos siguen avanzando en cocina mientras juegas. Los récords se guardan en tu navegador.")

        juego_sel = st.radio(
            "Elige un juego:",
            ["🐦 Pajarito Feliz", "🧱 Tetris Express", "🏎️ Carreritas"],
            horizontal=True,
            key="juego_sel"
        )

        if juego_sel == "🐦 Pajarito Feliz":
            st.markdown("**Instrucciones:** toca la pantalla o presiona **ESPACIO** para hacer saltar al pajarito y esquivar los tubos.")
            juego_flappy()
        elif juego_sel == "🧱 Tetris Express":
            st.markdown("**Instrucciones:** usa las flechas **← →** para mover, **↓** para bajar, **↑** para rotar y **ESPACIO** para caída rápida.")
            juego_tetris()
        else:
            st.markdown("**Instrucciones:** usa **← →** o toca a los lados del carro para cambiar de carril y esquivar los obstáculos.")
            juego_carreritas()

        st.stop()

    col_menu, col_chat = st.columns([1.2, 1])
    agotados = get_agotados()

    # ------------------------------ COLUMNA MENÚ ------------------------------
    with col_menu:
        st.subheader("📋 Nuestro Menú")
        for cat, platos in MENU.items():
            with st.expander(f"{cat} ({len(platos)} platos)", expanded=False):
                for nombre, info in platos.items():
                    alerg = ", ".join(info["alergenos"]) if info["alergenos"] else "sin alérgenos"
                    if nombre in agotados:
                        st.markdown(f"~~{nombre}~~ — 🚫 **AGOTADO por hoy**")
                    else:
                        st.markdown(
                            f"**{nombre}** — 💰 {cop(info['precio'])} — ⏱️ {info['tiempo']} min  \n"
                            f"⚠️ _{alerg}_"
                        )

        with st.expander("📱 Ver este menú en tu celular (código QR)"):
            mostrar_qr("cliente")

        st.divider()
        st.subheader("🛒 Hacer Pedido Rápido")

        tipo = st.selectbox("Tipo de entrega:", ["mesa", "domicilio"])
        categoria_sel = st.selectbox("Categoría:", list(MENU.keys()))
        opciones = [p for p in MENU[categoria_sel] if p not in agotados]
        carrito = st.session_state["carrito"]

        with st.form("form_pedido_cliente"):
            cliente_nombre = st.text_input("Tu nombre:", value="Cliente", max_chars=40)
            if tipo == "mesa":
                mesa_input = st.text_input("Número de mesa:", value="1", max_chars=10)
                dir_input = tel_input = None
            else:
                dir_input = st.text_input("Dirección:", placeholder="Cra 45 #12-34", max_chars=120)
                tel_input = st.text_input("Celular (10 dígitos):", placeholder="3001234567", max_chars=15)
                mesa_input = None
            plato_sel = st.selectbox("Plato:", opciones if opciones else ["(sin platos disponibles)"])
            cantidad_sel = st.number_input("Cantidad:", min_value=1, max_value=10, value=1)
            alergias_input = st.text_input("Alergias (separadas por coma):", value="")
            b1, b2 = st.columns(2)
            agregar = b1.form_submit_button("➕ Agregar al pedido")
            enviar = b2.form_submit_button("✅ Enviar pedido a cocina", disabled=not carrito)
            st.caption("Agrega uno o más platos y luego envía el pedido: se envía lo que aparece en «Tu pedido».")

        if agregar:
            if not opciones:
                st.error("❌ No quedan platos disponibles en esta categoría.")
            else:
                for it in carrito:
                    if it["plato"] == plato_sel:
                        it["cantidad"] = min(10, it["cantidad"] + int(cantidad_sel))
                        break
                else:
                    carrito.append({"categoria": categoria_sel, "plato": plato_sel,
                                    "cantidad": int(cantidad_sel)})
                st.rerun()

        if carrito:
            st.markdown("**🧺 Tu pedido:**")
            for it in carrito:
                sub = precio_plato(it["categoria"], it["plato"]) * it["cantidad"]
                st.markdown(f"- {it['cantidad']}× {it['plato']} — {cop(sub)}")
            st.markdown(f"**Total: {cop(total_items(carrito))}**")
            c1, c2, _ = st.columns([1, 1, 2])
            if c1.button("↩️ Quitar último"):
                carrito.pop()
                st.rerun()
            if c2.button("🧹 Vaciar pedido"):
                st.session_state["carrito"] = []
                st.rerun()

        if enviar:
            try:
                pid = crear_pedido(
                    tipo_entrega=tipo, mesa=mesa_input, direccion=dir_input, telefono=tel_input,
                    cliente=cliente_nombre, items=list(carrito),
                    alergias=alergias_input.split(","),
                )
                p = get_pedido(pid)
                st.session_state["carrito"] = []
                st.success(f"✅ Pedido **{pid}** enviado a cocina. Total: {cop(p['total'])}. "
                           f"Tiempo estimado: {p['tiempo_cocina']} min.")
                for a in p["avisos"]:
                    st.warning(a)
            except ValueError as e:
                st.error(f"❌ {e}")

    # ------------------------------ COLUMNA CHAT ------------------------------
    with col_chat:
        st.subheader("💬 Chat con Sofía")
        panel_estado_cliente()
        st.divider()

        chat_key = "chat_cliente"
        if chat_key not in st.session_state:
            st.session_state[chat_key] = [{"role": "assistant", "content": SALUDO_CLIENTE}]

        chat_container = st.container(height=400)
        with chat_container:
            for msg in st.session_state[chat_key]:
                st.chat_message(msg["role"]).write(msg["content"])

            if st.session_state["sofia_pendiente"]:
                with st.chat_message("assistant"):
                    with st.spinner("Sofía está pensando..."):
                        try:
                            respuesta = sofia_responder(st.session_state[chat_key])
                        except RuntimeError:
                            respuesta = None
                            st.session_state["sofia_pendiente"] = False
                            st.error("❌ Sofía no está configurada (falta GROQ_API_KEY).")
                        except Exception:
                            respuesta = None
                            st.session_state["sofia_pendiente"] = False
                            st.error("❌ No pude contactar a Sofía. Intenta de nuevo en unos segundos.")
                if respuesta is not None:
                    st.session_state[chat_key].append({"role": "assistant", "content": respuesta})
                    st.session_state["sofia_pendiente"] = False
                    st.rerun()

        if user_input := st.chat_input("Escribe tu mensaje a Sofía...", max_chars=500):
            st.session_state[chat_key].append({"role": "user", "content": user_input})
            st.session_state["sofia_pendiente"] = True
            st.rerun()

        if st.button("🗑️ Limpiar chat"):
            st.session_state[chat_key] = [{"role": "assistant", "content": SALUDO_CLIENTE}]
            st.session_state["sofia_pendiente"] = False
            st.rerun()


# ==============================================================================
# 👨‍🍳 VISTA COCINA / OPERACIÓN
# ==============================================================================
ORDEN_ESTADO = {"recibido": 0, "en_preparacion": 1, "listo": 2, "en_camino": 3, "entregado": 4}


def render_pedido(p):
    pid = p["id"]
    minutos = int((time.time() - p["ts"]) // 60)
    retrasado = p["estado"] in ("recibido", "en_preparacion") and minutos > p["tiempo_cocina"]

    st.markdown(
        f"#### 🧾 {esc(pid)} — {esc(p['cliente'])} ({esc(p['tipo'].upper())}) {badge_estado(p['estado'])}",
        unsafe_allow_html=True
    )
    ubicacion = p["mesa"] or p["direccion"] or "—"
    telefono = f"<b>Teléfono:</b> {esc(p['telefono'])}<br>" if p["telefono"] else ""
    avisos = "".join(f"<br>{esc(a)}" for a in p["avisos"])
    retraso = f"<br>⏰ <b>Retrasado:</b> lleva {minutos} min (estimado {p['tiempo_cocina']} min)" if retrasado else ""
    clase = "pedido-card pedido-alerta" if (p["avisos"] or retrasado) else "pedido-card"
    st.markdown(
        f"""<div class="{clase}">
        <b>Ubicación:</b> {esc(str(ubicacion))}<br>{telefono}
        <b>Items:</b> {esc(items_txt(p))}<br>
        <b>Alergias:</b> {esc(', '.join(p['alergias']) or 'ninguna')}{avisos}<br>
        <b>Total:</b> {esc(cop(p['total']))} | <b>Tiempo cocina:</b> {p['tiempo_cocina']} min | <b>Entrega:</b> {p['tiempo_entrega']} min<br>
        <b>Hora:</b> {esc(p['hora'])} (hace {minutos} min){retraso}
        </div>""",
        unsafe_allow_html=True
    )

    b1, b2, b3, b4, b5 = st.columns(5)
    if p["estado"] != "entregado":
        if b1.button("🔥 Preparando", key=f"prep_{pid}", disabled=(p["estado"] != "recibido")):
            cambiar_estado(pid, "en_preparacion")
            st.rerun(scope="fragment")
        if b2.button("✅ Listo", key=f"listo_{pid}", disabled=(p["estado"] != "en_preparacion")):
            cambiar_estado(pid, "listo")
            st.rerun(scope="fragment")
        if p["tipo"] == "mesa":
            if b3.button("🍽️ Entregado en mesa", key=f"ent_{pid}", disabled=(p["estado"] != "listo")):
                cambiar_estado(pid, "entregado")
                st.rerun(scope="fragment")
        else:
            if b3.button("🛵 En camino", key=f"cam_{pid}", disabled=(p["estado"] != "listo")):
                cambiar_estado(pid, "en_camino")
                st.rerun(scope="fragment")
            if b4.button("📬 Entregado", key=f"ent_{pid}", disabled=(p["estado"] != "en_camino")):
                cambiar_estado(pid, "entregado")
                st.rerun(scope="fragment")
    if b5.button("🗑️ Eliminar", key=f"del_{pid}"):
        st.session_state["confirmar_del"] = pid
        st.rerun(scope="fragment")

    if st.session_state["confirmar_del"] == pid:
        st.warning(f"¿Eliminar {pid}? Esta acción no se puede deshacer.")
        s1, s2, _ = st.columns([1, 1, 3])
        if s1.button("Sí, eliminar", key=f"delok_{pid}"):
            eliminar_pedido(pid)
            st.session_state["confirmar_del"] = None
            st.rerun(scope="fragment")
        if s2.button("Cancelar", key=f"delno_{pid}"):
            st.session_state["confirmar_del"] = None
            st.rerun(scope="fragment")
    st.divider()


@st.fragment(run_every=5)
def panel_cocina():
    pedidos = todos_los_pedidos()
    if not pedidos:
        st.info("⏳ No hay pedidos pendientes. Esperando nuevas órdenes del cliente...")
        return

    def cuenta(*estados):
        return sum(1 for p in pedidos if p["estado"] in estados)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📥 Recibidos", cuenta("recibido"))
    c2.metric("🔥 En preparación", cuenta("en_preparacion"))
    c3.metric("✅ Listos", cuenta("listo"))
    c4.metric("🚀 En camino / Entregados", cuenta("en_camino", "entregado"))

    activos = sorted((p for p in pedidos if p["estado"] != "entregado"),
                     key=lambda p: (ORDEN_ESTADO[p["estado"]], p["ts"]))
    entregados = sorted((p for p in pedidos if p["estado"] == "entregado"),
                        key=lambda p: p["ts"], reverse=True)

    recibidos = [p for p in activos if p["estado"] == "recibido"]
    if recibidos:
        sig = min(recibidos, key=lambda p: p["ts"])
        alerta = " — ⚠️ con alergias, revisar antes" if sig["avisos"] else ""
        st.info(f"👉 **Siguiente sugerido:** {sig['id']} ({items_txt(sig)}){alerta}")
    st.divider()

    for p in activos:
        render_pedido(p)

    if entregados:
        with st.expander(f"📬 Entregados ({len(entregados)})"):
            for p in entregados:
                render_pedido(p)


if vista == "👨‍🍳 Vista Cocina / Operación" and st.session_state["cocina_autenticado"]:
    st.subheader("👨‍🍳 Panel de Cocina y Operación")
    st.caption("Los pedidos de todos los clientes llegan aquí y el panel se actualiza solo cada 5 s.")
    panel_cocina()

    with st.expander("📱 Código QR del menú (para imprimir y poner en las mesas)"):
        mostrar_qr("cocina")

    with st.expander("📦 Inventario: marcar platos agotados"):
        todos_platos = [p for _, p in PLATOS.values()]
        actuales = sorted(get_agotados())
        seleccion_ag = st.multiselect("Platos agotados hoy:", todos_platos, default=actuales)
        if set(seleccion_ag) != set(actuales):
            guardar_agotados(seleccion_ag)
            st.rerun()
        st.caption("Los platos agotados desaparecen del menú y Sofía no los ofrece ni los registra.")

    with st.expander("📊 Reporte del día"):
        hoy = datetime.now(TZ).strftime("%Y-%m-%d")
        pedidos_hoy = [p for p in todos_los_pedidos() if p.get("fecha") == hoy]
        if not pedidos_hoy:
            st.info("Aún no hay pedidos hoy.")
        else:
            res = resumen_ventas(pedidos_hoy)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("🧾 Pedidos", res["pedidos"])
            m2.metric("💰 Ventas", cop(res["ventas"]))
            m3.metric("🎟️ Ticket promedio", cop(res["ticket_promedio"]))
            m4.metric("🛵 Domicilios", res["domicilios"])
            if res["top_platos"]:
                st.markdown("**🏆 Más pedidos:** " + ", ".join(f"{n} ({c})" for n, c in res["top_platos"]))
            st.caption(f"Pedidos con alergias declaradas: {res['con_alergias']}")
            if st.button("🤖 Generar resumen con IA"):
                try:
                    with st.spinner("Analizando el día..."):
                        st.session_state["reporte_ia"] = reporte_ia(res)
                except RuntimeError:
                    st.error("❌ Falta GROQ_API_KEY.")
                except Exception:
                    st.error("❌ No se pudo generar el resumen. Intenta de nuevo.")
            if st.session_state["reporte_ia"]:
                st.markdown(st.session_state["reporte_ia"])
