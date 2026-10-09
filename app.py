import os
import random
from datetime import datetime
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

# ==============================================================================
# CLIENTE GROQ
# ==============================================================================
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except Exception:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

client = Groq(api_key=GROQ_API_KEY)

INTEGRANTES = "Daniel Andres Jara Olivera | Daniel Felipe Escobar Ramirez | Diana Carolina León Ocampo | Michel Harold Silva Romero"
DOCENTE = "Ricardo Alberto Jimenez"

# ==============================================================================
# 🔐 CREDENCIALES DE ACCESO A COCINA
# ==============================================================================
COCINA_USER = "cocina"
COCINA_PASS = "cocina123"

if "cocina_autenticado" not in st.session_state:
    st.session_state["cocina_autenticado"] = False

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

# ==============================================================================
# PROMPTS
# ==============================================================================
PROMPT_CLIENTE = (
    "Eres Sofía, la asistente IA del restaurante 'Sabor Digital'. Eres cálida, "
    "cordial y eficiente. Ayudas al cliente a elegir platos del menú, preguntas por "
    "alergias, sugieres entradas/bebidas/postres, y confirmas el pedido. Cuando el "
    "cliente confirme, indícale su número de pedido y el tiempo estimado de preparación. "
    "También puedes informarle el estado actual de su pedido si te lo pregunta. "
    "Responde siempre en español y con calidez."
)

SALUDO_CLIENTE = (
    "¡Hola! 👋 Soy **Sofía**, tu asistente IA del restaurante 🍽️. "
    "Puedo mostrarte el menú, tomar tu pedido y avisarte cuando esté listo. "
    "¿Qué se te antoja hoy?"
)

def invocar_llama(mensajes):
    response = client.chat.completions.create(
        messages=mensajes,
        model="openai/gpt-oss-120b",
        max_tokens=600,
        temperature=0.7
    )
    return response.choices[0].message.content

def texto_menu_para_prompt():
    lineas = []
    for cat, platos in MENU.items():
        lineas.append(f"\n{cat}:")
        for nombre, info in platos.items():
            alerg = ", ".join(info["alergenos"]) if info["alergenos"] else "ninguno"
            lineas.append(
                f"  - {nombre} (${info['precio']:,} | {info['tiempo']} min | alérgenos: {alerg})"
            )
    return "\n".join(lineas)

MENU_TEXTO = texto_menu_para_prompt()

# ==============================================================================
# 🗂️ ESTADO GLOBAL DE PEDIDOS
# ==============================================================================
if "pedidos" not in st.session_state:
    st.session_state["pedidos"] = {}

def nuevo_pedido_id():
    return f"PED-{random.randint(1000, 9999)}"

def crear_pedido(tipo_entrega, mesa=None, direccion=None, telefono=None,
                 cliente="Cliente", items=None, alergias=None):
    pid = nuevo_pedido_id()
    items = items or []

    tiempo_cocina = 0
    for it in items:
        cat = it.get("categoria")
        plato = it.get("plato")
        if cat in MENU and plato in MENU[cat]:
            tiempo_cocina += MENU[cat][plato]["tiempo"] * it.get("cantidad", 1)

    tiempo_entrega = 20 if tipo_entrega == "domicilio" else 0

    st.session_state["pedidos"][pid] = {
        "id": pid,
        "tipo": tipo_entrega,
        "mesa": mesa,
        "direccion": direccion,
        "telefono": telefono,
        "cliente": cliente,
        "items": items,
        "alergias": alergias or [],
        "estado": "recibido",
        "tiempo_cocina": tiempo_cocina,
        "tiempo_entrega": tiempo_entrega,
        "hora": datetime.now().strftime("%H:%M:%S"),
    }
    return pid

def cambiar_estado(pid, nuevo_estado):
    if pid in st.session_state["pedidos"]:
        st.session_state["pedidos"][pid]["estado"] = nuevo_estado

def resumen_pedidos_texto():
    pedidos = st.session_state["pedidos"]
    if not pedidos:
        return "Sin pedidos activos."
    lineas = []
    for p in pedidos.values():
        items_str = ", ".join([i["plato"] for i in p["items"]]) or "—"
        ubicacion = p["mesa"] or p["direccion"] or "—"
        lineas.append(
            f"- {p['id']} | {p['estado']} | Ubicación: {ubicacion} | Items: {items_str}"
        )
    return "\n".join(lineas)

def badge_estado(estado):
    return f'<span class="estado-badge estado-{estado}">{estado.upper().replace("_", " ")}</span>'

# ==============================================================================
# ENCABEZADO
# ==============================================================================
st.markdown(f"""
<div class="header-box">
    <div class="header-title">🍽️ SISTEMA MULTIAGENTE - RESTAURANTE "SABOR DIGITAL"</div>
    <div class="header-info"><b>👨‍🏫 DOCENTE:</b> {DOCENTE}</div>
    <div class="header-info"><b>👥 INTEGRANTES:</b> {INTEGRANTES}</div>
</div>
""", unsafe_allow_html=True)

