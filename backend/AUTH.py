import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from mysql.connector import Error

from Database import get_db_connection


# ============================================================
# CONFIGURACIÓN JWT
# ============================================================

SECRET_KEY = os.environ.get("SECRET_KEY")

ALGORITHM = os.environ.get(
    "ALGORITHM",
    "HS256"
)

ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.environ.get(
        "ACCESS_TOKEN_EXPIRE_MINUTES",
        "360"
    )
)

security = HTTPBearer()


# ============================================================
# CREAR ACCESS TOKEN
# ============================================================

def crear_access_token(user: dict):
    """
    Crea un JWT para el usuario autenticado.

    Retorna:

        token
        fecha_creacion
        fecha_expiracion
    """

    if not SECRET_KEY:

        raise HTTPException(
            status_code=500,
            detail="SECRET_KEY no está configurada"
        )

    fecha_creacion = datetime.now(timezone.utc)

    fecha_expiracion = (
        fecha_creacion
        + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    )

    payload = {
        "sub": user["username"],
        "user_id": user["id"],
        "role_id": user["role_id"],
        "role_name": user.get("role_name"),
        "iat": fecha_creacion,
        "exp": fecha_expiracion
    }

    token = jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return (
        token,
        fecha_creacion,
        fecha_expiracion
    )


# ============================================================
# VALIDAR USUARIO ACTUAL
# ============================================================

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Valida:

    1. Firma del JWT
    2. Expiración del JWT
    3. Existencia de la sesión
    4. Sesión activa
    5. Expiración de la sesión en BD
    """

    token = credentials.credentials

    # --------------------------------------------------------
    # 1. Verificar SECRET_KEY
    # --------------------------------------------------------

    if not SECRET_KEY:

        raise HTTPException(
            status_code=500,
            detail="SECRET_KEY no está configurada"
        )

    # --------------------------------------------------------
    # 2. Decodificar JWT
    # --------------------------------------------------------

    try:

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        username = payload.get("sub")
        user_id = payload.get("user_id")
        role_id = payload.get("role_id")
        role_name = payload.get("role_name")

        if not username or not user_id:

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido"
            )

    except JWTError:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado"
        )

    # --------------------------------------------------------
    # 3. Conectar a BD
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
        # 4. Validar sesión mediante SP
        # ----------------------------------------------------

        cursor.callproc(
            "SP_AUTH_SESION_VALIDAR",
            (
                user_id,
                token
            )
        )

        sesion = None

        for result in cursor.stored_results():

            sesion = result.fetchone()
            break

        # ----------------------------------------------------
        # 5. Sesión inválida
        # ----------------------------------------------------

        if not sesion:

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="La sesión no es válida o fue cerrada"
            )

        # ----------------------------------------------------
        # 6. Usuario autenticado
        # ----------------------------------------------------

        return {
            "user_id": user_id,
            "username": username,
            "role_id": role_id,
            "role_name": role_name,
            "session_id": sesion["id"]
        }

    except HTTPException:

        raise

    except Error as e:

        raise HTTPException(
            status_code=500,
            detail=f"Error validando sesión: {e}"
        )

    finally:

        cursor.close()
        conn.close()