# ============================================================
# SISTEMA DE INVENTARIO DE COLECTORES
# ============================================================
#
# Este archivo contiene toda la lógica principal del sistema:
#
# 1. Inicia la aplicación Flask.
# 2. Controla el inicio y cierre de sesión.
# 3. Se conecta con Google Sheets.
# 4. Guarda colectores nuevos.
# 5. Evita números de serie duplicados.
# 6. Busca colectores por serie o usuario.
# 7. Filtra registros.
# 8. Permite editar un colector existente.
# 9. Genera los totales que aparecen en el resumen.
#
# El sistema trabaja con la hoja:
#   Archivo: Sistema de TI
#   Pestaña: COLECTOR
#
# Las columnas utilizadas son:
#   A = Item
#   B = Número de serie
#   C = Estado
#   D = Control de ubicación
#   E = Usuario asignado
#   F = Accesorio
#   G = Condición de reasignación
#   H = Condición del colector
#   I = Observación
# ============================================================


# ============================================================
# IMPORTAR LIBRERÍAS
# ============================================================

# os permite leer variables de entorno.
# En Render se utiliza para leer SECRET_KEY,
# ADMIN_USUARIO, ADMIN_PASSWORD, GOOGLE_CREDENTIALS y PORT.
import os

# json permite convertir el texto JSON guardado en Render
# en un diccionario de Python que pueda utilizar Google.
import json

# wraps conserva el nombre y la información original
# de una función cuando se utiliza un decorador.
from functools import wraps

# compare_digest compara textos de forma más segura.
# Se usa para validar el usuario y la contraseña.
from hmac import compare_digest

# Flask crea la aplicación web.
#
# render_template:
#   abre archivos HTML guardados en templates.
#
# request:
#   obtiene datos enviados desde formularios o desde la URL.
#
# redirect:
#   redirige al usuario hacia otra página.
#
# url_for:
#   genera la dirección de una ruta Flask usando su nombre.
#
# flash:
#   muestra mensajes temporales de éxito o error.
#
# session:
#   guarda información temporal del usuario conectado.
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session
)

# gspread permite leer, escribir y actualizar Google Sheets.
import gspread

# Credentials permite autenticar la cuenta de servicio de Google.
from google.oauth2.service_account import Credentials


# ============================================================
# CREAR LA APLICACIÓN FLASK
# ============================================================

# Se crea la aplicación web.
# __name__ indica a Flask en qué archivo se encuentra la aplicación.
app = Flask(__name__)

# La clave secreta protege las sesiones y los mensajes flash.
#
# En Render se obtiene de la variable SECRET_KEY.
# Si no existe, se utiliza el valor local de respaldo.
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "clave-local-sistema-colectores"
)


# ============================================================
# CONFIGURACIÓN DEL USUARIO Y CONTRASEÑA
# ============================================================

# Lee el usuario administrador desde Render.
# Si la variable ADMIN_USUARIO no existe,
# utiliza "administrador" para trabajar localmente.
USUARIO_ADMIN = os.environ.get(
    "ADMIN_USUARIO",
    "administrador"
)

# Lee la contraseña desde Render.
# Si ADMIN_PASSWORD no existe, usa el valor local.
#
# Es recomendable no dejar una contraseña real escrita aquí
# y utilizar siempre la variable de entorno en Render.
CONTRASENA_ADMIN = os.environ.get(
    "ADMIN_PASSWORD",
    "di6v6l6"
)


# ============================================================
# CONFIGURACIÓN DE GOOGLE SHEETS
# ============================================================

# SCOPES define los permisos que tendrá la cuenta de servicio.
SCOPES = [
    # Permite leer y modificar hojas de cálculo.
    "https://www.googleapis.com/auth/spreadsheets",

    # Permite encontrar y abrir el archivo desde Google Drive.
    "https://www.googleapis.com/auth/drive"
]

# Nombre del archivo JSON utilizado al ejecutar localmente.
ARCHIVO_CREDENCIALES = "credenciales.json"

# Nombre exacto del archivo de Google Sheets.
NOMBRE_ARCHIVO_GOOGLE = "Sistema de TI"

# Nombre exacto de la pestaña que contiene los colectores.
NOMBRE_HOJA = "COLECTOR"

# Los datos comienzan desde la fila 3.
# Las filas 1 y 2 se reservan para título y encabezados.
PRIMERA_FILA_DATOS = 3

# El sistema utiliza nueve columnas, desde A hasta I.
TOTAL_COLUMNAS = 9


