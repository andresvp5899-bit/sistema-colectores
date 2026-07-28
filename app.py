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


# ==========================================
# CREDENCIALES
# ==========================================

def obtener_credenciales():

    credenciales_render = os.environ.get(
        "GOOGLE_CREDENTIALS"
    )

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

    cliente = gspread.authorize(
        obtener_credenciales()
    )

    archivo = cliente.open(
        NOMBRE_ARCHIVO_GOOGLE
    )

    return archivo.worksheet(
        NOMBRE_HOJA
    )


# ==========================================
# COMPLETAR COLUMNAS
# ==========================================

def preparar_fila(fila):

    fila = fila + [""] * (9 - len(fila))

    return fila[:9]


# ==========================================
# LOGIN REQUERIDO
# ==========================================

def login_requerido(funcion):

    @wraps(funcion)

    def ruta(*args, **kwargs):

        if not session.get("usuario_autenticado"):

            flash(
                "Debes iniciar sesión.",
                "error"
            )

            return redirect(
                url_for("login")
            )

        return funcion(*args, **kwargs)

    return ruta


# ==========================================
# LOGIN
# ==========================================

@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])

def login():

    if session.get("usuario_autenticado"):

        return redirect(
            url_for("inicio")
        )

    if request.method == "POST":

        usuario = request.form.get(
            "usuario",
            ""
        )

        contrasena = request.form.get(
            "contrasena",
            ""
        )

        if (
            compare_digest(usuario, USUARIO_ADMIN)
            and
            compare_digest(contrasena, CONTRASENA_ADMIN)
        ):

            session.clear()

            session["usuario_autenticado"] = True

            session["nombre_usuario"] = usuario

            flash(
                "Inicio de sesión correcto.",
                "exito"
            )

            return redirect(
                url_for("inicio")
            )

        flash(
            "Usuario o contraseña incorrectos.",
            "error"
        )

    return render_template(
        "login.html"
    )


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
        nombre_usuario=session.get(
            "nombre_usuario"
        )
    )


# ==========================================
# CERRAR SESIÓN
# ==========================================

@app.route("/logout")
@login_requerido

def logout():

    session.clear()

    flash(
        "Sesión cerrada correctamente.",
        "exito"
    )

    return redirect(
        url_for("login")
    )

# ==========================================
# REGISTRAR COLECTOR
# ==========================================

@app.route(
    "/colector",
    methods=["GET", "POST"]
)
@login_requerido
def colector():

    if request.method == "GET":

        return render_template(
            "colector.html",
            resultados=[],
            consulta="",
            nombre_usuario=session.get(
                "nombre_usuario"
            )
        )

    item = request.form.get(
        "item",
        ""
    ).strip()

    serie = request.form.get(
        "serie",
        ""
    ).strip()

    estado = request.form.get(
        "estado",
        ""
    ).strip()

    ubicacion = request.form.get(
        "ubicacion",
        ""
    ).strip()

    usuario = request.form.get(
        "usuario_asignado",
        ""
    ).strip()

    accesorio = request.form.get(
        "accesorio",
        ""
    ).strip()

    reasignacion = request.form.get(
        "reasignacion",
        ""
    ).strip()

    condicion = request.form.get(
        "condicion",
        ""
    ).strip()

    observacion = request.form.get(
        "observacion",
        ""
    ).strip()

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

        hoja.append_row(
            [
                item,
                serie,
                estado,
                ubicacion,
                usuario,
                accesorio,
                reasignacion,
                condicion,
                observacion
            ],
            value_input_option="USER_ENTERED",
            table_range="A2:I"
        )

        flash(
            "El colector se registró correctamente.",
            "exito"
        )

    except Exception as error:

        print(
            "Error al guardar en Google Sheets:",
            error
        )

        flash(
            "No se pudo guardar la información.",
            "error"
        )

    return redirect(
        url_for("colector")
    )

# ==========================================
# BUSCAR COLECTORES
# ==========================================

@app.route("/buscar", methods=["GET"])
@login_requerido
def buscar_colector():

    consulta = request.args.get(
        "consulta",
        ""
    ).strip()

    resultados = []

    if not consulta:

        return render_template(
            "colector.html",
            resultados=[],
            consulta="",
            nombre_usuario=session.get(
                "nombre_usuario"
            )
        )

    try:

        hoja = obtener_hoja()

        filas = hoja.get_all_values()

        consulta_normalizada = consulta.lower()

        # Se omiten las filas 1 y 2.
        # Los datos comienzan desde la fila 3.
        for numero_fila, fila in enumerate(
            filas[2:],
            start=3
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

            serie_normalizada = serie.lower()
            usuario_normalizado = usuario_asignado.lower()

            # La búsqueda por serie acepta desde 6 caracteres
            # hasta el número de serie completo.
            # Siempre compara desde el final de la serie registrada.
            coincide_serie = (
                len(consulta_normalizada) >= 6
                and serie_normalizada.endswith(consulta_normalizada)
            )

            # La búsqueda por usuario sigue funcionando por nombre
            # o por una parte del nombre, aunque tenga menos de 6 caracteres.
            coincide_usuario = (
                consulta_normalizada
                in usuario_normalizado
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

        print(
            "Error al buscar en Google Sheets:",
            error
        )

        flash(
            "No se pudo realizar la búsqueda.",
            "error"
        )

    return render_template(
        "colector.html",
        resultados=resultados,
        consulta=consulta,
        nombre_usuario=session.get(
            "nombre_usuario"
        )
    )



# ==========================================
# EDITAR COLECTOR EXISTENTE
# ==========================================

@app.route("/editar-colector", methods=["POST"])
@login_requerido
def editar_colector():

    fila_texto = request.form.get(
        "fila",
        ""
    ).strip()

    item = request.form.get(
        "item",
        ""
    ).strip()

    serie = request.form.get(
        "serie",
        ""
    ).strip()

    estado = request.form.get(
        "estado",
        ""
    ).strip()

    ubicacion = request.form.get(
        "ubicacion",
        ""
    ).strip()

    usuario = request.form.get(
        "usuario_asignado",
        ""
    ).strip()

    accesorio = request.form.get(
        "accesorio",
        ""
    ).strip()

    reasignacion = request.form.get(
        "reasignacion",
        ""
    ).strip()

    condicion = request.form.get(
        "condicion",
        ""
    ).strip()

    observacion = request.form.get(
        "observacion",
        ""
    ).strip()

    consulta = request.form.get(
        "consulta",
        ""
    ).strip()

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

    numero_fila = int(fila_texto)

    # Las filas 1 y 2 corresponden a encabezados.
    if numero_fila < 3:

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

        hoja = obtener_hoja()

        # Se vuelve a consultar la fila antes de actualizarla.
        # Esto evita escribir fuera del rango de datos.
        fila_actual = hoja.row_values(numero_fila)

        if not fila_actual:

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

        hoja.update(
            range_name=f"A{numero_fila}:I{numero_fila}",
            values=[[
                item,
                serie,
                estado,
                ubicacion,
                usuario,
                accesorio,
                reasignacion,
                condicion,
                observacion
            ]],
            value_input_option="USER_ENTERED"
        )

        flash(
            "Los datos del colector se actualizaron correctamente.",
            "exito"
        )

    except Exception as error:

        print(
            "Error al actualizar Google Sheets:",
            error
        )

        flash(
            "No se pudieron guardar los cambios.",
            "error"
        )

    return redirect(
        url_for(
            "buscar_colector",
            consulta=consulta or serie[-6:]
        )
    )


# ==========================================
# INICIAR SERVIDOR
# ==========================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),
        debug=True
    )