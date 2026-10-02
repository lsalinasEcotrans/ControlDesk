from fastapi import APIRouter, HTTPException
import mysql.connector
from mysql.connector import Error
import os
import json
from typing import Optional, List
from pydantic import BaseModel


router = APIRouter(
    prefix="/ges-pre-contratos",
    tags=["GES - Pre Contratos"]
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

        print(
            f"❌ Error conectando a la base de datos: {e}"
        )

        return None


# ===============================
# MODELS
# ===============================

class PreContratoCreate(BaseModel):

    nombre: str

    fuentes: List[str]

    contenido: str

    creado_por: int


class PreContratoUpdate(BaseModel):

    nombre: Optional[str] = None

    fuentes: Optional[List[str]] = None

    contenido: Optional[str] = None

    actualizado_por: Optional[int] = None


# ===============================
# GET ALL
# ===============================

@router.get("/")
def listar_pre_contratos(
    activos: bool = True
):

    conn = get_db_connection()

    if not conn:

        raise HTTPException(
            status_code=500,
            detail="Error DB"
        )

    cursor = conn.cursor(
        dictionary=True
    )

    try:

        if activos:

            cursor.execute(
                """
                SELECT *
                FROM VW_GES_LISTAR_PRE_CONTRATOS
                """
            )

       
        contratos = cursor.fetchall()

        return contratos

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

@router.get("/{pre_contrato_id}")
def obtener_pre_contrato(
    pre_contrato_id: int
):

    conn = get_db_connection()

    if not conn:

        raise HTTPException(
            status_code=500,
            detail="Error DB"
        )

    cursor = conn.cursor(
        dictionary=True
    )

    try:

        cursor.execute(
            """
            SELECT
                id_pre_contrato,
                nombre,
                fuentes,
                contenido,
                estado,
                creado_por,
                fecha_creacion,
                actualizado_por,
                fecha_actualizacion,
                eliminado_por,
                fecha_eliminacion
            FROM GES_PRE_CONTRATOS
            WHERE id_pre_contrato = %s
            """,
            (pre_contrato_id,)
        )

        contrato = cursor.fetchone()

        if not contrato:

            raise HTTPException(
                status_code=404,
                detail="Pre-contrato no encontrado"
            )

        return contrato

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
def crear_pre_contrato(
    data: PreContratoCreate
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
        # VALIDAR NOMBRE DUPLICADO
        # ===============================

        cursor.execute(
            """
            SELECT id_pre_contrato
            FROM GES_PRE_CONTRATOS
            WHERE nombre = %s
              AND estado = 1
            """,
            (data.nombre,)
        )

        if cursor.fetchone():

            raise HTTPException(
                status_code=400,
                detail="Ya existe un pre-contrato activo con ese nombre"
            )

        # ===============================
        # CONVERTIR FUENTES A JSON
        # ===============================

        fuentes_json = json.dumps(
            data.fuentes,
            ensure_ascii=False
        )

        # ===============================
        # CREAR
        # ===============================

        cursor.execute(
            """
            INSERT INTO GES_PRE_CONTRATOS (
                nombre,
                fuentes,
                contenido,
                estado,
                creado_por,
                fecha_creacion
            )
            VALUES (
                %s,
                %s,
                %s,
                1,
                %s,
                NOW()
            )
            """,
            (
                data.nombre,
                fuentes_json,
                data.contenido,
                data.creado_por
            )
        )

        pre_contrato_id = cursor.lastrowid

        conn.commit()

        return {
            "message": "Pre-contrato creado correctamente",
            "id": pre_contrato_id
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

@router.put("/{pre_contrato_id}")
def actualizar_pre_contrato(
    pre_contrato_id: int,
    data: PreContratoUpdate
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
            SELECT
                id_pre_contrato
            FROM GES_PRE_CONTRATOS
            WHERE id_pre_contrato = %s
              AND estado = 1
            """,
            (pre_contrato_id,)
        )

        if not cursor.fetchone():

            raise HTTPException(
                status_code=404,
                detail="Pre-contrato no encontrado"
            )

        # ===============================
        # CAMPOS
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
        # VALIDAR NOMBRE
        # ===============================

        if "nombre" in fields:

            cursor.execute(
                """
                SELECT
                    id_pre_contrato
                FROM GES_PRE_CONTRATOS
                WHERE nombre = %s
                  AND id_pre_contrato <> %s
                  AND estado = 1
                """,
                (
                    fields["nombre"],
                    pre_contrato_id
                )
            )

            if cursor.fetchone():

                raise HTTPException(
                    status_code=400,
                    detail="Ya existe otro pre-contrato activo con ese nombre"
                )

        # ===============================
        # CONVERTIR FUENTES A JSON
        # ===============================

        if "fuentes" in fields:

            fields["fuentes"] = json.dumps(
                fields["fuentes"],
                ensure_ascii=False
            )

        # ===============================
        # UPDATE DINÁMICO
        # ===============================

        set_clause = ", ".join(
            [
                f"{key} = %s"
                for key in fields.keys()
            ]
        )

        values = list(
            fields.values()
        )

        values.append(
            pre_contrato_id
        )

        cursor.execute(
            f"""
            UPDATE GES_PRE_CONTRATOS
            SET
                {set_clause},
                fecha_actualizacion = NOW()
            WHERE id_pre_contrato = %s
            """,
            values
        )

        conn.commit()

        return {
            "message": "Pre-contrato actualizado correctamente"
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
# DELETE / SOFT DELETE
# ===============================

@router.delete("/{pre_contrato_id}")
def eliminar_pre_contrato(
    pre_contrato_id: int,
    eliminado_por: int
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
            SELECT
                id_pre_contrato,
                estado
            FROM GES_PRE_CONTRATOS
            WHERE id_pre_contrato = %s
            """,
            (pre_contrato_id,)
        )

        contrato = cursor.fetchone()

        if not contrato:

            raise HTTPException(
                status_code=404,
                detail="Pre-contrato no encontrado"
            )

        # ===============================
        # VALIDAR ESTADO
        # ===============================

        if contrato[1] == 0:

            raise HTTPException(
                status_code=400,
                detail="El pre-contrato ya se encuentra eliminado"
            )

        # ===============================
        # SOFT DELETE
        # ===============================

        cursor.execute(
            """
            UPDATE GES_PRE_CONTRATOS
            SET
                estado = 0,
                eliminado_por = %s,
                fecha_eliminacion = NOW()
            WHERE id_pre_contrato = %s
            """,
            (
                eliminado_por,
                pre_contrato_id
            )
        )

        conn.commit()

        return {
            "message": "Pre-contrato eliminado correctamente"
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