# ============================================================
# FUNCIONES AUXILIARES+
# ============================================================

def normalizar_texto(valor):
    """
    Convierte cualquier valor a un texto limpio.

    Esta función sirve para comparar datos sin que afecten:

    - Las mayúsculas y minúsculas.
    - Los espacios al principio.
    - Los espacios al final.
    - Los valores vacíos o None.

    Ejemplos:

    " LOCALIZADO " -> "localizado"
    "Julio Benitez" -> "julio benitez"
    None -> ""
    """

    # valor or "" reemplaza None por texto vacío.
    # str convierte el valor a texto.
    # strip elimina espacios iniciales y finales.
    # casefold convierte el texto a minúsculas de forma segura.
    return str(valor or "").strip().casefold()


def preparar_fila(fila):
    """
    Garantiza que una fila siempre tenga nueve posiciones.

    Google Sheets puede devolver una fila más corta cuando
    las últimas celdas están vacías.

    Esta función agrega textos vacíos hasta completar nueve
    columnas y después limita el resultado a nueve elementos.
    """

    # Convierte la fila recibida en una lista.
    #
    # [""] * cantidad crea las celdas vacías necesarias.
    fila = list(fila) + [""] * (
        TOTAL_COLUMNAS - len(fila)
    )

    # Devuelve solamente las primeras nueve columnas.
    return fila[:TOTAL_COLUMNAS]


def obtener_datos_formulario():
    """
    Lee los datos enviados desde el formulario HTML.

    request.form contiene todos los campos enviados mediante POST.

    get("campo", ""):
        obtiene el campo y utiliza texto vacío si no fue enviado.

    strip():
        elimina espacios innecesarios al inicio y al final.

    La función devuelve un diccionario para que los mismos datos
    puedan utilizarse al guardar y al editar.
    """

    return {
        # Obtiene el número de item.
        "item": request.form.get(
            "item",
            ""
        ).strip(),

        # Obtiene el número de serie.
        "serie": request.form.get(
            "serie",
            ""
        ).strip(),

        # Obtiene el estado: localizado, no localizado, etc.
        "estado": request.form.get(
            "estado",
            ""
        ).strip(),

        # Obtiene la ubicación actual del colector.
        "ubicacion": request.form.get(
            "ubicacion",
            ""
        ).strip(),

        # Obtiene el nombre del usuario asignado.
        "usuario_asignado": request.form.get(
            "usuario_asignado",
            ""
        ).strip(),

        # Obtiene la información del cargador, base u otro accesorio.
        "accesorio": request.form.get(
            "accesorio",
            ""
        ).strip(),

        # Obtiene la condición de reasignación.
        "reasignacion": request.form.get(
            "reasignacion",
            ""
        ).strip(),

        # Obtiene la condición técnica del colector.
        "condicion": request.form.get(
            "condicion",
            ""
        ).strip(),

        # Obtiene la observación adicional.
        "observacion": request.form.get(
            "observacion",
            ""
        ).strip()
    }


def datos_a_fila(datos):
    """
    Convierte el diccionario del formulario en una lista.

    El orden de esta lista debe coincidir exactamente con las
    columnas A:I de Google Sheets.
    """

    return [
        # Columna A.
        datos["item"],

        # Columna B.
        datos["serie"],

        # Columna C.
        datos["estado"],

        # Columna D.
        datos["ubicacion"],

        # Columna E.
        datos["usuario_asignado"],

        # Columna F.
        datos["accesorio"],

        # Columna G.
        datos["reasignacion"],

        # Columna H.
        datos["condicion"],

        # Columna I.
        datos["observacion"]
    ]


def buscar_fila_por_serie(
    hoja,
    serie,
    excluir_fila=None
):
    """
    Busca un número de serie exacto en Google Sheets.

    Parámetros:

    hoja:
        pestaña de Google Sheets donde se realizará la búsqueda.

    serie:
        número de serie que se desea encontrar.

    excluir_fila:
        durante una edición, permite ignorar la misma fila
        que se está modificando.

    Retorna:

    - El número de fila si encuentra la serie.
    - None si la serie no existe.
    """

    # Limpia y normaliza la serie recibida.
    serie_normalizada = normalizar_texto(
        serie
    )

    # Si la serie está vacía, no se puede buscar.
    if not serie_normalizada:
        return None

    # Descarga todas las filas de la hoja.
    filas = hoja.get_all_values()

    # Recorre las filas desde la fila 3.
    #
    # filas[PRIMERA_FILA_DATOS - 1:]
    # comienza desde el índice 2, que corresponde a la fila 3.
    #
    # start=PRIMERA_FILA_DATOS hace que numero_fila empiece en 3.
    for numero_fila, fila in enumerate(
        filas[PRIMERA_FILA_DATOS - 1:],
        start=PRIMERA_FILA_DATOS
    ):

        # Durante una edición, ignora la fila actual.
        if (
            excluir_fila is not None
            and numero_fila == excluir_fila
        ):
            continue

        # Completa la fila hasta nueve columnas.
        fila = preparar_fila(
            fila
        )

        # La serie está guardada en la columna B,
        # que corresponde al índice 1.
        serie_guardada = normalizar_texto(
            fila[1]
        )

        # Compara la serie guardada con la buscada.
        if serie_guardada == serie_normalizada:
            return numero_fila

    # Si termina el recorrido sin encontrarla,
    # devuelve None.
    return None


