from fastapi import APIRouter, HTTPException, Query
import mysql.connector
from mysql.connector import Error
import os
from typing import Optional
from pydantic import BaseModel

router = APIRouter(prefix="/auth-login", tags=["CRUD - Portal"])

# ===============================
# ENV (ya definido arriba, reutilizar)
# ===============================
# DB_USER, DB_PASS, DB_NAME, DB_SOCKET ya están definidos
DB_USER = os.environ.get("DB_USER")
DB_PASS = os.environ.get("DB_PASS")
DB_NAME = os.environ.get("DB_NAME_portalCliente")
DB_SOCKET = os.environ.get("DB_SOCKET")

# ===============================
# DB CONNECTION (reutilizar la función existente)
# ===============================
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            user=DB_USER,
            password=DB_PASS,
            unix_socket=DB_SOCKET,
            database=DB_NAME
        )
        return conn
    except Error as e:
        print(f"❌ Error conectando a la base de datos: {e}")
        return None


# ===============================
# MODEL CREATE AUTH_LOGIN
# ===============================
class AuthLoginCreate(BaseModel):
    nombre: str
    correo: str
    displayName: str
    accountCode: int
    customerId: int

class AuthLoginUpdate(BaseModel):
    nombre: Optional[str] = None
    correo: Optional[str] = None
    contrasena: Optional[str] = None
    displayName: Optional[str] = None
    accountCode: Optional[int] = None
    customerId: Optional[int] = None

# ===============================
# GET ALL AUTH_LOGIN
# ===============================
@router.get("/")
def get_auth_login(estado: Optional[str] = Query(None)):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a la base de datos")

    cursor = conn.cursor(dictionary=True)

    try:
        if estado:
            cursor.execute(
                """
                SELECT * FROM AUTH_LOGIN 
                WHERE estado = %s OR estado IS NULL
                ORDER BY created_at DESC
                """,
                (estado,)
            )
        else:
            cursor.execute(
                "SELECT * FROM AUTH_LOGIN ORDER BY created_at DESC"
            )
        
        result = cursor.fetchall()
        return result

    except Error as e:
        raise HTTPException(status_code=500, detail=f"Error consultando AUTH_LOGIN: {e}")

    finally:
        cursor.close()
        conn.close()

# ===============================
# GET AUTH_LOGIN BY ID
# ===============================
@router.get("/{id}")
def get_auth_login_by_id(id: int):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a la base de datos")

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT * FROM AUTH_LOGIN WHERE id = %s",
            (id,)
        )
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Auth login no encontrado")

        return result

    except Error as e:
        raise HTTPException(status_code=500, detail=f"Error consultando AUTH_LOGIN: {e}")

    finally:
        cursor.close()
        conn.close()

# ===============================
# CREATE AUTH_LOGIN
# ===============================
@router.post("/")
def crear_auth_login(data: AuthLoginCreate):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(
            status_code=500, 
            detail="Error conectando a la base de datos"
        )

    cursor = conn.cursor()

    try:
        conn.start_transaction()

        # 🔍 Verificar si el correo ya existe
        cursor.execute(
            "SELECT id FROM AUTH_LOGIN WHERE correo = %s",
            (data.correo,)
        )
        existing = cursor.fetchone()

        if existing:
            raise HTTPException(
                status_code=400,
                detail="Ya existe un usuario con este correo"
            )

        # 🧩 Insertar nuevo usuario
        insert_query = """
            INSERT INTO AUTH_LOGIN (
                nombre,
                correo,
                contrasena,
                displayName,
                accountCode,
                customerId,
                estado
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'pendiente')
        """

        cursor.execute(insert_query, (
            data.nombre,
            data.correo,
            "$2b$12$MhaXh04WUmjzOr3.HMDxyerCmPwLChS00o6xvnsZVFz.3tA.xJiu.",  # 🔑 clave inicial
            data.displayName,
            data.accountCode,
            data.customerId
        ))

        new_id = cursor.lastrowid
        conn.commit()

        return {
            "message": "Auth login creado correctamente",
            "id": new_id
        }

    except HTTPException:
        conn.rollback()
        raise

    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error creando usuario: {str(e)}"
        )

    finally:
        cursor.close()
        conn.close()

# ===============================
# UPDATE AUTH_LOGIN BY ID
# ===============================
@router.put("/{id}")
def actualizar_auth_login(id: int, data: AuthLoginUpdate):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a la base de datos")

    cursor = conn.cursor()

    try:
        conn.start_transaction()

        # Verificar que el usuario existe
        cursor.execute(
            "SELECT id FROM AUTH_LOGIN WHERE id = %s",
            (id,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Auth login no encontrado")

        fields = data.model_dump(exclude_none=True)
        if not fields:
            raise HTTPException(status_code=400, detail="No se enviaron campos para actualizar")

        # Construir query dinámico
        set_clause = ", ".join([f"{key} = %s" for key in fields.keys()])
        values = list(fields.values())
        values.append(id)

        cursor.execute(
            f"UPDATE AUTH_LOGIN SET {set_clause} WHERE id = %s",
            values
        )

        conn.commit()
        return {"message": "Auth login actualizado correctamente", "id": id}

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        cursor.close()
        conn.close()

# ===============================
# DELETE AUTH_LOGIN (Soft delete - cambiar estado)
# ===============================
@router.delete("/{id}")
def eliminar_auth_login(id: int):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a la base de datos")

    cursor = conn.cursor()

    try:
        conn.start_transaction()

        # Verificar que existe
        cursor.execute(
            "SELECT id FROM AUTH_LOGIN WHERE id = %s",
            (id,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Auth login no encontrado")

        cursor.execute(
            "UPDATE AUTH_LOGIN SET estado = 'inactivo' WHERE id = %s",
            (id,)
        )

        conn.commit()
        return {"message": "Auth login eliminado correctamente (estado: inactivo)", "id": id}

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        cursor.close()
        conn.close()

# ===============================
# RESET PASSWORD
# ===============================
@router.patch("/{id}/reset-password")
def reset_password_auth_login(id: int):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a la base de datos")

    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT id FROM AUTH_LOGIN WHERE id = %s",
            (id,)
        )
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Auth login no encontrado")

        cursor.execute(
            "UPDATE AUTH_LOGIN SET contrasena = %s, estado = 'pendiente' WHERE id = %s",
            ("$2b$12$MhaXh04WUmjzOr3.HMDxyerCmPwLChS00o6xvnsZVFz.3tA.xJiu.", id)
        )

        conn.commit()
        return {"message": "Contraseña reseteada correctamente", "id": id}

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        cursor.close()
        conn.close()

# ===============================
# GET BY CORREO
# ===============================
@router.get("/correo/{correo}")
def get_auth_login_by_correo(correo: str):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a la base de datos")

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT * FROM AUTH_LOGIN WHERE correo = %s",
            (correo,)
        )
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Auth login no encontrado")

        return result

    except Error as e:
        raise HTTPException(status_code=500, detail=f"Error consultando AUTH_LOGIN: {e}")

    finally:
        cursor.close()
        conn.close()