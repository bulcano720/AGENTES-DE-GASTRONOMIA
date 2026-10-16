import hmac
import html
import json
import os
import threading
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st
from groq import Groq

# ==============================================================================
# CONFIGURACIÓN DE PÁGINA Y ESTILO CSS FUTURISTA / HUD
# ==============================================================================
st.set_page_config(
    page_title="Restaurante Multiagente",
    page_icon="🍽️",
    layout="wide"
)

st.markdown("""
<style>
    .stApp {
        background-color: #0a0503;
        color: #ffb347;
        font-family: 'Consolas', 'Courier New', monospace;
    }
    .header-box {
        background: linear-gradient(135deg, rgba(255, 140, 0, 0.08) 0%, rgba(255, 60, 0, 0.12) 100%);
        border: 1px solid #ff8c00;
        box-shadow: 0 0 15px rgba(255, 140, 0, 0.35);
        padding: 20px;
        border-radius: 8px;
        margin-bottom: 25px;
    }
    .header-title {
        color: #ffb347;
        text-shadow: 0 0 10px #ff8c00;
        font-weight: bold;
        font-size: 24px;
        letter-spacing: 2px;
        margin-bottom: 10px;
    }
    .header-info {
        color: #ffd9a0;
        font-size: 14px;
        margin-bottom: 4px;
    }
    div.stButton > button {
        background: linear-gradient(90deg, #ff5e00, #ffb347) !important;
        color: #1a0a00 !important;
        font-weight: bold !important;
        border: 1px solid #ffb347 !important;
        box-shadow: 0 0 10px rgba(255, 140, 0, 0.5) !important;
        border-radius: 4px !important;
    }
    div.stButton > button:hover {
        background: linear-gradient(90deg, #ffb347, #ff5e00) !important;
        box-shadow: 0 0 20px #ffb347 !important;
    }
    .stTextInput input, .stTextArea textarea {
        background-color: #1a0f05 !important;
        color: #ffb347 !important;
        border: 1px solid #ff8c00 !important;
    }
    .pedido-card {
        background: #1a0f05;
        border-left: 4px solid #ff8c00;
        padding: 10px 15px;
        margin: 8px 0;
        border-radius: 4px;
        color: #ffd9a0;
        font-size: 13px;
    }
    .pedido-alerta {
        border-left-color: #dc3545;
        color: #ffb3b3;
    }
    .estado-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: bold;
        font-size: 12px;
        margin-left: 8px;
    }
    .estado-recibido { background: #555; color: #fff; }
    .estado-en_preparacion { background: #ff8c00; color: #1a0a00; }
    .estado-listo { background: #28a745; color: #fff; }
    .estado-en_camino { background: #007bff; color: #fff; }
    .estado-entregado { background: #6c757d; color: #fff; }
</style>
""", unsafe_allow_html=True)

esc = html.escape
TZ = ZoneInfo("America/Bogota")
MODELO = "openai/gpt-oss-120b"

INTEGRANTES = "Daniel Andres Jara Olivera | Daniel Felipe Escobar Ramirez | Diana Carolina León Ocampo | Michel Harold Silva Romero"
DOCENTE = "Ricardo Alberto Jimenez"


# ==============================================================================
# 🔐 SECRETOS (Groq + credenciales de cocina). Nada de claves en el código.
# ==============================================================================
def _secret(nombre):
    try:
        return str(st.secrets[nombre])
    except Exception:
        return os.getenv(nombre, "")


COCINA_USER = _secret("COCINA_USER")
COCINA_PASS = _secret("COCINA_PASS")


@st.cache_resource
def get_client():
    key = _secret("GROQ_API_KEY")
    return Groq(api_key=key) if key else None


def credenciales_ok(usuario, contrasena):
    if not COCINA_USER or not COCINA_PASS:
        return False
    return (hmac.compare_digest(usuario.encode(), COCINA_USER.encode())
            & hmac.compare_digest(contrasena.encode(), COCINA_PASS.encode()))


for k, v in (("cocina_autenticado", False), ("mis_pedidos", []), ("carrito", [])):
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


PLATOS = {norm(p): (cat, p) for cat, ps in MENU.items() for p in ps}
ALERGENOS = {norm(a): a for ps in MENU.values() for info in ps.values() for a in info["alergenos"]}
ALIAS = {"lactosa": "lacteos", "leche": "lacteos", "queso": "lacteos", "trigo": "gluten",
         "harina": "gluten", "huevos": "huevo", "pescados": "pescado", "salmon": "pescado"}


# ==============================================================================
# 🛡️ AGENTE DE ALERGIAS (determinista, sin LLM)
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
# 🗂️ ESTADO COMPARTIDO DE PEDIDOS (visible para cliente y cocina de cualquier sesión)
# ==============================================================================
@st.cache_resource
def get_store():
    return {"lock": threading.Lock(), "pedidos": {}, "seq": 0}