def obtener_registros_inventario(hoja):
    """
    Lee todos los colectores guardados desde la fila 3.

    Cada fila se convierte en un diccionario con nombres claros,
    lo que facilita utilizar los datos en filtros, búsquedas,
    resultados y estadísticas.
    """

    # Descarga todas las filas de Google Sheets.
    filas = hoja.get_all_values()

    # Aquí se guardarán los registros válidos.
    registros = []

    # Recorre desde la fila 3.
    for numero_fila, fila in enumerate(
        filas[PRIMERA_FILA_DATOS - 1:],
        start=PRIMERA_FILA_DATOS
    ):

        # Completa la fila hasta nueve columnas.
        fila = preparar_fila(
            fila
        )

        # any devuelve True si existe al menos un dato.
        #
        # Si toda la fila está vacía, continue evita guardarla.
        if not any(
            str(valor).strip()
            for valor in fila
        ):
            continue

        # Convierte la fila en un diccionario.
        registros.append(
            {
                # Guarda el número real de fila para editar después.
                "fila": numero_fila,

                # Columna A.
                "item": fila[0],

                # Columna B.
                "serie": fila[1],

                # Columna C.
                "estado": fila[2],

                # Columna D.
                "ubicacion": fila[3],

                # Columna E.
                "usuario_asignado": fila[4],

                # Columna F.
                "accesorio": fila[5],

                # Columna G.
                "reasignacion": fila[6],

                # Columna H.
                "condicion": fila[7],

                # Columna I.
                "observacion": fila[8]
            }
        )

    # Devuelve la lista completa de colectores.
    return registros


def crear_resumen(registros):
    """
    Cuenta los estados y condiciones del inventario.

    Los resultados se muestran en las tarjetas superiores
    de colector.html.
    """

    # Crea todos los contadores con valor inicial 0.
    resumen = {
        # Cantidad total de registros.
        "total": len(registros),

        # Cantidad de colectores localizados.
        "localizados": 0,

        # Cantidad de colectores no localizados.
        "no_localizados": 0,

        # Cantidad de colectores extraviados.
        "extraviados": 0,

        # Cantidad de colectores con usuario.
        "con_usuario": 0,

        # Cantidad de colectores para reasignar.
        "reasignar": 0,

        # Cantidad de colectores operativos.
        "operativos": 0,

        # Cantidad de colectores en reparación o defectuosos.
        "reparacion_defectuosos": 0
    }

    # Recorre todos los colectores.
    for equipo in registros:

        # Normaliza los valores para compararlos.
        estado = normalizar_texto(
            equipo["estado"]
        )

        reasignacion = normalizar_texto(
            equipo["reasignacion"]
        )

        condicion = normalizar_texto(
            equipo["condicion"]
        )

        # Cuenta los estados.
        if estado == "localizado":
            resumen["localizados"] += 1

        elif estado == "no localizado":
            resumen["no_localizados"] += 1

        elif estado == "extraviado":
            resumen["extraviados"] += 1

        # Cuenta las condiciones de reasignación.
        if reasignacion == "con usuario":
            resumen["con_usuario"] += 1

        elif reasignacion == "reasignar":
            resumen["reasignar"] += 1

        # Cuenta los colectores operativos.
        if condicion == "operativo":
            resumen["operativos"] += 1

        # Cuenta como reparación o defectuoso cualquier condición
        # que contenga alguna de estas palabras.
        if (
            "reparacion" in condicion
            or "reparación" in condicion
            or "defectuoso" in condicion
            or "fuera de servicio" in condicion
        ):
            resumen[
                "reparacion_defectuosos"
            ] += 1

    # Devuelve todos los totales.
    return resumen


