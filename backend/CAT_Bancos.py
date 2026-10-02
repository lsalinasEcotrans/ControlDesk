from fastapi import APIRouter, HTTPException
import mysql.connector
from mysql.connector import Error
import os
from typing import Optional
from pydantic import BaseModel

router = APIRouter(
    prefix="/cat-bancos",
    tags=["CAT - Bancos"]
)

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

class BancoCreate(BaseModel):
    codigo_banco: str
    nombre: str
    nombre_corto: Optional[str] = None
    activo: bool = True


class BancoUpdate(BaseModel):
    codigo_banco: Optional[str] = None
    nombre: Optional[str] = None
    nombre_corto: Optional[str] = None
    activo: Optional[bool] = None


# ===============================
# GET ALL
# ===============================
@router.get("/")
def listar_bancos(activos: bool = True):

    conn = get_db_connection()

    if not conn:
        raise HTTPException(
            status_code=500,
            detail="Error DB"
        )

    cursor = conn.cursor(dictionary=True)

    try:

        if activos:
            cursor.execute(
                """
                SELECT
                    id,
                    codigo_banco,
                    nombre,
                    nombre_corto,
                    activo,
                    created_at,
                    updated_at
                FROM CAT_BANCOS
                WHERE activo = TRUE
                ORDER BY nombre ASC
                """
            )
        else:
            cursor.execute(
                """
                SELECT
                    id,
                    codigo_banco,
                    nombre,
                    nombre_corto,
                    activo,
                    created_at,
                    updated_at
                FROM CAT_BANCOS
                ORDER BY nombre ASC
                """
            )

        return cursor.fetchall()

    except Error as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:

        cursor.close()
        conn.close()


# ===============================
# GET BY ID
# ===============================
@router.get("/{banco_id}")
def obtener_banco(banco_id: int):

    conn = get_db_connection()

    if not conn:
        raise HTTPException(
            status_code=500,
            detail="Error DB"
        )

    cursor = conn.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                id,
                codigo_banco,
                nombre,
                nombre_corto,
                activo,
                created_at,
                updated_at
            FROM CAT_BANCOS
            WHERE id = %s
            """,
            (banco_id,)
        )

        banco = cursor.fetchone()

        if not banco:
            raise HTTPException(
                status_code=404,
                detail="Banco no encontrado"
            )

        return banco

    except HTTPException:
        raise

    except Error as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:

        cursor.close()
        conn.close()


# ===============================
# CREATE
# ===============================
@router.post("/")
def crear_banco(data: BancoCreate):

    conn = get_db_connection()

    if not conn:
        raise HTTPException(
            status_code=500,
            detail="Error DB"
        )

    cursor = conn.cursor()

    try:

        conn.start_transaction()

        # ===============================
        # VALIDAR CODIGO DUPLICADO
        # ===============================
        cursor.execute(
            """
            SELECT id
            FROM CAT_BANCOS
            WHERE codigo_banco = %s
            """,
            (data.codigo_banco,)
        )

        if cursor.fetchone():

            raise HTTPException(
                status_code=400,
                detail="El código de banco ya existe"
            )

        # ===============================
        # CREAR
        # ===============================
        cursor.execute(
            """
            INSERT INTO CAT_BANCOS (
                codigo_banco,
                nombre,
                nombre_corto,
                activo
            )
            VALUES (%s, %s, %s, %s)
            """,
            (
                data.codigo_banco,
                data.nombre,
                data.nombre_corto,
                data.activo
            )
        )

        banco_id = cursor.lastrowid

        conn.commit()

        return {
            "message": "Banco creado correctamente",
            "id": banco_id
        }

    except HTTPException:

        conn.rollback()
        raise

    except Error as e:

        conn.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:

        cursor.close()
        conn.close()


# ===============================
# UPDATE
# ===============================
@router.put("/{banco_id}")
def actualizar_banco(
    banco_id: int,
    data: BancoUpdate
):

    conn = get_db_connection()

    if not conn:
        raise HTTPException(
            status_code=500,
            detail="Error DB"
        )

    cursor = conn.cursor()

    try:

        conn.start_transaction()

        # ===============================
        # VALIDAR EXISTENCIA
        # ===============================
        cursor.execute(
            """
            SELECT id
            FROM CAT_BANCOS
            WHERE id = %s
            """,
            (banco_id,)
        )

        if not cursor.fetchone():

            raise HTTPException(
                status_code=404,
                detail="Banco no encontrado"
            )

        # ===============================
        # CAMPOS A ACTUALIZAR
        # ===============================
        fields = data.model_dump(
            exclude_none=True
        )

        if not fields:

            raise HTTPException(
                status_code=400,
                detail="No hay campos para actualizar"
            )

        # ===============================
        # VALIDAR CODIGO
        # ===============================
        if "codigo_banco" in fields:

            cursor.execute(
                """
                SELECT id
                FROM CAT_BANCOS
                WHERE codigo_banco = %s
                  AND id <> %s
                """,
                (
                    fields["codigo_banco"],
                    banco_id
                )
            )

            if cursor.fetchone():

                raise HTTPException(
                    status_code=400,
                    detail="El código de banco ya está siendo utilizado"
                )

        # ===============================
        # UPDATE DINAMICO
        # ===============================
        set_clause = ", ".join(
            [
                f"{key} = %s"
                for key in fields.keys()
            ]
        )

        values = list(fields.values())
        values.append(banco_id)

        cursor.execute(
            f"""
            UPDATE CAT_BANCOS
            SET {set_clause}
            WHERE id = %s
            """,
            values
        )

        conn.commit()

        return {
            "message": "Banco actualizado correctamente"
        }

    except HTTPException:

        conn.rollback()
        raise

    except Error as e:

        conn.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:

        cursor.close()
        conn.close()


# ===============================
# DELETE / DESACTIVAR
# ===============================
@router.delete("/{banco_id}")
def eliminar_banco(banco_id: int):

    conn = get_db_connection()

    if not conn:
        raise HTTPException(
            status_code=500,
            detail="Error DB"
        )

    cursor = conn.cursor()

    try:

        conn.start_transaction()

        # ===============================
        # VALIDAR EXISTENCIA
        # ===============================
        cursor.execute(
            """
            SELECT id, activo
            FROM CAT_BANCOS
            WHERE id = %s
            """,
            (banco_id,)
        )

        banco = cursor.fetchone()

        if not banco:

            raise HTTPException(
                status_code=404,
                detail="Banco no encontrado"
            )

        # ===============================
        # DESACTIVAR
        # ===============================
        cursor.execute(
            """
            UPDATE CAT_BANCOS
            SET activo = FALSE
            WHERE id = %s
            """,
            (banco_id,)
        )

        conn.commit()

        return {
            "message": "Banco desactivado correctamente"
        }

    except HTTPException:

        conn.rollback()
        raise

    except Error as e:

        conn.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:

        cursor.close()
        conn.close()