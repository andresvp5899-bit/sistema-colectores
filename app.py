# ==========================================
# IMPORTAR LIBRERÍAS
# ==========================================

import os
import json

from functools import wraps
from hmac import compare_digest

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session
)

import gspread
from google.oauth2.service_account import Credentials


# ==========================================
# CREAR LA APLICACIÓN
# ==========================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "clave-local-sistema-colectores"
)


# ==========================================
# USUARIO Y CONTRASEÑA
# ==========================================

USUARIO_ADMIN = os.environ.get(
    "ADMIN_USUARIO",
    "administrador"
)

CONTRASENA_ADMIN = os.environ.get(
    "ADMIN_PASSWORD",
    "123456"
)


# ==========================================
# GOOGLE SHEETS
# ==========================================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

ARCHIVO_CREDENCIALES = "credenciales.json"
NOMBRE_ARCHIVO_GOOGLE = "Sistema de TI"
NOMBRE_HOJA = "COLECTOR"

PRIMERA_FILA_DATOS = 3
TOTAL_COLUMNAS = 9


# ==========================================
# FUNCIONES AUXILIARES
# ==========================================

def normalizar_texto(valor):
    """Convierte un valor a texto limpio para realizar comparaciones."""
    return str(valor or "").strip().casefold()


def preparar_fila(fila):
    """Completa una fila hasta las 9 columnas utilizadas por el sistema."""
    fila = list(fila) + [""] * (TOTAL_COLUMNAS - len(fila))
    return fila[:TOTAL_COLUMNAS]


def obtener_datos_formulario():
    """Obtiene y limpia los campos comunes del formulario."""
    return {
        "item": request.form.get("item", "").strip(),
        "serie": request.form.get("serie", "").strip(),
        "estado": request.form.get("estado", "").strip(),
        "ubicacion": request.form.get("ubicacion", "").strip(),
        "usuario_asignado": request.form.get(
            "usuario_asignado",
            ""
        ).strip(),
        "accesorio": request.form.get("accesorio", "").strip(),
        "reasignacion": request.form.get(
            "reasignacion",
            ""
        ).strip(),
        "condicion": request.form.get("condicion", "").strip(),
        "observacion": request.form.get(
            "observacion",
            ""
        ).strip()
    }


def datos_a_fila(datos):
    """Convierte los datos del formulario al orden de columnas A:I."""
    return [
        datos["item"],
        datos["serie"],
        datos["estado"],
        datos["ubicacion"],
        datos["usuario_asignado"],
        datos["accesorio"],
        datos["reasignacion"],
        datos["condicion"],
        datos["observacion"]
    ]


def buscar_fila_por_serie(hoja, serie, excluir_fila=None):
    """
    Busca una serie exacta en la columna B.

    excluir_fila se utiliza durante la edición para que el registro
    que se está modificando no sea considerado un duplicado.
    """
    serie_normalizada = normalizar_texto(serie)

    if not serie_normalizada:
        return None

    filas = hoja.get_all_values()

    for numero_fila, fila in enumerate(
        filas[PRIMERA_FILA_DATOS - 1:],
        start=PRIMERA_FILA_DATOS
    ):
        if excluir_fila is not None and numero_fila == excluir_fila:
            continue

        fila = preparar_fila(fila)
        serie_guardada = normalizar_texto(fila[1])

        if serie_guardada == serie_normalizada:
            return numero_fila

    return None


# ==========================================
# CREDENCIALES
# ==========================================

def obtener_credenciales():
    credenciales_render = os.environ.get("GOOGLE_CREDENTIALS")

    if credenciales_render:
        return Credentials.from_service_account_info(
            json.loads(credenciales_render),
            scopes=SCOPES
        )

    return Credentials.from_service_account_file(
        ARCHIVO_CREDENCIALES,
        scopes=SCOPES
    )


# ==========================================
# CONECTAR A GOOGLE SHEETS
# ==========================================