def crear_opciones_filtros(registros):
    """
    Obtiene valores únicos desde Google Sheets.

    Esta función permite generar opciones dinámicas para filtros,
    evitando repetir valores iguales.
    """

    def valores_unicos(campo):
        """
        Extrae valores únicos de un campo específico.
        """

        # Un set evita valores duplicados.
        valores = {
            str(equipo[campo]).strip()
            for equipo in registros
            if str(equipo[campo]).strip()
        }

        # Ordena alfabéticamente sin importar mayúsculas.
        return sorted(
            valores,
            key=lambda valor: valor.casefold()
        )

    # Devuelve las opciones agrupadas.
    return {
        "estados": valores_unicos(
            "estado"
        ),

        "ubicaciones": valores_unicos(
            "ubicacion"
        ),

        "reasignaciones": valores_unicos(
            "reasignacion"
        ),

        "condiciones": valores_unicos(
            "condicion"
        )
    }



def crear_resumen_ubicaciones(registros):
    """
    Agrupa los colectores por ubicación para mostrar las tarjetas
    superiores del panel, de forma similar al sistema de tablets.
    """
    conteo = {}

    for equipo in registros:
        ubicacion = str(equipo.get("ubicacion", "") or "").strip()

        if not ubicacion:
            ubicacion = "Sin ubicación"

        conteo[ubicacion] = conteo.get(ubicacion, 0) + 1

    # Ordena primero por mayor cantidad y luego por nombre.
    return sorted(
        [
            {
                "nombre": nombre,
                "cantidad": cantidad
            }
            for nombre, cantidad in conteo.items()
        ],
        key=lambda x: (-x["cantidad"], x["nombre"].casefold())
    )


def contexto_inventario(
    resultados=None,
    consulta="",
    filtros=None
):
    """
    Prepara todos los datos enviados a colector.html.

    Incluye:

    - resultados de búsqueda;
    - texto buscado;
    - filtros seleccionados;
    - resumen del inventario;
    - opciones disponibles;
    - nombre del usuario conectado.
    """

    # Si no se reciben filtros, crea filtros vacíos.
    filtros = filtros or {
        "estado": "",
        "ubicacion": "",
        "reasignacion": "",
        "condicion": ""
    }

    try:
        # Obtiene la hoja COLECTOR.
        hoja = obtener_hoja()

        # Lee todos los registros.
        registros = obtener_registros_inventario(
            hoja
        )

        # Devuelve el contexto que utilizará el HTML.
        return {
            "resultados": (
                resultados
                if resultados is not None
                else []
            ),

            "consulta": consulta,

            "filtros": filtros,

            "resumen": crear_resumen(
                registros
            ),

            "opciones": crear_opciones_filtros(
                registros
            ),

            # Todos los registros se muestran en la tabla principal.
            "registros": registros,

            # Resumen agrupado para las tarjetas "Colectores por ubicación".
            "resumen_ubicaciones": crear_resumen_ubicaciones(
                registros
            ),

            "nombre_usuario": session.get(
                "nombre_usuario"
            )
        }

    except Exception as error:
        # Muestra el error en los logs de Render o la terminal.
        print(
            "Error al cargar el resumen del inventario:",
            error
        )

        # Si ocurre un error, devuelve valores vacíos
        # para evitar que la página se detenga.
        return {
            "resultados": (
                resultados
                if resultados is not None
                else []
            ),

            "consulta": consulta,

            "filtros": filtros,

            "resumen": {
                "total": 0,
                "localizados": 0,
                "no_localizados": 0,
                "extraviados": 0,
                "con_usuario": 0,
                "reasignar": 0,
                "operativos": 0,
                "reparacion_defectuosos": 0
            },

            "opciones": {
                "estados": [],
                "ubicaciones": [],
                "reasignaciones": [],
                "condiciones": []
            },

            "registros": [],
            "resumen_ubicaciones": [],

            "nombre_usuario": session.get(
                "nombre_usuario"
            )
        }


# ============================================================
# OBTENER CREDENCIALES DE GOOGLE
# ============================================================