STORE = get_store()


def normalizar_items(items):
    out = []
    for it in items or []:
        hit = PLATOS.get(norm(it.get("plato", "")))
        if not hit:
            raise ValueError(f"El plato '{it.get('plato')}' no existe en el menú.")
        try:
            cant = int(it.get("cantidad", 1))
        except (TypeError, ValueError):
            raise ValueError("Cantidad inválida.")
        if not 1 <= cant <= 10:
            raise ValueError("La cantidad debe estar entre 1 y 10.")
        out.append({"categoria": hit[0], "plato": hit[1], "cantidad": cant})
    if not out:
        raise ValueError("El pedido está vacío.")
    return out


def crear_pedido(tipo_entrega, mesa=None, direccion=None, telefono=None,
                 cliente="Cliente", items=None, alergias=None):
    items = normalizar_items(items)
    alergias = [a.strip() for a in (alergias or []) if a.strip()]
    if tipo_entrega == "mesa":
        if not (mesa or "").strip():
            raise ValueError("Falta el número de mesa.")
    elif tipo_entrega == "domicilio":
        if not (direccion or "").strip() or len("".join(c for c in (telefono or "") if c.isdigit())) < 7:
            raise ValueError("Para domicilio se necesita dirección y un teléfono válido.")
    else:
        raise ValueError("Tipo de entrega inválido (mesa o domicilio).")

    tiempo_cocina = sum(MENU[i["categoria"]][i["plato"]]["tiempo"] * i["cantidad"] for i in items)
    with STORE["lock"]:
        STORE["seq"] += 1
        pid = f"PED-{STORE['seq']:04d}"
        STORE["pedidos"][pid] = {
            "id": pid,
            "tipo": tipo_entrega,
            "mesa": mesa,
            "direccion": direccion,
            "telefono": telefono,
            "cliente": (cliente or "Cliente").strip() or "Cliente",
            "items": items,
            "alergias": alergias,
            "avisos": revisar_alergias(items, alergias),
            "estado": "recibido",
            "tiempo_cocina": tiempo_cocina,
            "tiempo_entrega": 20 if tipo_entrega == "domicilio" else 0,
            "hora": datetime.now(TZ).strftime("%H:%M:%S"),
        }
    st.session_state["mis_pedidos"].append(pid)
    return pid


def get_pedido(pid):
    with STORE["lock"]:
        p = STORE["pedidos"].get(pid)
        return dict(p) if p else None


def pedidos_de_sesion():
    return [p for p in map(get_pedido, st.session_state["mis_pedidos"]) if p]


def todos_los_pedidos():
    with STORE["lock"]:
        return [dict(p) for p in STORE["pedidos"].values()]


def cambiar_estado(pid, nuevo_estado):
    with STORE["lock"]:
        if pid in STORE["pedidos"]:
            STORE["pedidos"][pid]["estado"] = nuevo_estado


def eliminar_pedido(pid):
    with STORE["lock"]:
        STORE["pedidos"].pop(pid, None)


def badge_estado(estado):
    return f'<span class="estado-badge estado-{estado}">{esc(estado.upper().replace("_", " "))}</span>'


def items_txt(p):
    return ", ".join(f"{i['cantidad']}x {i['plato']}" for i in p["items"]) or "—"