# ==============================================================================
# 🧭 SELECTOR DE VISTA PRINCIPAL (CLIENTE vs COCINA con login)
# ==============================================================================
vista = st.radio(
    "🧭 SELECCIONA LA VISTA:",
    ["👤 Vista Cliente (Usuario)", "👨‍🍳 Vista Cocina / Operación"],
    horizontal=True
)

st.divider()

# ----------------------- LOGIN OBLIGATORIO PARA COCINA -----------------------
if vista == "👨‍🍳 Vista Cocina / Operación" and not st.session_state["cocina_autenticado"]:
    st.warning("🔒 Acceso restringido. Ingresa tus credenciales de cocina.")

    with st.form("login_cocina"):
        usuario = st.text_input("Usuario:")
        contrasena = st.text_input("Contraseña:", type="password")
        entrar = st.form_submit_button("🔓 Ingresar")

    if entrar:
        if usuario == COCINA_USER and contrasena == COCINA_PASS:
            st.session_state["cocina_autenticado"] = True
            st.success("✅ Acceso concedido. Cargando panel de cocina...")
            st.rerun()
        else:
            st.error("❌ Usuario o contraseña incorrectos.")

    st.stop()

# -----------------------------------------------------------------------------
# Botón para cerrar sesión de cocina
# -----------------------------------------------------------------------------
if vista == "👨‍🍳 Vista Cocina / Operación" and st.session_state["cocina_autenticado"]:
    col_logout, _ = st.columns([1, 4])
    with col_logout:
        if st.button("🔒 Cerrar sesión de cocina"):
            st.session_state["cocina_autenticado"] = False
            st.rerun()

# ==============================================================================
# 👤 VISTA CLIENTE
# ==============================================================================
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
        with st.form("form_pedido_cliente"):
            tipo = st.selectbox("Tipo de entrega:", ["mesa", "domicilio"])
            cliente_nombre = st.text_input("Tu nombre:", value="Cliente")
            if tipo == "mesa":
                mesa_input = st.text_input("Número de mesa:", value="1")
                dir_input, tel_input = None, None
            else:
                dir_input = st.text_input("Dirección:", value="Cra 45 #12-34")
                tel_input = st.text_input("Teléfono:", value="3001234567")
                mesa_input = None

            categoria_sel = st.selectbox("Categoría:", list(MENU.keys()))
            plato_sel = st.selectbox("Plato:", list(MENU[categoria_sel].keys()))
            cantidad_sel = st.number_input("Cantidad:", min_value=1, max_value=10, value=1)
            alergias_input = st.text_input("Alergias (separadas por coma):", value="")

            enviar = st.form_submit_button("✅ Enviar pedido a cocina")

        if enviar:
            items = [{
                "categoria": categoria_sel,
                "plato": plato_sel,
                "cantidad": cantidad_sel,
            }]
            alergias_lista = [a.strip() for a in alergias_input.split(",") if a.strip()]
            pid = crear_pedido(
                tipo_entrega=tipo,
                mesa=mesa_input,
                direccion=dir_input,
                telefono=tel_input,
                cliente=cliente_nombre,
                items=items,
                alergias=alergias_lista,
            )
            st.success(f"✅ Pedido **{pid}** enviado a cocina. Tiempo estimado: {st.session_state['pedidos'][pid]['tiempo_cocina']} min.")

    # ------------------------------ COLUMNA CHAT ------------------------------
    with col_chat:
        st.subheader("💬 Chat con Sofía")

        pedidos_cliente = list(st.session_state["pedidos"].values())
        if pedidos_cliente:
            st.markdown("### 📦 Estado de tus pedidos")
            for p in reversed(pedidos_cliente):
                items_txt = ", ".join([f"{i['cantidad']}x {i['plato']}" for i in p["items"]])
                st.markdown(
                    f"<div class='pedido-card'>"
                    f"<b>{p['id']}</b> {badge_estado(p['estado'])}<br>"
                    f"Items: {items_txt}<br>"
                    f"Hora: {p['hora']} | Tiempo cocina: {p['tiempo_cocina']} min"
                    f"</div>",
                    unsafe_allow_html=True
                )
        else:
            st.info("Aún no tienes pedidos registrados.")

        st.divider()

        chat_key = "chat_cliente"
        if chat_key not in st.session_state:
            st.session_state[chat_key] = [
                {"role": "assistant", "content": SALUDO_CLIENTE}
            ]

        chat_container = st.container(height=400)
        with chat_container:
            for msg in st.session_state[chat_key]:
                st.chat_message(msg["role"]).write(msg["content"])

        if user_input := st.chat_input("Escribe tu mensaje a Sofía..."):
            st.session_state[chat_key].append({"role": "user", "content": user_input})
            with chat_container:
                st.chat_message("user").write(user_input)

            resumen = resumen_pedidos_texto()
            system_prompt = (
                f"{PROMPT_CLIENTE}\n\n"
                f"📋 MENÚ:\n{MENU_TEXTO}\n\n"
                f"📦 PEDIDOS ACTIVOS:\n{resumen}\n\n"
                "INSTRUCCIONES:\n"
                "- Si el cliente confirma un pedido, recuérdale que puede registrarlo en el formulario.\n"
                "- Si pregunta por el estado de su pedido, infórmalo según los pedidos activos.\n"
                "- Responde con calidez en español."
            )

            mensajes_api = [{"role": "system", "content": system_prompt}]
            for m in st.session_state[chat_key]:
                mensajes_api.append({"role": m["role"], "content": m["content"]})

            with chat_container:
                with st.chat_message("assistant"):
                    with st.spinner("Pensando..."):
                        try:
                            respuesta = invocar_llama(mensajes_api)
                            st.write(respuesta)
                            st.session_state[chat_key].append(
                                {"role": "assistant", "content": respuesta}
                            )
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")

        if st.button("🗑️ Limpiar chat"):
            st.session_state[chat_key] = [
                {"role": "assistant", "content": SALUDO_CLIENTE}
            ]
            st.rerun()