def obtener_credenciales():
    """
    Obtiene las credenciales según dónde se ejecute el sistema.

    En Render:
        utiliza la variable GOOGLE_CREDENTIALS.

    Localmente:
        utiliza el archivo credenciales.json.
    """

    # Lee las credenciales guardadas en Render.
    credenciales_render = os.environ.get(
        "GOOGLE_CREDENTIALS"
    )

    # Si existen credenciales en Render:
    if credenciales_render:

        # Convierte el texto JSON a diccionario.
        informacion = json.loads(
            credenciales_render
        )

        # Crea las credenciales usando el diccionario.
        return Credentials.from_service_account_info(
            informacion,
            scopes=SCOPES
        )

    # Si no se ejecuta en Render, utiliza el archivo local.
    return Credentials.from_service_account_file(
        ARCHIVO_CREDENCIALES,
        scopes=SCOPES
    )


# ============================================================
# CONECTAR CON GOOGLE SHEETS
# ============================================================

def obtener_hoja():
    """
    Autoriza la cuenta de servicio y abre la pestaña COLECTOR.
    """

    # Autoriza gspread usando las credenciales.
    cliente = gspread.authorize(
        obtener_credenciales()
    )

    # Abre el archivo "Sistema de TI".
    archivo = cliente.open(
        NOMBRE_ARCHIVO_GOOGLE
    )

    # Devuelve la pestaña "COLECTOR".
    return archivo.worksheet(
        NOMBRE_HOJA
    )


# ============================================================
# DECORADOR PARA PROTEGER RUTAS
# ============================================================

def login_requerido(funcion):
    """
    Protege una ruta para que solamente pueda ingresar
    un usuario autenticado.
    """

    # wraps conserva la información de la función original.
    @wraps(funcion)
    def ruta(*args, **kwargs):

        # Comprueba si la sesión tiene la marca de autenticación.
        if not session.get(
            "usuario_autenticado"
        ):

            # Muestra un mensaje.
            flash(
                "Debes iniciar sesión.",
                "error"
            )

            # Envía al usuario al login.
            return redirect(
                url_for("login")
            )

        # Si está autenticado, ejecuta la ruta original.
        return funcion(
            *args,
            **kwargs
        )

    # Devuelve la función protegida.
    return ruta


# ============================================================
# RUTA DE INICIO DE SESIÓN
# ============================================================

# La misma función responde tanto a "/" como a "/login".
# GET muestra el formulario.
# POST procesa el usuario y la contraseña.
@app.route(
    "/",
    methods=["GET", "POST"]
)
@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():
    """
    Muestra y procesa el formulario de inicio de sesión.
    """

    # Si ya existe una sesión válida,
    # envía directamente al sistema.
    if session.get(
        "usuario_autenticado"
    ):
        return redirect(
            url_for("inicio")
        )

    # Solo entra aquí cuando se envía el formulario.
    if request.method == "POST":

        # Obtiene el usuario escrito.
        usuario = request.form.get(
            "usuario",
            ""
        )

        # Obtiene la contraseña escrita.
        contrasena = request.form.get(
            "contrasena",
            ""
        )

        # Compara el usuario y la contraseña.
        if (
            compare_digest(
                usuario,
                USUARIO_ADMIN
            )
            and compare_digest(
                contrasena,
                CONTRASENA_ADMIN
            )
        ):

            # Elimina datos de sesiones anteriores.
            session.clear()

            # Marca al usuario como autenticado.
            session[
                "usuario_autenticado"
            ] = True

            # Guarda el nombre del usuario.
            session[
                "nombre_usuario"
            ] = usuario

            # Muestra mensaje de éxito.
            flash(
                "Inicio de sesión correcto.",
                "exito"
            )

            # Redirige a la página principal.
            return redirect(
                url_for("inicio")
            )

        # Se ejecuta si el usuario o la contraseña son incorrectos.
        flash(
            "Usuario o contraseña incorrectos.",
            "error"
        )

    # Muestra login.html.
    return render_template(
        "login.html"
    )


# ============================================================
# PÁGINA PRINCIPAL
# ============================================================

# Define la dirección /sistema.
@app.route("/sistema")

# Obliga a iniciar sesión antes de entrar.
@login_requerido
def inicio():
    """
    Muestra la pantalla principal del sistema.
    """

    # render_template abre colector.html.
    #
    # **contexto_inventario() distribuye todos los valores
    # del diccionario como variables independientes en el HTML.
    return render_template(
        "colector.html",
        **contexto_inventario()
    )


# ============================================================
# CERRAR SESIÓN
# ============================================================

@app.route("/logout")
@login_requerido
def logout():
    """
    Elimina la sesión actual y vuelve al login.
    """

    # Borra toda la información de la sesión.
    session.clear()

    # Muestra mensaje de confirmación.
    flash(
        "Sesión cerrada correctamente.",
        "exito"
    )

    # Regresa al inicio de sesión.
    return redirect(
        url_for("login")
    )


