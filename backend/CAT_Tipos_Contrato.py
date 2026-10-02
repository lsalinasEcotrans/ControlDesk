from fastapi import APIRouter, HTTPException
import mysql.connector
from mysql.connector import Error
import os
from typing import Optional
from pydantic import BaseModel

router = APIRouter(
    prefix="/cat-tipos-contrato",
    tags=["CAT - Tipos Contrato"]
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
class TipoContratoCreate(BaseModel):
    codigo: str
    nombre: str
    porcentaje_descuento: float
    activo: bool = True


class TipoContratoUpdate(BaseModel):
    codigo: Optional[str] = None
    nombre: Optional[str] = None
    porcentaje_descuento: Optional[float] = None
    activo: Optional[bool] = None


# ===============================
# GET ALL
# ===============================
@router.get("/")
def listar_tipos_contrato(activos: bool = True):

    conn = get_db_connection()

    if not conn:
        raise HTTPException(status_code=500, detail="Error DB")

    cursor = conn.cursor(dictionary=True)

    try:

        if activos:
            cursor.execute("""
                SELECT
                    id,
                    codigo,
                    nombre,
                    porcentaje_descuento,
                    activo,
                    created_at,
                    updated_at
                FROM CAT_TIPOS_CONTRATO
                WHERE activo = TRUE
                ORDER BY nombre ASC
            """)
        else:
            cursor.execute("""
                SELECT
                    id,
                    codigo,
                    nombre,
                    porcentaje_descuento,
                    activo,
                    created_at,
                    updated_at
                FROM CAT_TIPOS_CONTRATO
                ORDER BY nombre ASC
            """)

        return cursor.fetchall()

    except Error as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        cursor.close()
        conn.close()


# ===============================
# GET BY ID
# ===============================
@router.get("/{tipo_contrato_id}")
def obtener_tipo_contrato(tipo_contrato_id: int):

    conn = get_db_connection()

    if not conn:
        raise HTTPException(status_code=500, detail="Error DB")

    cursor = conn.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT
                id,
                codigo,
                nombre,
                porcentaje_descuento,
                activo,
                created_at,
                updated_at
            FROM CAT_TIPOS_CONTRATO
            WHERE id = %s
        """, (tipo_contrato_id,))

        contrato = cursor.fetchone()

        if not contrato:
            raise HTTPException(
                status_code=404,
                detail="Tipo de contrato no encontrado"
            )

        return contrato

    except HTTPException:
        raise

    except Error as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        cursor.close()
        conn.close()


# ===============================
# CREATE
# ===============================
@router.post("/")
def crear_tipo_contrato(data: TipoContratoCreate):

    conn = get_db_connection()

    if not conn:
        raise HTTPException(status_code=500, detail="Error DB")

    cursor = conn.cursor()

    try:

        conn.start_transaction()

        cursor.execute("""
            SELECT id
            FROM CAT_TIPOS_CONTRATO
            WHERE codigo = %s
        """, (data.codigo,))

        if cursor.fetchone():
            raise HTTPException(
                status_code=400,
                detail="El código del tipo de contrato ya existe"
            )

        cursor.execute("""
            INSERT INTO CAT_TIPOS_CONTRATO (
                codigo,
                nombre,
                porcentaje_descuento,
                activo
            )
            VALUES (%s, %s, %s, %s)
        """, (
            data.codigo,
            data.nombre,
            data.porcentaje_descuento,
            data.activo
        ))

        contrato_id = cursor.lastrowid

        conn.commit()

        return {
            "message": "Tipo de contrato creado correctamente",
            "id": contrato_id
        }

    except HTTPException:
        conn.rollback()
        raise

    except Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        cursor.close()
        conn.close()


# ===============================
# UPDATE
# ===============================
@router.put("/{tipo_contrato_id}")
def actualizar_tipo_contrato(
    tipo_contrato_id: int,
    data: TipoContratoUpdate
):

    conn = get_db_connection()

    if not conn:
        raise HTTPException(status_code=500, detail="Error DB")

    cursor = conn.cursor()

    try:

        conn.start_transaction()

        cursor.execute("""
            SELECT id
            FROM CAT_TIPOS_CONTRATO
            WHERE id = %s
        """, (tipo_contrato_id,))

        if not cursor.fetchone():
            raise HTTPException(
                status_code=404,
                detail="Tipo de contrato no encontrado"
            )

        fields = data.model_dump(exclude_none=True)

        if not fields:
            raise HTTPException(
                status_code=400,
                detail="No hay campos para actualizar"
            )

        if "codigo" in fields:

            cursor.execute("""
                SELECT id
                FROM CAT_TIPOS_CONTRATO
                WHERE codigo = %s
                  AND id <> %s
            """, (
                fields["codigo"],
                tipo_contrato_id
            ))

            if cursor.fetchone():
                raise HTTPException(
                    status_code=400,
                    detail="El código ya está siendo utilizado"
                )

        set_clause = ", ".join(
            [f"{key} = %s" for key in fields.keys()]
        )

        values = list(fields.values())
        values.append(tipo_contrato_id)

        cursor.execute(f"""
            UPDATE CAT_TIPOS_CONTRATO
            SET {set_clause}
            WHERE id = %s
        """, values)

        conn.commit()

        return {
            "message": "Tipo de contrato actualizado correctamente"
        }

    except HTTPException:
        conn.rollback()
        raise

    except Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        cursor.close()
        conn.close()


# ===============================
# DELETE / DESACTIVAR
# ===============================
@router.delete("/{tipo_contrato_id}")
def eliminar_tipo_contrato(tipo_contrato_id: int):

    conn = get_db_connection()

    if not conn:
        raise HTTPException(status_code=500, detail="Error DB")

    cursor = conn.cursor()

    try:

        conn.start_transaction()

        cursor.execute("""
            SELECT id, activo
            FROM CAT_TIPOS_CONTRATO
            WHERE id = %s
        """, (tipo_contrato_id,))

        contrato = cursor.fetchone()

        if not contrato:
            raise HTTPException(
                status_code=404,
                detail="Tipo de contrato no encontrado"
            )

        cursor.execute("""
            UPDATE CAT_TIPOS_CONTRATO
            SET activo = FALSE
            WHERE id = %s
        """, (tipo_contrato_id,))

        conn.commit()

        return {
            "message": "Tipo de contrato desactivado correctamente"
        }

    except HTTPException:
        conn.rollback()
        raise

    except Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        cursor.close()
        conn.close()