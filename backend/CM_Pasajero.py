from fastapi import APIRouter, HTTPException
import mysql.connector
from mysql.connector import Error
import os
from typing import Optional
from pydantic import BaseModel

router = APIRouter(prefix="/cm-pasajero", tags=["CM - Pasajero"])

# ===============================
# ENV
# ===============================
DB_USER = os.environ.get("DB_USER")
DB_PASS = os.environ.get("DB_PASS")
DB_NAME = os.environ.get("DB_NAME")
DB_SOCKET = os.environ.get("DB_SOCKET")

# ===============================
# DB CONNECTION
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
# MODELS
# ===============================
class PasajeroCreate(BaseModel):
    rut: str
    nombre: Optional[str] = None
    accountcode: int


class PasajeroUpdate(BaseModel):
    nombre: Optional[str] = None


# ===============================
# GET ALL POR EMPRESA
# ===============================
@router.get("/{accountcode}")
def get_pasajeros(accountcode: int):

    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Error DB")

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT * FROM CM_PASAJERO WHERE accountcode = %s",
            (accountcode,)
        )
        return cursor.fetchall()

    except Error as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        cursor.close()
        conn.close()


# ===============================
# CREATE
# ===============================
@router.post("/")
def crear_pasajero(data: PasajeroCreate):

    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Error DB")

    cursor = conn.cursor()

    try:
        conn.start_transaction()

        # 🔥 Validar duplicado
        cursor.execute(
            "SELECT rut FROM CM_PASAJERO WHERE rut = %s",
            (data.rut,)
        )
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="El pasajero ya existe")

        # 🔥 Validar empresa
        cursor.execute(
            "SELECT accountcode FROM CM_EMPRESA WHERE accountcode = %s",
            (data.accountcode,)
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Empresa no existe")

        cursor.execute(
            """
            INSERT INTO CM_PASAJERO (rut, nombre, accountcode)
            VALUES (%s, %s, %s)
            """,
            (data.rut, data.nombre, data.accountcode)
        )

        conn.commit()

        return {"message": "Pasajero creado correctamente"}

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
# UPDATE
# ===============================
@router.put("/{rut}")
def actualizar_pasajero(rut: str, data: PasajeroUpdate):

    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Error DB")

    cursor = conn.cursor()

    try:
        conn.start_transaction()

        # validar existencia
        cursor.execute(
            "SELECT rut FROM CM_PASAJERO WHERE rut = %s",
            (rut,)
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Pasajero no encontrado")

        fields = data.model_dump(exclude_none=True)

        if not fields:
            raise HTTPException(status_code=400, detail="No hay campos para actualizar")

        set_clause = ", ".join([f"{key} = %s" for key in fields.keys()])
        values = list(fields.values())
        values.append(rut)

        cursor.execute(
            f"UPDATE CM_PASAJERO SET {set_clause} WHERE rut = %s",
            values
        )

        conn.commit()

        return {"message": "Pasajero actualizado correctamente"}

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
# DELETE (REAL)
# ===============================
@router.delete("/{rut}")
def eliminar_pasajero(rut: str):

    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Error DB")

    cursor = conn.cursor()

    try:
        conn.start_transaction()

        cursor.execute(
            "SELECT rut FROM CM_PASAJERO WHERE rut = %s",
            (rut,)
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Pasajero no encontrado")

        cursor.execute(
            "DELETE FROM CM_PASAJERO WHERE rut = %s",
            (rut,)
        )

        conn.commit()

        return {"message": "Pasajero eliminado correctamente"}

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        cursor.close()
        conn.close()