# ============================================================
# REGISTRAR UN COLECTOR NUEVO
# ============================================================

# GET:
#   abre el formulario.
#
# POST:
#   procesa y guarda el formulario.
@app.route(
    "/colector",
    methods=["GET", "POST"]
)
@login_requerido
def colector():
    """
    Registra un colector nuevo en Google Sheets.
    """

    # Si se ingresa directamente mediante GET,
    # solamente muestra la página.
    if request.method == "GET":
        return render_template(
            "colector.html",
            **contexto_inventario()
        )

    # Lee todos los campos enviados.
    datos = obtener_datos_formulario()

    # Extrae la serie porque es obligatoria
    # y se utiliza para buscar duplicados.
    serie = datos["serie"]

    # Impide guardar sin número de serie.
    if not serie:

        flash(
            "El número de serie es obligatorio.",
            "error"
        )

        return redirect(
            url_for("colector")
        )

    try:
        # Conecta con Google Sheets.
        hoja = obtener_hoja()

        # Busca si ya existe el mismo número de serie.
        fila_existente = buscar_fila_por_serie(
            hoja,
            serie
        )

        # Si existe, no inserta otro registro.
        if fila_existente:

            flash(
                "Este número de serie ya está registrado. "
                "Buscalo y utiliza el botón Editar para modificarlo.",
                "error"
            )

            # Lleva al usuario directamente al resultado existente.
            return redirect(
                url_for(
                    "buscar_colector",
                    consulta=serie
                )
            )

        # Agrega una fila nueva al final de la tabla.
        #
        # datos_a_fila ordena correctamente las nueve columnas.
        #
        # USER_ENTERED hace que Google interprete los valores
        # como si hubieran sido escritos manualmente.
        #
        # table_range indica que la tabla comienza en A3:I.
        hoja.append_row(
            datos_a_fila(
                datos
            ),
            value_input_option="USER_ENTERED",
            table_range="A3:I"
        )

        # Muestra mensaje de éxito.
        flash(
            "El colector se registró correctamente.",
            "exito"
        )

    except Exception as error:
        # Registra el error en la terminal o los logs.
        print(
            "Error al guardar en Google Sheets:",
            error
        )

        # Muestra un mensaje general al usuario.
        flash(
            "No se pudo guardar la información.",
            "error"
        )

    # Regresa al formulario.
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
@login_requerido
def buscar_colector():
    """
    Busca colectores por serie o usuario.

    También admite filtros de estado, ubicación,
    reasignación y condición.
    """

    # Obtiene el texto escrito en el buscador.
    consulta = request.args.get(
        "consulta",
        ""
    ).strip()

    # Obtiene los filtros enviados por la URL.
    filtros = {
        "estado": request.args.get(
            "estado",
            ""
        ).strip(),

        "ubicacion": request.args.get(
            "ubicacion",
            ""
        ).strip(),

        "reasignacion": request.args.get(
            "reasignacion",
            ""
        ).strip(),

        "condicion": request.args.get(
            "condicion",
            ""
        ).strip()
    }

    # Aquí se almacenarán las coincidencias.
    resultados = []

    try:
        # Se conecta con Google Sheets.
        hoja = obtener_hoja()

        # Obtiene todos los registros.
        registros = obtener_registros_inventario(
            hoja
        )

        # Normaliza la consulta.
        consulta_normalizada = normalizar_texto(
            consulta
        )

        # Recorre cada colector.
        for equipo in registros:

            # Normaliza la serie.
            serie_normalizada = normalizar_texto(
                equipo["serie"]
            )

            # Normaliza el usuario.
            usuario_normalizado = normalizar_texto(
                equipo["usuario_asignado"]
            )

            # Por defecto, considera que coincide.
            coincide_consulta = True

            # Si existe texto de búsqueda:
            if consulta_normalizada:

                # La serie solamente se busca cuando se escriben
                # seis o más caracteres.
                #
                # endswith permite buscar por los últimos caracteres.
                coincide_serie = (
                    len(
                        consulta_normalizada
                    ) >= 6
                    and serie_normalizada.endswith(
                        consulta_normalizada
                    )
                )

                # Para usuario, permite coincidencia parcial.
                coincide_usuario = (
                    consulta_normalizada
                    in usuario_normalizado
                )

                # Debe coincidir por serie o por usuario.
                coincide_consulta = (
                    coincide_serie
                    or coincide_usuario
                )

            # Comprueba el filtro Estado.
            coincide_estado = (
                not filtros["estado"]
                or normalizar_texto(
                    equipo["estado"]
                )
                == normalizar_texto(
                    filtros["estado"]
                )
            )

            # Comprueba el filtro Ubicación.
            coincide_ubicacion = (
                not filtros["ubicacion"]
                or normalizar_texto(
                    equipo["ubicacion"]
                )
                == normalizar_texto(
                    filtros["ubicacion"]
                )
            )

            # Comprueba el filtro Reasignación.
            coincide_reasignacion = (
                not filtros["reasignacion"]
                or normalizar_texto(
                    equipo["reasignacion"]
                )
                == normalizar_texto(
                    filtros["reasignacion"]
                )
            )

            # Comprueba el filtro Condición.
            coincide_condicion = (
                not filtros["condicion"]
                or normalizar_texto(
                    equipo["condicion"]
                )
                == normalizar_texto(
                    filtros["condicion"]
                )
            )

            # Solo agrega el registro si cumple
            # la búsqueda y todos los filtros.
            if (
                coincide_consulta
                and coincide_estado
                and coincide_ubicacion
                and coincide_reasignacion
                and coincide_condicion
            ):
                resultados.append(
                    equipo
                )

        # Prepara todos los datos para colector.html.
        contexto = {
            "resultados": resultados,
            "consulta": consulta,
            "filtros": filtros,
            "resumen": crear_resumen(
                registros
            ),
            "opciones": crear_opciones_filtros(
                registros
            ),
            "registros": registros,
            "resumen_ubicaciones": crear_resumen_ubicaciones(
                registros
            ),
            "nombre_usuario": session.get(
                "nombre_usuario"
            )
        }

    except Exception as error:
        # Registra el error.
        print(
            "Error al filtrar en Google Sheets:",
            error
        )

        # Informa al usuario.
        flash(
            "No se pudo realizar el filtro.",
            "error"
        )

        # Prepara un contexto vacío para que la página siga funcionando.
        contexto = contexto_inventario(
            resultados=[],
            consulta=consulta,
            filtros=filtros
        )

    # Muestra colector.html con los resultados.
    return render_template(
        "colector.html",
        **contexto
    )


