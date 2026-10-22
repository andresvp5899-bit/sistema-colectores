# ============================================================
# SISTEMA DE INVENTARIO DE COLECTORES
# ACCESO DIRECTO SIN INICIO DE SESIÓN
# GOOGLE SHEETS: COLUMNAS A HASTA G
# ============================================================

import os
import json
import logging
import unicodedata

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash
)

import gspread
from google.oauth2.service_account import Credentials


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "clave-local-sistema-colectores"
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURACIÓN DE GOOGLE SHEETS
# ============================================================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

ARCHIVO_CREDENCIALES = "credenciales.json"

NOMBRE_ARCHIVO_GOOGLE = "Sistema de TI"
NOMBRE_HOJA = "COLECTOR"

# Fila 1: encabezados
# Fila 2 en adelante: registros
PRIMERA_FILA_DATOS = 2

# Estructura definitiva: A hasta G
TOTAL_COLUMNAS = 7

# A = Número de serie
# B = Estado
# C = Control de ubicación
# D = Usuario asignado
# E = Accesorio
# F = Condición del colector
# G = Observación

COLUMNAS = [
    "serie",
    "estado",
    "ubicacion",
    "usuario_asignado",
    "accesorio",
    "condicion",
    "observacion"
]


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def normalizar_texto(valor):
    """
    Permite comparar textos sin importar
    mayúsculas, minúsculas ni espacios.
    """
    return str(valor or "").strip().casefold()


def normalizar_busqueda(valor):
    """
    Normaliza textos para búsquedas,
    incluyendo palabras con acentos.
    """
    texto = normalizar_texto(valor)

    texto = unicodedata.normalize(
        "NFKD",
        texto
    )

    return "".join(
        caracter
        for caracter in texto
        if not unicodedata.combining(caracter)
    )


def preparar_fila(fila):
    """
    Completa las posiciones faltantes para
    trabajar siempre con siete columnas.
    """
    fila = list(fila)

    if len(fila) < TOTAL_COLUMNAS:
        fila.extend(
            [""] * (TOTAL_COLUMNAS - len(fila))
        )

    return fila[:TOTAL_COLUMNAS]


def obtener_datos_formulario():
    """
    Obtiene los siete campos enviados
    desde el formulario HTML.
    """
    return {
        "serie": request.form.get(
            "serie", ""
        ).strip(),

        "estado": request.form.get(
            "estado", ""
        ).strip(),

        "ubicacion": request.form.get(
            "ubicacion", ""
        ).strip(),

        "usuario_asignado": request.form.get(
            "usuario_asignado", ""
        ).strip(),

        "accesorio": request.form.get(
            "accesorio", ""
        ).strip(),

        "condicion": request.form.get(
            "condicion", ""
        ).strip(),

        "observacion": request.form.get(
            "observacion", ""
        ).strip()
    }


def datos_a_fila(datos):
    """
    Organiza los valores exactamente
    en el orden de Google Sheets: A:G.
    """
    return [
        datos["serie"],
        datos["estado"],
        datos["ubicacion"],
        datos["usuario_asignado"],
        datos["accesorio"],
        datos["condicion"],
        datos["observacion"]
    ]


def fila_a_registro(numero_fila, fila):
    """
    Convierte una fila de Google Sheets
    en un registro para la página HTML.
    """
    fila = preparar_fila(fila)

    return {
        "fila": numero_fila,
        "serie": fila[0],
        "estado": fila[1],
        "ubicacion": fila[2],
        "usuario_asignado": fila[3],
        "accesorio": fila[4],
        "condicion": fila[5],
        "observacion": fila[6]
    }


# ============================================================
# CONEXIÓN CON GOOGLE SHEETS
# ============================================================