# ==============================================================================
# 🤖 AGENTE SOFÍA (Groq con herramienta crear_pedido)
# ==============================================================================
PROMPT_CLIENTE = (
    "Eres Sofía, la asistente IA del restaurante 'Sabor Digital'. Eres cálida, "
    "cordial y eficiente. Ayudas al cliente a elegir platos del menú, preguntas por "
    "alergias, sugieres entradas/bebidas/postres y registras el pedido. "
    "Responde siempre en español y con calidez."
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
            lineas.append(f"  - {nombre} (${info['precio']:,} | {info['tiempo']} min | alérgenos: {alerg})")
    return "\n".join(lineas)


MENU_TEXTO = texto_menu_para_prompt()

TOOLS = [{
    "type": "function",
    "function": {
        "name": "crear_pedido",
        "description": "Registra el pedido en cocina. Úsala SOLO cuando el cliente haya confirmado "
                       "explícitamente platos, cantidades, datos de entrega y alergias.",
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
                "telefono": {"type": "string"},
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
        return {"ok": True, "pedido": pid, "tiempo_cocina_min": p["tiempo_cocina"],
                "tiempo_entrega_min": p["tiempo_entrega"], "avisos_alergias": p["avisos"]}
    except ValueError as e:
        return {"ok": False, "error": str(e)}


TOOL_FUNCS = {"crear_pedido": tool_crear_pedido}


def resumen_pedidos_texto():
    mios = pedidos_de_sesion()
    if not mios:
        return "Este cliente no tiene pedidos."
    return "\n".join(
        f"- {p['id']} | {p['estado']} | {p['mesa'] or p['direccion'] or '—'} | {items_txt(p)}" for p in mios
    )


def sofia_responder(historial):
    client = get_client()
    if client is None:
        raise RuntimeError("Falta GROQ_API_KEY")
    system_prompt = (
        f"{PROMPT_CLIENTE}\n\n📋 MENÚ:\n{MENU_TEXTO}\n\n"
        f"📦 PEDIDOS DE ESTE CLIENTE:\n{resumen_pedidos_texto()}\n\n"
        "INSTRUCCIONES:\n"
        "- Antes de llamar a crear_pedido confirma platos, cantidades, tipo de entrega "
        "(mesa o domicilio con dirección y teléfono) y alergias.\n"
        "- Tras crear el pedido informa su número, el tiempo estimado y los avisos de alergias.\n"
        "- Nunca ofrezcas platos que no estén en el menú.\n"
        "- Si pregunta por el estado de su pedido, respóndelo según los pedidos listados."
    )
    mensajes = [{"role": "system", "content": system_prompt}] + historial
    for _ in range(4):
        r = client.chat.completions.create(
            messages=mensajes, model=MODELO, max_tokens=600, temperature=0.5,
            tools=TOOLS, tool_choice="auto",
        )
        msg = r.choices[0].message
        if not msg.tool_calls:
            return msg.content or ""
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


# ==============================================================================
# ENCABEZADO
# ==============================================================================
st.markdown(f"""
<div class="header-box">
    <div class="header-title">🍽️ SISTEMA MULTIAGENTE - RESTAURANTE "SABOR DIGITAL"</div>
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
    if not COCINA_USER or not COCINA_PASS:
        st.error("🔒 La vista de cocina está deshabilitada: configura COCINA_USER y COCINA_PASS en los secrets.")
        st.stop()
    st.warning("🔒 Acceso restringido. Ingresa tus credenciales de cocina.")
    with st.form("login_cocina"):
        usuario = st.text_input("Usuario:")
        contrasena = st.text_input("Contraseña:", type="password")
        entrar = st.form_submit_button("🔓 Ingresar")
    if entrar:
        if credenciales_ok(usuario, contrasena):
            st.session_state["cocina_autenticado"] = True
            st.rerun()
        else:
            st.error("❌ Usuario o contraseña incorrectos.")
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
    for p in reversed(mios):
        avisos = "".join(f"<br>{esc(a)}" for a in p["avisos"])
        st.markdown(
            f"<div class='pedido-card'><b>{esc(p['id'])}</b> {badge_estado(p['estado'])}<br>"
            f"Items: {esc(items_txt(p))}<br>"
            f"Hora: {esc(p['hora'])} | Tiempo cocina: {p['tiempo_cocina']} min{avisos}</div>",
            unsafe_allow_html=True
        )


if vista == "👤 Vista Cliente (Usuario)":

    col_menu, col_chat = st.columns([1.2, 1])

    # ------------------------------ COLUMNA MENÚ ------------------------------
    with col_menu:
        st.subheader("📋 Nuestro Menú")
        for cat, platos in MENU.items():
            with st.expander(f"{cat} ({len(platos)} platos)", expanded=False):
                for nombre, info in platos.items():
                    alerg = ", ".join(info["alergenos"]) if info["alergenos"] else "sin alérgenos"
                    st.markdown(
                        f"**{nombre}** — 💰 ${info['precio']:,} — ⏱️ {info['tiempo']} min  \n"
                        f"⚠️ _{alerg}_"
                    )

        st.divider()
        st.subheader("🛒 Hacer Pedido Rápido")

        # Estos selectores van FUERA del form para que los campos dependientes se actualicen al instante.
        tipo = st.selectbox("Tipo de entrega:", ["mesa", "domicilio"])
        categoria_sel = st.selectbox("Categoría:", list(MENU.keys()))

        with st.form("form_pedido_cliente"):
            cliente_nombre = st.text_input("Tu nombre:", value="Cliente")
            if tipo == "mesa":
                mesa_input = st.text_input("Número de mesa:", value="1")
                dir_input = tel_input = None
            else:
                dir_input = st.text_input("Dirección:", placeholder="Cra 45 #12-34")
                tel_input = st.text_input("Teléfono:", placeholder="3001234567")
                mesa_input = None
            plato_sel = st.selectbox("Plato:", list(MENU[categoria_sel].keys()))
            cantidad_sel = st.number_input("Cantidad:", min_value=1, max_value=10, value=1)
            alergias_input = st.text_input("Alergias (separadas por coma):", value="")
            b1, b2 = st.columns(2)
            agregar = b1.form_submit_button("➕ Agregar al pedido")
            enviar = b2.form_submit_button("✅ Enviar pedido a cocina")

        seleccion = {"categoria": categoria_sel, "plato": plato_sel, "cantidad": int(cantidad_sel)}
        if agregar:
            st.session_state["carrito"].append(seleccion)
        carrito = st.session_state["carrito"]
        if carrito:
            st.markdown("**Tu pedido:** " + ", ".join(f"{i['cantidad']}x {i['plato']}" for i in carrito))
            if st.button("🧹 Vaciar pedido"):
                st.session_state["carrito"] = []
                st.rerun()

        if enviar:
            try:
                pid = crear_pedido(
                    tipo_entrega=tipo, mesa=mesa_input, direccion=dir_input, telefono=tel_input,
                    cliente=cliente_nombre, items=carrito or [seleccion],
                    alergias=alergias_input.split(","),
                )
                p = get_pedido(pid)
                st.session_state["carrito"] = []
                st.success(f"✅ Pedido **{pid}** enviado a cocina. Tiempo estimado: {p['tiempo_cocina']} min.")
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

        if user_input := st.chat_input("Escribe tu mensaje a Sofía..."):
            historial = st.session_state[chat_key] + [{"role": "user", "content": user_input}]
            with st.spinner("Sofía está pensando..."):
                try:
                    respuesta = sofia_responder(historial)
                    st.session_state[chat_key] = historial + [{"role": "assistant", "content": respuesta}]
                    st.rerun()
                except RuntimeError:
                    st.error("❌ Sofía no está configurada (falta GROQ_API_KEY).")
                except Exception:
                    st.error("❌ No pude contactar a Sofía. Intenta de nuevo en unos segundos.")

        if st.button("🗑️ Limpiar chat"):
            st.session_state[chat_key] = [{"role": "assistant", "content": SALUDO_CLIENTE}]
            st.rerun()


# ==============================================================================
# 👨‍🍳 VISTA COCINA / OPERACIÓN
# ==============================================================================
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
    st.divider()

    for p in pedidos:
        pid = p["id"]
        st.markdown(
            f"#### 🧾 {esc(pid)} — {esc(p['cliente'])} ({esc(p['tipo'].upper())}) {badge_estado(p['estado'])}",
            unsafe_allow_html=True
        )
        ubicacion = p["mesa"] or p["direccion"] or "—"
        telefono = f"<b>Teléfono:</b> {esc(p['telefono'])}<br>" if p["telefono"] else ""
        avisos = "".join(f"<br>{esc(a)}" for a in p["avisos"])
        clase = "pedido-card pedido-alerta" if p["avisos"] else "pedido-card"
        st.markdown(
            f"""<div class="{clase}">
            <b>Ubicación:</b> {esc(str(ubicacion))}<br>{telefono}
            <b>Items:</b> {esc(items_txt(p))}<br>
            <b>Alergias:</b> {esc(', '.join(p['alergias']) or 'ninguna')}{avisos}<br>
            <b>Tiempo cocina:</b> {p['tiempo_cocina']} min | <b>Entrega:</b> {p['tiempo_entrega']} min<br>
            <b>Hora:</b> {esc(p['hora'])}
            </div>""",
            unsafe_allow_html=True
        )

        b1, b2, b3, b4, b5 = st.columns(5)
        if b1.button("🔥 Preparando", key=f"prep_{pid}", disabled=(p["estado"] != "recibido")):
            cambiar_estado(pid, "en_preparacion")
            st.rerun()
        if b2.button("✅ Listo", key=f"listo_{pid}", disabled=(p["estado"] != "en_preparacion")):
            cambiar_estado(pid, "listo")
            st.rerun()
        if p["tipo"] == "mesa":
            if b3.button("🍽️ Entregado en mesa", key=f"ent_{pid}", disabled=(p["estado"] != "listo")):
                cambiar_estado(pid, "entregado")
                st.rerun()
        else:
            if b3.button("🛵 En camino", key=f"cam_{pid}", disabled=(p["estado"] != "listo")):
                cambiar_estado(pid, "en_camino")
                st.rerun()
            if b4.button("📬 Entregado", key=f"ent_{pid}", disabled=(p["estado"] != "en_camino")):
                cambiar_estado(pid, "entregado")
                st.rerun()
        if b5.button("🗑️ Eliminar", key=f"del_{pid}"):
            eliminar_pedido(pid)
            st.rerun()
        st.divider()


if vista == "👨‍🍳 Vista Cocina / Operación" and st.session_state["cocina_autenticado"]:
    st.subheader("👨‍🍳 Panel de Cocina y Operación")
    st.caption("Los pedidos de todos los clientes llegan aquí y el panel se actualiza solo cada 5 s.")
    panel_cocina()