# ============================================================
# EDITAR UN COLECTOR EXISTENTE
# ============================================================

@app.route(
    "/editar-colector",
    methods=["POST"]
)
@login_requerido
def editar_colector():
    """
    Actualiza un registro existente sin agregar una fila nueva.
    """

    # Obtiene el número de fila enviado desde el formulario.
    fila_texto = request.form.get(
        "fila",
        ""
    ).strip()

    # Conserva la consulta anterior.
    consulta = request.form.get(
        "consulta",
        ""
    ).strip()

    # Guarda la serie original para verificar que la fila
    # no haya cambiado mientras se estaba editando.
    serie_original = request.form.get(
        "serie_original",
        ""
    ).strip()

    # Lee todos los datos editados.
    datos = obtener_datos_formulario()

    # Obtiene la nueva serie.
    serie = datos["serie"]

    # Comprueba que la fila sea un número.
    if not fila_texto.isdigit():

        flash(
            "La fila seleccionada no es válida.",
            "error"
        )

        return redirect(
            url_for(
                "buscar_colector",
                consulta=consulta
            )
        )

    # Convierte el número de fila de texto a entero.
    numero_fila = int(
        fila_texto
    )

    # Impide modificar las filas 1 y 2.
    if numero_fila < PRIMERA_FILA_DATOS:

        flash(
            "No se puede modificar una fila de encabezado.",
            "error"
        )

        return redirect(
            url_for(
                "buscar_colector",
                consulta=consulta
            )
        )

    # Impide dejar la serie vacía.
    if not serie:

        flash(
            "El número de serie es obligatorio.",
            "error"
        )

        return redirect(
            url_for(
                "buscar_colector",
                consulta=consulta
            )
        )

    try:
        # Obtiene la hoja.
        hoja = obtener_hoja()

        # Lee la fila que se desea modificar.
        fila_actual = preparar_fila(
            hoja.row_values(
                numero_fila
            )
        )

        # Comprueba que la fila todavía exista.
        if not any(
            fila_actual
        ):

            flash(
                "El registro ya no existe en Google Sheets.",
                "error"
            )

            return redirect(
                url_for(
                    "buscar_colector",
                    consulta=consulta
                )
            )

        # La serie está en la segunda columna.
        serie_actual_hoja = fila_actual[1]

        # Comprueba que el registro no haya cambiado
        # desde que se abrió para edición.
        if (
            serie_original
            and normalizar_texto(
                serie_actual_hoja
            )
            != normalizar_texto(
                serie_original
            )
        ):

            flash(
                "El registro cambió mientras lo estabas editando. "
                "Realiza nuevamente la búsqueda.",
                "error"
            )

            return redirect(
                url_for(
                    "buscar_colector",
                    consulta=(
                        consulta
                        or serie_original
                    )
                )
            )

        # Busca si la nueva serie pertenece a otro colector.
        #
        # excluir_fila evita comparar con el mismo registro.
        fila_duplicada = buscar_fila_por_serie(
            hoja,
            serie,
            excluir_fila=numero_fila
        )

        # Si existe en otra fila, cancela la actualización.
        if fila_duplicada:

            flash(
                "No se pudo actualizar: el número de serie "
                "ya pertenece a otro colector.",
                "error"
            )

            return redirect(
                url_for(
                    "buscar_colector",
                    consulta=(
                        consulta
                        or serie
                    )
                )
            )

        # Actualiza exactamente las columnas A:I
        # de la misma fila.
        #
        # No agrega una fila nueva.
        hoja.update(
            range_name=(
                f"A{numero_fila}:I{numero_fila}"
            ),
            values=[
                datos_a_fila(
                    datos
                )
            ],
            value_input_option="USER_ENTERED"
        )

        # Informa que la edición fue exitosa.
        flash(
            "Los datos del colector se actualizaron correctamente.",
            "exito"
        )

    except Exception as error:
        # Muestra el error técnico en los logs.
        print(
            "Error al actualizar Google Sheets:",
            error
        )

        # Muestra un mensaje amigable al usuario.
        flash(
            "No se pudieron guardar los cambios.",
            "error"
        )

    # Después de actualizar, vuelve a buscar el registro.
    #
    # Si la serie tiene seis o más caracteres,
    # utiliza sus últimos seis.
    return redirect(
        url_for(
            "buscar_colector",
            consulta=(
                serie[-6:]
                if len(serie) >= 6
                else serie
            )
        )
    )



