from fastapi import APIRouter, HTTPException
import mysql.connector
from mysql.connector import Error
import os
from typing import Optional
from pydantic import BaseModel

router = APIRouter(prefix="/cm-empresa", tags=["CM - Empresa"])

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
class EmpresaCreate(BaseModel):
    displayname: Optional[str] = None
    accountcode: int
    customerId: int


class EmpresaUpdate(BaseModel):
    displayname: Optional[str] = None
    customerId: Optional[int] = None
    estado: Optional[str] = None  # activo / inactivo


# ===============================
# GET ALL (solo activos)
# ===============================
@router.get("/")
def get_empresas():

    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Error DB")

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT * FROM CM_EMPRESA WHERE estado = 'activo'"
        )
        return cursor.fetchall()

    except Error as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        cursor.close()
        conn.close()


# ===============================
# GET BY ID
# ===============================
@router.get("/{accountcode}")
def get_empresa(accountcode: int):

    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Error DB")

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT * FROM CM_EMPRESA WHERE accountcode = %s",
            (accountcode,)
        )
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")

        return row

    except Error as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        cursor.close()
        conn.close()


# ===============================
# CREATE
# ===============================
@router.post("/")
def crear_empresa(data: EmpresaCreate):

    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Error DB")

    cursor = conn.cursor()

    try:
        conn.start_transaction()

        cursor.execute(
            """
            INSERT INTO CM_EMPRESA (displayname, accountcode, customerId)
            VALUES (%s, %s, %s)
            """,
            (data.displayname, data.accountcode, data.customerId)
        )

        conn.commit()

        return {"message": "Empresa creada correctamente"}

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        cursor.close()
        conn.close()


# ===============================
# UPDATE
# ===============================
@router.put("/{accountcode}")
def actualizar_empresa(accountcode: int, data: EmpresaUpdate):

    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Error DB")

    cursor = conn.cursor()

    try:
        conn.start_transaction()

        # validar existencia
        cursor.execute(
            "SELECT accountcode FROM CM_EMPRESA WHERE accountcode = %s",
            (accountcode,)
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Empresa no encontrada")

        fields = data.model_dump(exclude_none=True)

        if not fields:
            raise HTTPException(status_code=400, detail="No hay campos para actualizar")

        # validar estado
        if "estado" in fields:
            if fields["estado"] not in ["activo", "inactivo"]:
                raise HTTPException(status_code=400, detail="Estado inválido")

        set_clause = ", ".join([f"{key} = %s" for key in fields.keys()])
        values = list(fields.values())
        values.append(accountcode)

        cursor.execute(
            f"UPDATE CM_EMPRESA SET {set_clause} WHERE accountcode = %s",
            values
        )

        conn.commit()

        return {"message": "Empresa actualizada correctamente"}

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
# DELETE LOGICO (soft delete)
# ===============================
@router.delete("/{accountcode}")
def eliminar_empresa(accountcode: int):

    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Error DB")

    cursor = conn.cursor()

    try:
        conn.start_transaction()

        cursor.execute(
            "SELECT accountcode FROM CM_EMPRESA WHERE accountcode = %s",
            (accountcode,)
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Empresa no encontrada")

        cursor.execute(
            """
            UPDATE CM_EMPRESA
            SET estado = 'inactivo'
            WHERE accountcode = %s
            """,
            (accountcode,)
        )

        conn.commit()

        return {"message": "Empresa desactivada correctamente"}

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        cursor.close()
        conn.close()