def obtener_hoja():
    cliente = gspread.authorize(obtener_credenciales())
    archivo = cliente.open(NOMBRE_ARCHIVO_GOOGLE)
    return archivo.worksheet(NOMBRE_HOJA)


# ==========================================
# LOGIN REQUERIDO
# ==========================================

def login_requerido(funcion):

    @wraps(funcion)
    def ruta(*args, **kwargs):

        if not session.get("usuario_autenticado"):
            flash("Debes iniciar sesión.", "error")
            return redirect(url_for("login"))

        return funcion(*args, **kwargs)

    return ruta


# ==========================================
# LOGIN
# ==========================================

@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():

    if session.get("usuario_autenticado"):
        return redirect(url_for("inicio"))

    if request.method == "POST":
        usuario = request.form.get("usuario", "")
        contrasena = request.form.get("contrasena", "")

        if (
            compare_digest(usuario, USUARIO_ADMIN)
            and compare_digest(contrasena, CONTRASENA_ADMIN)
        ):
            session.clear()
            session["usuario_autenticado"] = True
            session["nombre_usuario"] = usuario

            flash("Inicio de sesión correcto.", "exito")
            return redirect(url_for("inicio"))

        flash("Usuario o contraseña incorrectos.", "error")

    return render_template("login.html")


# ==========================================
# INICIO
# ==========================================

@app.route("/sistema")
@login_requerido
def inicio():

    return render_template(
        "colector.html",
        resultados=[],
        consulta="",
        nombre_usuario=session.get("nombre_usuario")
    )


# ==========================================
# CERRAR SESIÓN
# ==========================================

@app.route("/logout")
@login_requerido
def logout():

    session.clear()
    flash("Sesión cerrada correctamente.", "exito")
    return redirect(url_for("login"))


# ==========================================
# REGISTRAR COLECTOR NUEVO
# ==========================================

@app.route("/colector", methods=["GET", "POST"])
@login_requerido
def colector():

    if request.method == "GET":
        return render_template(
            "colector.html",
            resultados=[],
            consulta="",
            nombre_usuario=session.get("nombre_usuario")
        )

    datos = obtener_datos_formulario()
    serie = datos["serie"]

    if not serie:
        flash("El número de serie es obligatorio.", "error")
        return redirect(url_for("colector"))

    try:
        hoja = obtener_hoja()

        # Evita registrar dos veces el mismo número de serie.
        fila_existente = buscar_fila_por_serie(hoja, serie)

        if fila_existente:
            flash(
                "Este número de serie ya está registrado. "
                "Buscalo y utiliza el botón Editar para modificarlo.",
                "error"
            )

            return redirect(
                url_for(
                    "buscar_colector",
                    consulta=serie
                )
            )

        hoja.append_row(
            datos_a_fila(datos),
            value_input_option="USER_ENTERED",
            table_range="A3:I"
        )

        flash(
            "El colector se registró correctamente.",
            "exito"
        )

    except Exception as error:
        print("Error al guardar en Google Sheets:", error)

        flash(
            "No se pudo guardar la información.",
            "error"
        )

    return redirect(url_for("colector"))


# ==========================================
# BUSCAR COLECTORES
# ==========================================