def obtener_credenciales():
    """
    En Render utiliza GOOGLE_CREDENTIALS.

    En la computadora utiliza
    el archivo credenciales.json.
    """
    credenciales_render = os.environ.get(
        "GOOGLE_CREDENTIALS"
    )

    if credenciales_render:

        informacion = json.loads(
            credenciales_render
        )

        return Credentials.from_service_account_info(
            informacion,
            scopes=SCOPES
        )

    return Credentials.from_service_account_file(
        ARCHIVO_CREDENCIALES,
        scopes=SCOPES
    )


def obtener_hoja():
    """
    Abre el archivo Sistema de TI
    y la pestaña COLECTOR.
    """
    cliente = gspread.authorize(
        obtener_credenciales()
    )

    archivo = cliente.open(
        NOMBRE_ARCHIVO_GOOGLE
    )

    return archivo.worksheet(
        NOMBRE_HOJA
    )


# ============================================================
# BUSCAR NÚMERO DE SERIE DUPLICADO
# ============================================================

def buscar_fila_por_serie(
    hoja,
    serie,
    excluir_fila=None
):
    """
    Busca un número de serie en la columna A.

    Durante una edición permite excluir
    la fila que se está modificando.
    """
    serie_normalizada = normalizar_texto(
        serie
    )

    if not serie_normalizada:
        return None

    filas = hoja.get_all_values()

    for numero_fila, fila in enumerate(
        filas[PRIMERA_FILA_DATOS - 1:],
        start=PRIMERA_FILA_DATOS
    ):

        if (
            excluir_fila is not None
            and numero_fila == excluir_fila
        ):
            continue

        fila = preparar_fila(fila)

        # Columna A: número de serie
        serie_guardada = normalizar_texto(
            fila[0]
        )

        if serie_guardada == serie_normalizada:
            return numero_fila

    return None


# ============================================================
# OBTENER TODOS LOS REGISTROS
# ============================================================

def obtener_registros_inventario(hoja):
    """
    Lee las columnas A:G desde la fila 2.

    Conserva el número real de fila
    para editar o eliminar correctamente.
    """
    filas = hoja.get_all_values()

    registros = []

    for numero_fila, fila in enumerate(
        filas[PRIMERA_FILA_DATOS - 1:],
        start=PRIMERA_FILA_DATOS
    ):

        fila = preparar_fila(fila)

        if not any(
            str(valor).strip()
            for valor in fila
        ):
            continue

        registros.append(
            fila_a_registro(
                numero_fila,
                fila
            )
        )

    return registros


# ============================================================
# RESUMEN GENERAL DEL INVENTARIO
# ============================================================

def crear_resumen(registros):
    """
    Calcula los totales del inventario.
    """
    resumen = {
        "total": len(registros),
        "localizados": 0,
        "no_localizados": 0,
        "extraviados": 0,
        "con_usuario": 0,
        "operativos": 0,
        "reparacion_defectuosos": 0
    }

    for equipo in registros:

        estado = normalizar_busqueda(
            equipo["estado"]
        )

        condicion = normalizar_busqueda(
            equipo["condicion"]
        )

        usuario = normalizar_texto(
            equipo["usuario_asignado"]
        )

        if estado == "localizado":
            resumen["localizados"] += 1

        elif estado == "no localizado":
            resumen["no_localizados"] += 1

        elif estado == "extraviado":
            resumen["extraviados"] += 1

        if usuario:
            resumen["con_usuario"] += 1

        if condicion == "operativo":
            resumen["operativos"] += 1

        if any(
            palabra in condicion
            for palabra in (
                "reparacion",
                "defectuoso",
                "fuera de servicio"
            )
        ):
            resumen["reparacion_defectuosos"] += 1

    return resumen


# ============================================================
# OPCIONES DINÁMICAS DE FILTROS
# ============================================================

def crear_opciones_filtros(registros):
    """
    Obtiene las opciones existentes
    directamente desde Google Sheets.
    """

    def valores_unicos(campo):

        valores = {
            str(
                equipo.get(campo, "")
            ).strip()
            for equipo in registros
            if str(
                equipo.get(campo, "")
            ).strip()
        }

        return sorted(
            valores,
            key=lambda valor: valor.casefold()
        )

    return {
        "estados": valores_unicos("estado"),
        "ubicaciones": valores_unicos("ubicacion"),
        "usuarios": valores_unicos("usuario_asignado"),
        "accesorios": valores_unicos("accesorio"),
        "condiciones": valores_unicos("condicion")
    }


