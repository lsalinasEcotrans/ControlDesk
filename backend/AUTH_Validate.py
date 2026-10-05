from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from mysql.connector import Error
import os
import json
import httpx

from AUTH import (
    crear_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

from Database import get_db_connection


router = APIRouter(
    prefix="/validate",
    tags=["AUTH - Validate"]
)


URL_AUTOCAB_AUTENTICATHION = os.environ.get(
    "URL_AUTOCAB_AUTENTICATHION"
)


# Rol que se asignará a usuarios nuevos provenientes de Autocab
DEFAULT_ROLE_ID = 2


class LoginRequest(BaseModel):
    username: str
    password: str


# ============================================================
# AUTOCAB
# ============================================================

async def autenticar_autocab(
    username: str,
    password: str
):

    if not URL_AUTOCAB_AUTENTICATHION:

        raise HTTPException(
            status_code=500,
            detail="URL_AUTOCAB_AUTENTICATHION no está configurada"
        )

    payload = {
        "username": username,
        "password": password
    }

    try:

        async with httpx.AsyncClient() as client:

            response = await client.post(
                URL_AUTOCAB_AUTENTICATHION,
                json=payload,
                timeout=30
            )

        # ----------------------------------------------------
        # Credenciales incorrectas
        # ----------------------------------------------------

        if response.status_code == 401:
            return None

        # ----------------------------------------------------
        # Otros errores de Autocab
        # ----------------------------------------------------

        if response.status_code >= 400:

            raise HTTPException(
                status_code=502,
                detail=(
                    "Error autenticando en Autocab: "
                    f"{response.status_code}"
                )
            )

        return response.json()

    except httpx.RequestError as e:

        raise HTTPException(
            status_code=502,
            detail=f"No se pudo conectar con Autocab: {e}"
        )


# ============================================================
# LOGIN
# ============================================================

@router.post(
    "/",
    summary="Autenticar usuario"
)
async def validate_user(data: LoginRequest):

    username = data.username
    password = data.password

    # --------------------------------------------------------
    # 1. Autenticar primero contra Autocab
    # --------------------------------------------------------

    autocab_response = await autenticar_autocab(
        username,
        password
    )

    if not autocab_response:

        raise HTTPException(
            status_code=401,
            detail="Usuario o contraseña incorrectos"
        )

    # --------------------------------------------------------
    # 2. Conectar a nuestra BD
    # --------------------------------------------------------

    conn = get_db_connection()

    if not conn:

        raise HTTPException(
            status_code=500,
            detail="No se pudo conectar a la base de datos"
        )

    cursor = conn.cursor(dictionary=True)

    try:

        # ----------------------------------------------------
        # 3. Crear usuario si no existe
        #    o devolver el existente
        # ----------------------------------------------------

        cursor.callproc(
            "SP_AUTH_USUARIO_CREAR",
            (
                username,
                username,
                DEFAULT_ROLE_ID,
                None
            )
        )

        user = None

        for result in cursor.stored_results():

            user = result.fetchone()
            break

        if not user:

            raise HTTPException(
                status_code=500,
                detail="No se pudo obtener el usuario"
            )

        # ----------------------------------------------------
        # 4. Convertir JSON_MENU
        # ----------------------------------------------------

        if (
            user.get("json_menu")
            and isinstance(user["json_menu"], str)
        ):

            try:

                user["json_menu"] = json.loads(
                    user["json_menu"]
                )

            except json.JSONDecodeError:

                user["json_menu"] = None

        # ----------------------------------------------------
        # 5. Convertir EXTRA_PERMISSIONS
        # ----------------------------------------------------

        if (
            user.get("extra_permissions")
            and isinstance(
                user["extra_permissions"],
                str
            )
        ):

            try:

                user["extra_permissions"] = json.loads(
                    user["extra_permissions"]
                )

            except json.JSONDecodeError:

                user["extra_permissions"] = None

        # ----------------------------------------------------
        # 6. Confirmar creación del usuario
        # ----------------------------------------------------

        conn.commit()

        # ----------------------------------------------------
        # 7. Generar JWT
        # ----------------------------------------------------

        access_token, fecha_creacion, fecha_expiracion = (
            crear_access_token(user)
        )

        # ----------------------------------------------------
        # 8. Guardar sesión
        # ----------------------------------------------------

        cursor.callproc(
            "SP_AUTH_SESION_CREAR",
            (
                user["id"],
                access_token,
                fecha_creacion.replace(tzinfo=None),
                fecha_expiracion.replace(tzinfo=None)
            )
        )

        # ----------------------------------------------------
        # 9. Confirmar creación de sesión
        # ----------------------------------------------------

        conn.commit()

        # ----------------------------------------------------
        # 10. Respuesta
        # ----------------------------------------------------

        return {
            "authenticated": True,
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "source": "autocab",
            "user": user
        }

    except Error as e:

        conn.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Error ejecutando SP: {e}"
        )

    finally:

        cursor.close()
        conn.close()