# ==============================================================================
# 👨‍🍳 VISTA COCINA / OPERACIÓN
# ==============================================================================
elif vista == "👨‍🍳 Vista Cocina / Operación" and st.session_state["cocina_autenticado"]:

    st.subheader("👨‍🍳 Panel de Cocina y Operación")
    st.caption("Aquí llegan los pedidos del cliente. Cambia el estado según avance la preparación.")

    pedidos = st.session_state["pedidos"]
    if not pedidos:
        st.info("⏳ No hay pedidos pendientes. Esperando nuevas órdenes del cliente...")
    else:
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("📥 Recibidos", sum(1 for p in pedidos.values() if p["estado"] == "recibido"))
        col_m2.metric("🔥 En preparación", sum(1 for p in pedidos.values() if p["estado"] == "en_preparacion"))
        col_m3.metric("✅ Listos", sum(1 for p in pedidos.values() if p["estado"] == "listo"))
        col_m4.metric("🚀 En camino / Entregados",
                      sum(1 for p in pedidos.values() if p["estado"] in ("en_camino", "entregado")))

        st.divider()

        for pid, p in list(pedidos.items()):
            with st.container():
                st.markdown(
                    f"#### 🧾 {pid} — {p['cliente']} ({p['tipo'].upper()}) {badge_estado(p['estado'])}",
                    unsafe_allow_html=True
                )
                items_txt = ", ".join([f"{i['cantidad']}x {i['plato']}" for i in p["items"]]) or "—"
                ubicacion = p["mesa"] or p["direccion"] or "—"

                st.markdown(
                    f"""<div class="pedido-card">
                    <b>Ubicación:</b> {ubicacion}<br>
                    <b>Items:</b> {items_txt}<br>
                    <b>Alergias:</b> {', '.join(p['alergias']) or 'ninguna'}<br>
                    <b>Tiempo cocina:</b> {p['tiempo_cocina']} min |
                    <b>Entrega:</b> {p['tiempo_entrega']} min<br>
                    <b>Hora:</b> {p['hora']}
                    </div>""",
                    unsafe_allow_html=True
                )

                c1, c2, c3, c4, c5 = st.columns(5)

                if c1.button("🔥 Preparando", key=f"prep_{pid}", disabled=(p["estado"] != "recibido")):
                    cambiar_estado(pid, "en_preparacion")
                    st.rerun()

                if c2.button("✅ Listo", key=f"listo_{pid}", disabled=(p["estado"] != "en_preparacion")):
                    cambiar_estado(pid, "listo")
                    st.rerun()

                if p["tipo"] == "mesa":
                    if c3.button("🍽️ Entregado en mesa", key=f"ent_{pid}", disabled=(p["estado"] != "listo")):
                        cambiar_estado(pid, "entregado")
                        st.rerun()
                else:
                    if c3.button("🛵 En camino", key=f"cam_{pid}", disabled=(p["estado"] != "listo")):
                        cambiar_estado(pid, "en_camino")
                        st.rerun()
                    if c4.button("📬 Entregado", key=f"ent_{pid}", disabled=(p["estado"] != "en_camino")):
                        cambiar_estado(pid, "entregado")
                        st.rerun()

                if c5.button("🗑️ Eliminar", key=f"del_{pid}"):
                    del st.session_state["pedidos"][pid]
                    st.rerun()

                st.divider()