# ============================================================
# RESUMEN POR UBICACIÓN
# ============================================================

def crear_resumen_ubicaciones(registros):
    """
    Agrupa los colectores por ubicación
    o departamento.
    """
    conteo = {}

    for equipo in registros:

        ubicacion = str(
            equipo.get("ubicacion", "") or ""
        ).strip()

        if not ubicacion:
            ubicacion = "Sin ubicación"

        conteo[ubicacion] = (
            conteo.get(ubicacion, 0) + 1
        )

    return sorted(
        [
            {
                "nombre": nombre,
                "cantidad": cantidad
            }
            for nombre, cantidad in conteo.items()
        ],
        key=lambda x: (
            -x["cantidad"],
            x["nombre"].casefold()
        )
    )


# ============================================================
# FILTRAR REGISTROS
# ============================================================

def filtrar_registros(
    registros,
    consulta="",
    filtros=None
):
    """
    Permite buscar por serie, usuario,
    ubicación, estado, accesorio,
    condición u observación.
    """
    filtros = filtros or {}

    consulta_normalizada = normalizar_busqueda(
        consulta
    )

    resultados = []

    for equipo in registros:

        coincide_consulta = True

        if consulta_normalizada:

            campos_busqueda = (
                "serie",
                "usuario_asignado",
                "ubicacion",
                "estado",
                "accesorio",
                "condicion",
                "observacion"
            )

            coincide_consulta = any(
                consulta_normalizada
                in normalizar_busqueda(
                    equipo.get(campo, "")
                )
                for campo in campos_busqueda
            )

        coincide_filtros = True

        for campo in (
            "estado",
            "ubicacion",
            "condicion"
        ):

            valor_filtro = normalizar_busqueda(
                filtros.get(campo, "")
            )

            if (
                valor_filtro
                and normalizar_busqueda(
                    equipo.get(campo, "")
                ) != valor_filtro
            ):
                coincide_filtros = False
                break

        if coincide_consulta and coincide_filtros:
            resultados.append(equipo)

    return resultados


# ============================================================
# CONTEXTO PARA LA PÁGINA PRINCIPAL
# ============================================================

def contexto_inventario(
    consulta="",
    filtros=None
):
    """
    Prepara todos los datos utilizados
    por templates/colector.html.
    """
    filtros = filtros or {
        "estado": "",
        "ubicacion": "",
        "condicion": ""
    }

    try:

        hoja = obtener_hoja()

        registros = obtener_registros_inventario(
            hoja
        )

        resultados = filtrar_registros(
            registros,
            consulta,
            filtros
        )

        return {
            "resultados": resultados,
            "consulta": consulta,
            "filtros": filtros,
            "resumen": crear_resumen(registros),
            "opciones": crear_opciones_filtros(
                registros
            ),
            "registros": resultados,
            "resumen_ubicaciones": crear_resumen_ubicaciones(
                registros
            ),
            "nombre_usuario": ""
        }

    except Exception:

        logger.exception(
            "Error al cargar el inventario"
        )

        flash(
            "No se pudo cargar la información "
            "de Google Sheets.",
            "error"
        )

        return {
            "resultados": [],
            "consulta": consulta,
            "filtros": filtros,
            "resumen": {
                "total": 0,
                "localizados": 0,
                "no_localizados": 0,
                "extraviados": 0,
                "con_usuario": 0,
                "operativos": 0,
                "reparacion_defectuosos": 0
            },
            "opciones": {
                "estados": [],
                "ubicaciones": [],
                "usuarios": [],
                "accesorios": [],
                "condiciones": []
            },
            "registros": [],
            "resumen_ubicaciones": [],
            "nombre_usuario": ""
        }


