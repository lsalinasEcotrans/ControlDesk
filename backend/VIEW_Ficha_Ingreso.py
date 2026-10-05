from fastapi import APIRouter, HTTPException, Query
import mysql.connector
from mysql.connector import Error
import os
from typing import Optional

router = APIRouter(
    prefix="/vw-ges-movil",
    tags=["VW - GES Movil"]
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
# GET ALL (LISTADO PAGINADO)
# ===============================
@router.get("/")
def listar_vw_ges_movil(
    patente: Optional[str] = Query(None),
    empresa_id: Optional[int] = Query(None),
    conductor_id: Optional[int] = Query(None),
    contrato_estado: Optional[str] = Query(None),
    con_contrato: Optional[bool] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):

    conn = get_db_connection()

    if not conn:
        raise HTTPException(status_code=500, detail="Error DB")

    cursor = conn.cursor(dictionary=True)

    try:

        where = []
        params = []

        if patente:
            where.append("patente LIKE %s")
            params.append(f"%{patente.strip().upper()}%")

        if empresa_id is not None:
            where.append("empresa_id = %s")
            params.append(empresa_id)

        if conductor_id is not None:
            where.append("conductor_id = %s")
            params.append(conductor_id)

        if contrato_estado:
            where.append("contrato_estado = %s")
            params.append(contrato_estado)

        if con_contrato is True:
            where.append("contrato_id IS NOT NULL")
        elif con_contrato is False:
            where.append("contrato_id IS NULL")

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""

        cursor.execute(
            f"SELECT COUNT(*) AS total FROM VW_GES_MOVIL {where_sql}",
            params
        )

        total = cursor.fetchone()["total"]

        cursor.execute(
            f"""
            SELECT *
            FROM VW_GES_MOVIL
            {where_sql}
            ORDER BY patente ASC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset]
        )

        registros = cursor.fetchall()

        pagina_actual = (offset // limit) + 1 if limit > 0 else 1
        total_paginas = (total + limit - 1) // limit if limit > 0 else 0

        return {
            "registros": registros,
            "paginacion": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "pagina_actual": pagina_actual,
                "total_paginas": total_paginas,
                "tiene_siguiente": offset + limit < total,
                "tiene_anterior": offset > 0,
            },
        }

    except HTTPException:
        raise

    except Error as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        cursor.close()
        conn.close()


# ===============================
# GET BY PATENTE  ⬅️ MOVER ANTES DE /{movil_id}
# ===============================
@router.get("/patente/{patente}")
def obtener_vw_ges_movil_por_patente(patente: str):

    conn = get_db_connection()

    if not conn:
        raise HTTPException(status_code=500, detail="Error DB")

    cursor = conn.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT *
            FROM VW_GES_MOVIL
            WHERE patente = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (patente.strip().upper(),)
        )

        row = cursor.fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="No se encontró registro para la patente indicada"
            )

        return row

    except HTTPException:
        raise

    except Error as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        cursor.close()
        conn.close()


# ===============================
# GET BY ID  ⬅️ VA DESPUÉS
# ===============================
@router.get("/{movil_id}")
def obtener_vw_ges_movil(movil_id: int):

    conn = get_db_connection()

    if not conn:
        raise HTTPException(status_code=500, detail="Error DB")

    cursor = conn.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT *
            FROM VW_GES_MOVIL
            WHERE id = %s
            """,
            (movil_id,)
        )

        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Registro no encontrado")

        return row

    except HTTPException:
        raise

    except Error as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        cursor.close()
        conn.close()