# ============================================================
# ELIMINAR UN COLECTOR
# ============================================================

@app.route(
    "/eliminar-colector",
    methods=["POST"]
)
@login_requerido
def eliminar_colector():
    """
    Elimina de Google Sheets el registro seleccionado desde la tabla.
    Antes de borrar valida la fila y, si se envía, la serie original.
    """
    fila_texto = request.form.get("fila", "").strip()
    serie_original = request.form.get("serie_original", "").strip()

    if not fila_texto.isdigit():
        flash("No se pudo identificar el colector a eliminar.", "error")
        return redirect(url_for("inicio"))

    numero_fila = int(fila_texto)

    if numero_fila < PRIMERA_FILA_DATOS:
        flash("No se puede eliminar una fila de encabezado.", "error")
        return redirect(url_for("inicio"))

    try:
        hoja = obtener_hoja()
        fila_actual = preparar_fila(hoja.row_values(numero_fila))

        if not any(fila_actual):
            flash("El registro ya no existe en Google Sheets.", "error")
            return redirect(url_for("inicio"))

        if (
            serie_original
            and normalizar_texto(fila_actual[1])
            != normalizar_texto(serie_original)
        ):
            flash(
                "El registro cambió antes de eliminarse. Actualiza la página e intenta nuevamente.",
                "error"
            )
            return redirect(url_for("inicio"))

        hoja.delete_rows(numero_fila)

        flash("El colector se eliminó correctamente.", "exito")

    except Exception as error:
        print("Error al eliminar colector:", error)
        flash("No se pudo eliminar el colector.", "error")

    return redirect(url_for("inicio"))



# ============================================================
# INICIAR EL SERVIDOR
# ============================================================

# Este bloque solamente se ejecuta cuando se abre el archivo
# directamente con:
#
# py app.py
#
# Render no utiliza esta línea directamente;
# Render normalmente ejecuta:
#
# gunicorn app:app
if __name__ == "__main__":

    # Inicia el servidor Flask.
    app.run(
        # 0.0.0.0 permite aceptar conexiones externas.
        host="0.0.0.0",

        # En Render utiliza la variable PORT.
        # Localmente utiliza el puerto 5000.
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),

        # Activa debug solo si FLASK_DEBUG tiene el valor "true".
        #
        # En producción debe permanecer desactivado.
        debug=os.environ.get(
            "FLASK_DEBUG",
            "false"
        ).lower() == "true"
    )