# ============================================================
# ACCESO DIRECTO SIN LOGIN
# ============================================================

@app.route("/")
def pagina_principal():
    """
    Abre directamente el inventario.
    """
    return redirect(
        url_for("inicio")
    )


@app.route("/login")
def login_anterior():
    """
    Redirige las direcciones antiguas
    de inicio de sesión.
    """
    return redirect(
        url_for("inicio")
    )


@app.route("/sistema")
def inicio():
    """
    Muestra el inventario sin contraseña.
    """
    return render_template(
        "colector.html",
        **contexto_inventario()
    )


# ============================================================
# REGISTRAR UN COLECTOR NUEVO
# ============================================================

@app.route(
    "/colector",
    methods=["GET", "POST"]
)
def colector():
    """
    Registra un colector en las columnas A:G.
    """

    if request.method == "GET":

        return render_template(
            "colector.html",
            **contexto_inventario()
        )

    datos = obtener_datos_formulario()

    serie = datos["serie"]

    if not serie:

        flash(
            "El número de serie es obligatorio.",
            "error"
        )

        return redirect(
            url_for("colector")
        )

    try:

        hoja = obtener_hoja()

        fila_existente = buscar_fila_por_serie(
            hoja,
            serie
        )

        if fila_existente:

            flash(
                "Este número de serie ya está "
                "registrado. Buscalo y utilizá "
                "Editar para modificarlo.",
                "error"
            )

            return redirect(
                url_for(
                    "buscar_colector",
                    consulta=serie
                )
            )

        # Guardar exactamente siete columnas.
        # RAW evita alterar números de serie.
        hoja.append_row(
            datos_a_fila(datos),
            value_input_option="RAW",
            table_range="A1:G"
        )

        flash(
            "El colector se registró correctamente.",
            "exito"
        )

    except Exception:

        logger.exception(
            "Error al registrar el colector"
        )

        flash(
            "No se pudo guardar la información.",
            "error"
        )

    return redirect(
        url_for("colector")
    )


# ============================================================
# BUSCAR Y FILTRAR COLECTORES
# ============================================================

@app.route(
    "/buscar",
    methods=["GET"]
)
def buscar_colector():
    """
    Busca y filtra los registros
    sin modificar Google Sheets.
    """

    consulta = request.args.get(
        "consulta", ""
    ).strip()

    filtros = {
        "estado": request.args.get(
            "estado", ""
        ).strip(),

        "ubicacion": request.args.get(
            "ubicacion", ""
        ).strip(),

        "condicion": request.args.get(
            "condicion", ""
        ).strip()
    }

    return render_template(
        "colector.html",
        **contexto_inventario(
            consulta=consulta,
            filtros=filtros
        )
    )


# ============================================================
# EDITAR UN COLECTOR
# ============================================================

