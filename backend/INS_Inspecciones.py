# INS_Inspecciones.py
import os
import json
from datetime import datetime, timezone, timedelta
from typing import Optional

import mysql.connector
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Query
from fastapi.responses import Response

from INS_OneDrive import upload_photos_to_onedrive, get_photo_content

router = APIRouter(prefix="/inspecciones", tags=["INS - Inspecciones"])


# ── DB helper ─────────────────────────────────────────────────────────────────

def get_connection():
    return mysql.connector.connect(
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASS"),
        database=os.environ.get("DB_NAME"),
        unix_socket=os.environ.get("DB_SOCKET"),
    )


# ── Helpers ───────────────────────────────────────────────────────────────────
def _parse_json_fields(row: dict) -> dict:
    for field in ("datos_vehiculo", "datos_conductor", "datos_inspeccion"):
        if isinstance(row.get(field), str):
            try:
                row[field] = json.loads(row[field])
            except Exception:
                row[field] = {}
    for field in ("fecha_creacion", "fecha_proxima", "updated_at"):
        if row.get(field) and hasattr(row[field], "isoformat"):
            row[field] = row[field].isoformat()
    return row


def _determinar_estado(datos: dict) -> tuple[str, Optional[str]]:
    motivos = []

    seguridad_map = {
        "cinturonDelantero":    "Cinturón delantero",
        "cinturonTrasero":      "Cinturón trasero",
        "chalecoReflectante":   "Chaleco reflectante",
        "botiquin":             "Botiquín",
        "ruedaRepuesto":        "Rueda de repuesto",
        "triangulosEmergencia": "Triángulos de emergencia",
    }
    faltantes_seg = [v for k, v in seguridad_map.items() if not datos.get(k)]
    if faltantes_seg:
        motivos.append(f"Seguridad incompleta: {', '.join(faltantes_seg)}")

    luces_map = {
        "luzPatenteTransera":   "Luz patente trasera",
        "lucesIntermitentes":   "Luces intermitentes",
        "lucesEstacionamiento": "Luces estacionamiento",
        "lucesFrenos":          "Luces de frenos",
        "lucesMarchaAtras":     "Luces marcha atrás",
        "lucesBajas":           "Luces bajas",
        "lucesAltas":           "Luces altas",
    }
    faltantes_luz = [v for k, v in luces_map.items() if not datos.get(k)]
    if faltantes_luz:
        motivos.append(f"Luces con falla: {', '.join(faltantes_luz)}")

    if datos.get("neumaticos", 0) < 50:
        motivos.append(f"Neumáticos en estado crítico ({datos.get('neumaticos')}%)")
    if datos.get("frenos", 0) < 50:
        motivos.append(f"Frenos en estado crítico ({datos.get('frenos')}%)")
    if datos.get("carroceria") == "Malo":
        motivos.append("Carrocería en mal estado")
    if not datos.get("kilometraje"):
        motivos.append("Kilometraje no ingresado")

    extintor = datos.get("extintorFecha", "")
    if extintor:
        try:
            venc = datetime.strptime(extintor, "%Y-%m-%d").date()
            if venc < datetime.now(timezone.utc).date():
                motivos.append(f"Extintor vencido ({extintor})")
        except ValueError:
            motivos.append("Fecha de extintor inválida")
    else:
        motivos.append("Fecha de extintor no ingresada")

    return ("rechazado", " | ".join(motivos)) if motivos else ("aprobado", None)


def _fecha_proxima(estado: str) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=60 if estado == "aprobado" else 7)


# ── GET /foto/{item_id} — Proxy autenticado para imágenes OneDrive ────────────
@router.get("/foto/{item_id}")
async def proxy_foto(item_id: str):
    """
    Sirve la imagen de OneDrive autenticándose con Graph API.
    El frontend usa /inspecciones/foto/<item_id> como src de las imágenes.
    """
    try:
        content, content_type = await get_photo_content(item_id)
        return Response(
            content=content,
            media_type=content_type,
            headers={"Cache-Control": "private, max-age=3600"},
        )
    except Exception as e:
        print(f"[Proxy foto] Error: {e}")
        raise HTTPException(status_code=404, detail="Foto no encontrada")


