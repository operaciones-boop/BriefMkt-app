import streamlit as st


# Configuración general
st.set_page_config(
    page_title="Brief de Marketing",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Barra lateral
with st.sidebar:
    st.header("Menú")
    st.write("Aplicación de Brief de Marketing")


# Contenido principal
st.title("📋 Brief de Marketing")

st.write(
    """
    Bienvenido a la nueva aplicación.

    Esta será nuestra base para construir el formulario,
    adjuntar imágenes y generar el brief.
    """
)

st.success("La aplicación está funcionando correctamente.")