@app.route(
    "/editar-colector",
    methods=["POST"]
)
def editar_colector():
    """
    Actualiza las columnas A:G
    sin crear una fila nueva.
    """

    fila_texto = request.form.get(
        "fila", ""
    ).strip()

    serie_original = request.form.get(
        "serie_original", ""
    ).strip()

    datos = obtener_datos_formulario()

    serie = datos["serie"]

    if not fila_texto.isdigit():

        flash(
            "La fila seleccionada no es válida.",
            "error"
        )

        return redirect(
            url_for("inicio")
        )

    numero_fila = int(fila_texto)

    if numero_fila < PRIMERA_FILA_DATOS:

        flash(
            "No se puede modificar "
            "una fila de encabezado.",
            "error"
        )

        return redirect(
            url_for("inicio")
        )

    if not serie:

        flash(
            "El número de serie es obligatorio.",
            "error"
        )

        return redirect(
            url_for("inicio")
        )

    if not serie_original:

        flash(
            "No se pudo verificar el registro "
            "original. Actualizá la página.",
            "error"
        )

        return redirect(
            url_for("inicio")
        )

    try:

        hoja = obtener_hoja()

        fila_actual = preparar_fila(
            hoja.row_values(numero_fila)
        )

        if not any(fila_actual):

            flash(
                "El registro ya no existe "
                "en Google Sheets.",
                "error"
            )

            return redirect(
                url_for("inicio")
            )

        # La serie está en la columna A.
        serie_actual_hoja = fila_actual[0]

        if (
            normalizar_texto(serie_actual_hoja)
            != normalizar_texto(serie_original)
        ):

            flash(
                "El registro cambió mientras "
                "lo estabas editando. "
                "Actualizá la página.",
                "error"
            )

            return redirect(
                url_for("inicio")
            )

        fila_duplicada = buscar_fila_por_serie(
            hoja,
            serie,
            excluir_fila=numero_fila
        )

        if fila_duplicada:

            flash(
                "No se pudo actualizar porque "
                "el número de serie ya pertenece "
                "a otro colector.",
                "error"
            )

            return redirect(
                url_for(
                    "buscar_colector",
                    consulta=serie
                )
            )

        # Actualiza solo A:G.
        hoja.update(
            range_name=(
                f"A{numero_fila}:G{numero_fila}"
            ),
            values=[
                datos_a_fila(datos)
            ],
            value_input_option="RAW"
        )

        flash(
            "Los datos del colector se "
            "actualizaron correctamente.",
            "exito"
        )

    except Exception:

        logger.exception(
            "Error al actualizar el colector"
        )

        flash(
            "No se pudieron guardar los cambios.",
            "error"
        )

    # Volver al inventario completo después de editar.
    # Los 254 registros siguen disponibles; no filtrar por serie.
    return redirect(url_for("inicio"))


# ============================================================
# ELIMINAR UN COLECTOR
# ============================================================

@app.route(
    "/eliminar-colector",
    methods=["POST"]
)
def eliminar_colector():
    """
    Elimina la fila del colector
    después de verificar su número de serie.
    """

    fila_texto = request.form.get(
        "fila", ""
    ).strip()

    serie_original = request.form.get(
        "serie_original", ""
    ).strip()

    if not fila_texto.isdigit():

        flash(
            "No se pudo identificar "
            "el colector a eliminar.",
            "error"
        )

        return redirect(
            url_for("inicio")
        )

    numero_fila = int(fila_texto)

    if numero_fila < PRIMERA_FILA_DATOS:

        flash(
            "No se puede eliminar "
            "una fila de encabezado.",
            "error"
        )

        return redirect(
            url_for("inicio")
        )

    if not serie_original:

        flash(
            "No se pudo verificar el "
            "colector original. "
            "Actualizá la página.",
            "error"
        )

        return redirect(
            url_for("inicio")
        )

    try:

        hoja = obtener_hoja()

        fila_actual = preparar_fila(
            hoja.row_values(numero_fila)
        )

        if not any(fila_actual):

            flash(
                "El registro ya no existe "
                "en Google Sheets.",
                "error"
            )

            return redirect(
                url_for("inicio")
            )

        # Verifica la serie de la columna A.
        if (
            normalizar_texto(fila_actual[0])
            != normalizar_texto(serie_original)
        ):

            flash(
                "El registro cambió antes "
                "de eliminarse. "
                "Actualizá la página.",
                "error"
            )

            return redirect(
                url_for("inicio")
            )

        hoja.delete_rows(
            numero_fila
        )

        flash(
            "El colector se eliminó correctamente.",
            "exito"
        )

    except Exception:

        logger.exception(
            "Error al eliminar el colector"
        )

        flash(
            "No se pudo eliminar el colector.",
            "error"
        )

    return redirect(
        url_for("inicio")
    )


# ============================================================
# INICIAR EL SERVIDOR
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",

        port=int(
            os.environ.get("PORT", 5000)
        ),

        debug=(
            os.environ.get(
                "FLASK_DEBUG",
                "false"
            ).lower() == "true"
        )
    )