# ── GET / — Lista con filtros y paginación ────────────────────────────────────
@router.get("/")
def listar_inspecciones(
    page:        int = Query(1,  ge=1),
    page_size:   int = Query(20, ge=1, le=100),
    search:      Optional[str] = Query(None),
    estado:      Optional[str] = Query(None),
    fecha_desde: Optional[str] = Query(None),
    fecha_hasta: Optional[str] = Query(None),
):
    conditions, params = [], []

    if search:
        like = f"%{search}%"
        conditions.append("(registration LIKE %s OR callsign LIKE %s OR forename LIKE %s OR surname LIKE %s)")
        params.extend([like, like, like, like])
    if estado and estado in ("aprobado", "rechazado"):
        conditions.append("estado = %s")
        params.append(estado)
    if fecha_desde:
        conditions.append("DATE(fecha_creacion) >= %s")
        params.append(fecha_desde)
    if fecha_hasta:
        conditions.append("DATE(fecha_creacion) <= %s")
        params.append(fecha_hasta)

    where  = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    offset = (page - 1) * page_size

    try:
        conn   = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(f"SELECT COUNT(*) as total FROM INS_INSPECCION {where}", params)
        total = cursor.fetchone()["total"]
        cursor.execute(
            f"""
            SELECT id, callsign, registration, make, model, year_manufacture,
                   forename, surname, cpc_card_number, estado, motivo_rechazo,
                   fecha_creacion, fecha_proxima,
                   datos_vehiculo, datos_conductor, datos_inspeccion
            FROM INS_INSPECCION {where}
            ORDER BY fecha_creacion DESC
            LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        items = [_parse_json_fields(row) for row in cursor.fetchall()]
    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"Error BD: {e}")
    finally:
        cursor.close()
        conn.close()

    return {"total": total, "page": page, "page_size": page_size, "items": items}


# ── GET /{id} — Detalle ───────────────────────────────────────────────────────
@router.get("/{inspeccion_id}")
def obtener_inspeccion(inspeccion_id: int):
    try:
        conn   = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM INS_INSPECCION WHERE id = %s", (inspeccion_id,))
        row = cursor.fetchone()
    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"Error BD: {e}")
    finally:
        cursor.close()
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Inspección no encontrada")

    return _parse_json_fields(row)


# ── PUT /{id} — Editar y recalcular estado ────────────────────────────────────
@router.put("/{inspeccion_id}")
def actualizar_inspeccion(inspeccion_id: int, body: dict):
    # Obtener datos de inspección (obligatorio)
    datos_i = body.get("datos_inspeccion")
    if not datos_i or not isinstance(datos_i, dict):
        raise HTTPException(status_code=422, detail="datos_inspeccion requerido")

    # Obtener fecha_creacion si viene en el body (opcional)
    fecha_creacion_raw = body.get("fecha_creacion")
    fecha_creacion = None
    
    # Validar formato de fecha si viene
    if fecha_creacion_raw:
        try:
            # Intentar parsear la fecha (espera formato ISO: "2024-01-15T14:30")
            if isinstance(fecha_creacion_raw, str):
                # Si viene de datetime-local input, tiene formato "YYYY-MM-DDTHH:mm"
                # Convertir a datetime completo
                if len(fecha_creacion_raw) == 16:  # "2024-01-15T14:30"
                    fecha_creacion = datetime.fromisoformat(fecha_creacion_raw)
                else:
                    fecha_creacion = datetime.fromisoformat(fecha_creacion_raw)
            elif isinstance(fecha_creacion_raw, datetime):
                fecha_creacion = fecha_creacion_raw
        except ValueError:
            raise HTTPException(status_code=422, detail="Formato de fecha_creacion inválido. Use ISO format")
    
    # Recalcular estado basado en los nuevos datos
    estado, motivo_rechazo = _determinar_estado(datos_i)
    fecha_proxima = _fecha_proxima(estado)

    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Construir query dinámica
        if fecha_creacion:
            cursor.execute(
                """
                UPDATE INS_INSPECCION
                SET datos_inspeccion = %s, 
                    estado = %s,
                    motivo_rechazo = %s, 
                    fecha_proxima = %s,
                    fecha_creacion = %s
                WHERE id = %s
                """,
                (json.dumps(datos_i, ensure_ascii=False), 
                 estado, 
                 motivo_rechazo, 
                 fecha_proxima, 
                 fecha_creacion, 
                 inspeccion_id),
            )
        else:
            cursor.execute(
                """
                UPDATE INS_INSPECCION
                SET datos_inspeccion = %s, 
                    estado = %s,
                    motivo_rechazo = %s, 
                    fecha_proxima = %s
                WHERE id = %s
                """,
                (json.dumps(datos_i, ensure_ascii=False), 
                 estado, 
                 motivo_rechazo, 
                 fecha_proxima, 
                 inspeccion_id),
            )
        
        conn.commit()
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Inspección no encontrada")
            
    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"Error BD: {e}")
    finally:
        cursor.close()
        conn.close()

    response = {
        "id": inspeccion_id, 
        "estado": estado, 
        "motivo_rechazo": motivo_rechazo, 
        "fecha_proxima": fecha_proxima.isoformat()
    }
    
    if fecha_creacion:
        response["fecha_creacion"] = fecha_creacion.isoformat() if isinstance(fecha_creacion, datetime) else fecha_creacion
    
    return response

# ── POST / — Crear nueva inspección ──────────────────────────────────────────
@router.post("/", status_code=201)
async def crear_inspeccion(
    registration:     str = Form(...),
    callsign:         str = Form(""),
    make:             str = Form(""),
    model:            str = Form(""),
    year_manufacture: str = Form(""),
    forename:         str = Form(""),
    surname:          str = Form(""),
    cpc_card_number:  str = Form(""),
    datos_vehiculo:   str = Form("{}"),
    datos_conductor:  str = Form("{}"),
    datos_inspeccion: str = Form("{}"),
    fotos: list[UploadFile] = File(default=[]),
):
    try:
        datos_v = json.loads(datos_vehiculo)
        datos_c = json.loads(datos_conductor)
        datos_i = json.loads(datos_inspeccion)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=422, detail=f"JSON inválido: {e}")

    # Subir fotos — se guardan como lista de {item_id, filename, path}
    foto_items: list[dict] = []
    if fotos:
        archivos = []
        for foto in fotos:
            contenido = await foto.read()
            if contenido:
                nombre = (foto.filename or "foto.jpg").replace(" ", "_")
                archivos.append((nombre, contenido))
        if archivos:
            try:
                foto_items = await upload_photos_to_onedrive(registration, archivos)
            except Exception as e:
                print(f"[OneDrive] Error: {e}")

    datos_i["fotos"] = foto_items
    estado, motivo_rechazo = _determinar_estado(datos_i)
    fecha_proxima = _fecha_proxima(estado)

    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO INS_INSPECCION (
                callsign, registration, make, model, year_manufacture,
                forename, surname, cpc_card_number,
                estado, motivo_rechazo,
                datos_vehiculo, datos_conductor, datos_inspeccion, fecha_proxima
            ) VALUES (%s,%s,%s,%s,%s, %s,%s,%s, %s,%s, %s,%s,%s, %s)
            """,
            (
                callsign or None, registration, make or None, model or None,
                int(year_manufacture) if year_manufacture.isdigit() else None,
                forename or None, surname or None, cpc_card_number or None,
                estado, motivo_rechazo,
                json.dumps(datos_v, ensure_ascii=False),
                json.dumps(datos_c, ensure_ascii=False),
                json.dumps(datos_i, ensure_ascii=False),
                fecha_proxima,
            ),
        )
        conn.commit()
        inspeccion_id = cursor.lastrowid
    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"Error BD: {e}")
    finally:
        cursor.close()
        conn.close()

    return {
        "id":            inspeccion_id,
        "estado":        estado,
        "motivo_rechazo": motivo_rechazo,
        "fecha_proxima": fecha_proxima.isoformat(),
        "fotos_subidas": len(foto_items),
    }