@app.route("/buscar", methods=["GET"])
@login_requerido
def buscar_colector():

    consulta = request.args.get("consulta", "").strip()
    resultados = []

    if not consulta:
        return render_template(
            "colector.html",
            resultados=[],
            consulta="",
            nombre_usuario=session.get("nombre_usuario")
        )

    try:
        hoja = obtener_hoja()
        filas = hoja.get_all_values()
        consulta_normalizada = normalizar_texto(consulta)

        # Se omiten las filas 1 y 2.
        # Los datos comienzan desde la fila 3.
        for numero_fila, fila in enumerate(
            filas[PRIMERA_FILA_DATOS - 1:],
            start=PRIMERA_FILA_DATOS
        ):
            fila = preparar_fila(fila)

            item = fila[0]
            serie = fila[1]
            estado = fila[2]
            ubicacion = fila[3]
            usuario_asignado = fila[4]
            accesorio = fila[5]
            reasignacion = fila[6]
            condicion = fila[7]
            observacion = fila[8]

            serie_normalizada = normalizar_texto(serie)
            usuario_normalizado = normalizar_texto(
                usuario_asignado
            )

            coincide_serie = (
                len(consulta_normalizada) >= 6
                and serie_normalizada.endswith(
                    consulta_normalizada
                )
            )

            coincide_usuario = (
                consulta_normalizada in usuario_normalizado
            )

            if coincide_serie or coincide_usuario:
                resultados.append(
                    {
                        "fila": numero_fila,
                        "item": item,
                        "serie": serie,
                        "estado": estado,
                        "ubicacion": ubicacion,
                        "usuario_asignado": usuario_asignado,
                        "accesorio": accesorio,
                        "reasignacion": reasignacion,
                        "condicion": condicion,
                        "observacion": observacion
                    }
                )

    except Exception as error:
        print("Error al buscar en Google Sheets:", error)
        flash("No se pudo realizar la búsqueda.", "error")

    return render_template(
        "colector.html",
        resultados=resultados,
        consulta=consulta,
        nombre_usuario=session.get("nombre_usuario")
    )


# ==========================================
# EDITAR COLECTOR EXISTENTE
# ==========================================

@app.route("/editar-colector", methods=["POST"])
@login_requerido
def editar_colector():

    fila_texto = request.form.get("fila", "").strip()
    consulta = request.form.get("consulta", "").strip()
    serie_original = request.form.get(
        "serie_original",
        ""
    ).strip()

    datos = obtener_datos_formulario()
    serie = datos["serie"]

    if not fila_texto.isdigit():
        flash("La fila seleccionada no es válida.", "error")

        return redirect(
            url_for(
                "buscar_colector",
                consulta=consulta
            )
        )

    numero_fila = int(fila_texto)

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

    if not serie:
        flash("El número de serie es obligatorio.", "error")

        return redirect(
            url_for(
                "buscar_colector",
                consulta=consulta
            )
        )

    try:
        hoja = obtener_hoja()
        fila_actual = preparar_fila(
            hoja.row_values(numero_fila)
        )

        if not any(fila_actual):
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

        # Verifica que la fila todavía corresponda al registro
        # que el usuario seleccionó para editar.
        serie_actual_hoja = fila_actual[1]

        if (
            serie_original
            and normalizar_texto(serie_actual_hoja)
            != normalizar_texto(serie_original)
        ):
            flash(
                "El registro cambió mientras lo estabas editando. "
                "Realiza nuevamente la búsqueda.",
                "error"
            )

            return redirect(
                url_for(
                    "buscar_colector",
                    consulta=consulta or serie_original
                )
            )

        # Si se cambia el número de serie, evita utilizar una serie
        # que ya pertenezca a otro colector.
        fila_duplicada = buscar_fila_por_serie(
            hoja,
            serie,
            excluir_fila=numero_fila
        )

        if fila_duplicada:
            flash(
                "No se pudo actualizar: el número de serie "
                "ya pertenece a otro colector.",
                "error"
            )

            return redirect(
                url_for(
                    "buscar_colector",
                    consulta=consulta or serie
                )
            )

        # Actualiza exactamente la misma fila, sin insertar
        # una fila nueva y sin duplicar el colector.
        hoja.update(
            range_name=f"A{numero_fila}:I{numero_fila}",
            values=[datos_a_fila(datos)],
            value_input_option="USER_ENTERED"
        )

        flash(
            "Los datos del colector se actualizaron correctamente.",
            "exito"
        )

    except Exception as error:
        print("Error al actualizar Google Sheets:", error)

        flash(
            "No se pudieron guardar los cambios.",
            "error"
        )

    return redirect(
        url_for(
            "buscar_colector",
            consulta=serie[-6:] if len(serie) >= 6 else serie
        )
    )


# ==========================================
# INICIAR SERVIDOR
# ==========================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get(
            "FLASK_DEBUG",
            "false"
        ).lower() == "true"
    )