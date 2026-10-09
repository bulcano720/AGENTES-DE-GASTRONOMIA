import os
import random
from datetime import datetime
import streamlit as st
from huggingface_hub import InferenceClient

# ==============================================================================
# CONFIGURACIÓN DE PÁGINA Y ESTILO CSS FUTURISTA / HUD
# ==============================================================================
st.set_page_config(
    page_title="HUD Restaurante Multiagent",
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
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# CLIENTE HUGGING FACE
# ==============================================================================
try:
    HF_TOKEN = st.secrets["HF_TOKEN"]
except Exception:
    HF_TOKEN = os.getenv("HF_TOKEN", "")

client = InferenceClient(
    model="meta-llama/Llama-3.1-8B-Instruct",
    token=HF_TOKEN
)

INTEGRANTES = "Daniel Andres Jara Olivera | Daniel Felipe Escobar Ramirez | Diana Carolina León Ocampo | Michel Harold Silva Romero"
DOCENTE = "Ricardo Alberto Jimenez"

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
# PROMPTS DE ROLES
# ==============================================================================
PROMPTS_ROLES = {
    "👤 Cliente (Mesa)": (
        "Eres Sofía, mesera IA del restaurante, atendiendo a un cliente SENTADO EN MESA. "
        "Eres cálida, cordial y eficiente. Ayudas a elegir platos del menú, preguntas por "
        "alergias, sugieres entradas/bebidas/postres, confirmas pedidos y avisas el tiempo "
        "estimado. Confirmas cuando el mesero llevará la comida a la mesa."
    ),
    "📱 Cliente (Domicilio)": (
        "Eres Sofía, asistente IA del restaurante atendiendo a un cliente para DOMICILIO. "
        "Amable y clara. Tomas pedido, pides dirección y teléfono, informas tiempo de "
        "preparación + tiempo de entrega, y avisas cuando el repartidor sale con el pedido."
    ),
    "👨‍🍳 Cocinero": (
        "Eres el Chef IA del restaurante. Recibes pedidos estructurados, informas tiempo "
        "estimado de preparación, actualizas estados (recibido → en_preparacion → listo), "
        "avisas si falta un ingrediente y notificas cuando el plato está listo para entregar."
    ),
    "🧑‍💼 Mesero": (
        "Eres el mesero IA del restaurante. Recibes alertas cuando un pedido está listo "
        "en cocina y debes llevarlo a la mesa correspondiente. Confirmas cuando entregas "
        "el pedido. Puedes consultar detalles (alergias, notas) de cualquier pedido."
    ),
    "🛵 Repartidor": (
        "Eres el repartidor IA del restaurante. Recibes alertas cuando un pedido para "
        "domicilio está listo, con dirección y teléfono del cliente. Confirmas recogida "
        "y entrega. Informas al cliente cuando vas en camino."
    ),
}

SALUDOS = {
    "👤 Cliente (Mesa)": "¡Hola! 👋 Soy **Sofía**, tu mesera IA. Bienvenido al restaurante 🍽️. ¿Te muestro el menú o ya sabes qué se te antoja hoy?",
    "📱 Cliente (Domicilio)": "¡Hola! 🛵 Soy **Sofía**, asistente de domicilios. Con gusto tomo tu pedido. ¿Qué se te antoja hoy?",
    "👨‍🍳 Cocinero": "👨‍🍳 **Chef IA** en línea. Listo para recibir pedidos y reportar tiempos. ¿Nuevo pedido o consulta de estado?",
    "🧑‍💼 Mesero": "🧑‍💼 **Mesero IA** activo. Recibirás alertas cuando haya pedidos listos para llevar a mesa.",
    "🛵 Repartidor": "🛵 **Repartidor IA** activo. Te avisaré cuando tengas un pedido listo para entrega a domicilio.",
}

def invocar_llama(mensajes):
    """Consulta a Llama 3.1 en Hugging Face."""
    response = client.chat_completion(
        messages=mensajes,
        max_tokens=600,
        temperature=0.7
    )
    return response.choices[0].message.content

def texto_menu_para_prompt():
    """Convierte el menú a texto legible para el prompt."""
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
            tiempo_cocina += MENU[cat][plato]["tiempo"]

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
    """Devuelve texto con los pedidos activos."""
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
# PESTAÑAS
# ==============================================================================
tab_menu, tab_pedidos, tab_chat = st.tabs([
    "📋 Menú", "📦 Panel de Pedidos", "💬 Chat por Rol"
])

# ------------------------------------------------------------------------------
# TAB 1: MENÚ
# ------------------------------------------------------------------------------
with tab_menu:
    st.subheader("📋 Nuestro Menú")
    cols = st.columns(len(MENU))
    for i, (cat, platos) in enumerate(MENU.items()):
        with cols[i]:
            st.markdown(f"### {cat}")
            for nombre, info in platos.items():
                alerg = ", ".join(info["alergenos"]) if info["alergenos"] else "sin alérgenos"
                st.markdown(
                    f"**{nombre}**  \n"
                    f"💰 ${info['precio']:,}  \n"
                    f"⏱️ {info['tiempo']} min  \n"
                    f"⚠️ {alerg}"
                )

# ------------------------------------------------------------------------------
# TAB 2: PANEL DE PEDIDOS
# ------------------------------------------------------------------------------
with tab_pedidos:
    st.subheader("📦 Panel de Pedidos en Vivo")

    # --- Formulario rápido para crear pedidos manualmente ---
    with st.expander("➕ Crear pedido manualmente (para pruebas)"):
        col1, col2 = st.columns(2)
        with col1:
            tipo = st.selectbox("Tipo de entrega:", ["mesa", "domicilio"])
            cliente_nombre = st.text_input("Nombre del cliente:", value="Cliente Demo")
            if tipo == "mesa":
                mesa_input = st.text_input("Mesa:", value="1")
                dir_input = None
                tel_input = None
            else:
                dir_input = st.text_input("Dirección:", value="Cra 45 #12-34")
                tel_input = st.text_input("Teléfono:", value="3001234567")
                mesa_input = None
        with col2:
            categoria_sel = st.selectbox("Categoría:", list(MENU.keys()))
            plato_sel = st.selectbox("Plato:", list(MENU[categoria_sel].keys()))
            cantidad_sel = st.number_input("Cantidad:", min_value=1, max_value=10, value=1)
            alergias_input = st.text_input("Alergias (separadas por coma):", value="")

        if st.button("✅ Registrar pedido"):
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
            st.success(f"Pedido {pid} creado con éxito.")
            st.rerun()

    st.divider()

    pedidos = st.session_state["pedidos"]
    if not pedidos:
        st.info("Aún no hay pedidos. Puedes crearlos manualmente arriba o conversando con el agente.")
    else:
        for pid, p in list(pedidos.items()):
            with st.container():
                st.markdown(f"#### 🧾 {pid} — {p['cliente']} ({p['tipo'].upper()})")
                items_txt = ", ".join([f"{i['cantidad']}x {i['plato']}" for i in p["items"]]) or "—"
                ubicacion = p["mesa"] or p["direccion"] or "—"
                st.markdown(
                    f"""<div class="pedido-card">
                    <b>Estado:</b> {p['estado'].upper()}<br>
                    <b>Mesa/Dirección:</b> {ubicacion}<br>
                    <b>Items:</b> {items_txt}<br>
                    <b>Alergias:</b> {', '.join(p['alergias']) or 'ninguna'}<br>
                    <b>Tiempo cocina:</b> {p['tiempo_cocina']} min |
                    <b>Entrega:</b> {p['tiempo_entrega']} min<br>
                    <b>Hora:</b> {p['hora']}
                    </div>""",
                    unsafe_allow_html=True
                )

                col1, col2, col3, col4 = st.columns(4)
                if col1.button("👨‍🍳 Preparando", key=f"prep_{pid}"):
                    cambiar_estado(pid, "en_preparacion")
                    st.rerun()
                if col2.button("✅ Listo", key=f"listo_{pid}"):
                    cambiar_estado(pid, "listo")
                    destino = "mesero" if p["tipo"] == "mesa" else "repartidor"
                    st.success(f"🔔 Pedido {pid} LISTO. Notificar al {destino}.")
                    st.rerun()
                if col3.button("🍽️ Entregado", key=f"ent_{pid}"):
                    cambiar_estado(pid, "entregado")
                    st.rerun()
                if col4.button("🗑️ Eliminar", key=f"del_{pid}"):
                    del st.session_state["pedidos"][pid]
                    st.rerun()
                st.divider()

# ------------------------------------------------------------------------------
# TAB 3: CHAT POR ROL
# ------------------------------------------------------------------------------
with tab_chat:
    st.subheader("💬 Terminal de Atención por Rol")

    rol_actual = st.selectbox(
        "SELECCIONAR ROL:",
        options=list(PROMPTS_ROLES.keys())
    )

    # --- Contexto según rol ---
    contexto_extra = ""
    if rol_actual == "👤 Cliente (Mesa)":
        mesa = st.text_input("Número de mesa:", value="1")
        contexto_extra = f"El cliente está en la MESA {mesa}."
    elif rol_actual == "📱 Cliente (Domicilio)":
        direccion = st.text_input("Dirección de entrega:", value="Cra 45 #12-34")
        telefono = st.text_input("Teléfono:", value="3001234567")
        contexto_extra = f"Pedido a domicilio. Dirección: {direccion}. Teléfono: {telefono}."
    elif rol_actual == "🧑‍💼 Mesero":
        pedidos_listos_mesa = [p for p in st.session_state["pedidos"].values()
                               if p["estado"] == "listo" and p["tipo"] == "mesa"]
        if pedidos_listos_mesa:
            st.warning("🔔 **Pedidos listos para llevar a mesa:**")
            for p in pedidos_listos_mesa:
                st.write(f"- {p['id']} → Mesa {p['mesa']}")
        else:
            st.info("Sin pedidos listos para mesa por ahora.")
    elif rol_actual == "🛵 Repartidor":
        pedidos_listos_dom = [p for p in st.session_state["pedidos"].values()
                              if p["estado"] == "listo" and p["tipo"] == "domicilio"]
        if pedidos_listos_dom:
            st.warning("🔔 **Pedidos listos para entrega a domicilio:**")
            for p in pedidos_listos_dom:
                st.write(f"- {p['id']} → {p['direccion']} | Tel: {p['telefono']}")
        else:
            st.info("Sin pedidos listos para domicilio por ahora.")
    elif rol_actual == "👨‍🍳 Cocinero":
        activos = [p for p in st.session_state["pedidos"].values()
                   if p["estado"] in ("recibido", "en_preparacion")]
        if activos:
            st.warning(f"👨‍🍳 **{len(activos)} pedido(s) en cocina:**")
            for p in activos:
                items_str = ", ".join([i["plato"] for i in p["items"]])
                st.write(f"- {p['id']} ({p['estado']}) → {items_str}")
        else:
            st.info("Sin pedidos pendientes en cocina.")

    # --- Historial de chat por rol ---
    chat_key = f"messages_{rol_actual}"
    if chat_key not in st.session_state:
        st.session_state[chat_key] = [
            {"role": "assistant", "content": SALUDOS[rol_actual]}
        ]

    for msg in st.session_state[chat_key]:
        st.chat_message(msg["role"]).write(msg["content"])

    # --- Input del usuario ---
    if user_input := st.chat_input("Escribe tu mensaje..."):
        st.session_state[chat_key].append({"role": "user", "content": user_input})
        st.chat_message("user").write(user_input)

        # Calcular resumen ANTES del f-string
        resumen = resumen_pedidos_texto()

        instrucciones = PROMPTS_ROLES[rol_actual]
        system_prompt = (
            f"{instrucciones}\n\n"
            f"📋 MENÚ DISPONIBLE DEL RESTAURANTE:\n{MENU_TEXTO}\n\n"
            f"📦 PEDIDOS ACTIVOS EN EL SISTEMA:\n{resumen}\n\n"
            f"CONTEXTO ADICIONAL: {contexto_extra}\n\n"
            "INSTRUCCIONES:\n"
            "- Cuando un cliente confirme un pedido, dile que se registró y da tiempo estimado.\n"
            "- Si eres cocinero y marcas listo, avisa: '✅ Pedido listo para mesero/repartidor'.\n"
            "- Si eres mesero y te avisan de pedido listo, confirma cuando lo entregas.\n"
            "- Si eres repartidor, confirma salida y entrega.\n"
            "- Responde SIEMPRE con calidez y en español."
        )

        mensajes_api = [{"role": "system", "content": system_prompt}]
        for m in st.session_state[chat_key]:
            mensajes_api.append({"role": m["role"], "content": m["content"]})

        with st.chat_message("assistant"):
            with st.spinner("Pensando respuesta..."):
                try:
                    respuesta = invocar_llama(mensajes_api)
                    st.write(respuesta)
                    st.session_state[chat_key].append(
                        {"role": "assistant", "content": respuesta}
                    )
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

    if st.button("🗑️ Limpiar chat de este rol", key=f"limpiar_{rol_actual}"):
        st.session_state[chat_key] = [
            {"role": "assistant", "content": SALUDOS[rol_actual]}
        ]
        st.rerun()