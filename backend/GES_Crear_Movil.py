import os
import json
import logging

from datetime import datetime
from typing import Optional

import httpx

from fastapi import (
    APIRouter,
    HTTPException,
    UploadFile,
    File,
    Form,
    Request,
)

import mysql.connector
from mysql.connector import Error


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("GES_Crear_Movil")


# =========================================================
# ROUTER
# =========================================================

router = APIRouter(
    prefix="/GES_Crear_Movil",
    tags=["GES - Crear_Movil"]
)


# =========================================================
# VARIABLES BASE DE DATOS
# =========================================================

DB_USER = os.environ.get("DB_USER")
DB_PASS = os.environ.get("DB_PASS")
DB_NAME = os.environ.get("DB_NAME")
DB_SOCKET = os.environ.get("DB_SOCKET")


# =========================================================
# VARIABLES ONEDRIVE / MICROSOFT GRAPH
# =========================================================

TENANT_ID = os.environ.get("TENANT_ID", "")
CLIENT_ID = os.environ.get("CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "")
USER_EMAIL = os.environ.get("USER_EMAIL", "")

ONEDRIVE_ROOT = "Registros"

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

UPLOAD_TIMEOUT = 120

TOKEN_URL = (
    f"https://login.microsoftonline.com/"
    f"{TENANT_ID}/oauth2/v2.0/token"
)

GRAPH_URL = "https://graph.microsoft.com/v1.0"


# =========================================================
# CONEXIÓN BASE DE DATOS
# =========================================================

def GES_Crear_Movil_Conexion_DB():

    try:

        connection = mysql.connector.connect(
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME,
            unix_socket=DB_SOCKET,
        )

        if not connection.is_connected():

            raise HTTPException(
                status_code=500,
                detail="No fue posible conectar a la base de datos"
            )

        logger.info(
            "Conexión a MySQL establecida correctamente"
        )

        return connection

    except Error as e:

        logger.error(
            f"❌ Error conexión MySQL: {e}"
        )

        raise HTTPException(
            status_code=500,
            detail="Error de conexión con la base de datos"
        )


# =========================================================
# OBTENER TOKEN MICROSOFT GRAPH
# =========================================================

async def GES_Crear_Movil_Get_Token() -> str:

    if not TENANT_ID:

        raise HTTPException(
            status_code=500,
            detail="TENANT_ID no está configurado"
        )

    if not CLIENT_ID:

        raise HTTPException(
            status_code=500,
            detail="CLIENT_ID no está configurado"
        )

    if not CLIENT_SECRET:

        raise HTTPException(
            status_code=500,
            detail="CLIENT_SECRET no está configurado"
        )

    if not USER_EMAIL:

        raise HTTPException(
            status_code=500,
            detail="USER_EMAIL no está configurado"
        )

    try:

        async with httpx.AsyncClient(timeout=30) as client:

            response = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "scope": "https://graph.microsoft.com/.default",
                },
            )

        if response.status_code != 200:

            logger.error(
                "❌ Error obteniendo token Microsoft Graph: "
                f"{response.text}"
            )

            raise HTTPException(
                status_code=500,
                detail="No fue posible obtener el token de OneDrive"
            )

        token_data = response.json()

        access_token = token_data.get(
            "access_token"
        )

        if not access_token:

            logger.error(
                "❌ Microsoft Graph no devolvió access_token"
            )

            raise HTTPException(
                status_code=500,
                detail="Microsoft Graph no devolvió el token de acceso"
            )

        logger.info(
            "✅ Token Microsoft Graph obtenido correctamente"
        )

        return access_token

    except HTTPException:

        raise

    except Exception as e:

        logger.error(
            f"❌ Error obteniendo token OneDrive: {e}",
            exc_info=True
        )

        raise HTTPException(
            status_code=500,
            detail="Error al conectar con Microsoft Graph"
        )


# =========================================================
# CREAR / OBTENER CARPETAS ONEDRIVE
# =========================================================

async def GES_Crear_Movil_Ensure_Folder(
    client: httpx.AsyncClient,
    headers: dict,
    folder_path: str
) -> str:

    parts = folder_path.strip("/").split("/")

    current_path = ""

    folder_id = "root"

    for part in parts:

        current_path = (
            f"{current_path}/{part}"
            if current_path
            else part
        )

        # -------------------------------------------------
        # BUSCAR CARPETA
        # -------------------------------------------------

        url = (
            f"{GRAPH_URL}/users/{USER_EMAIL}"
            f"/drive/root:/{current_path}"
        )

        response = await client.get(
            url,
            headers=headers,
        )

        # -------------------------------------------------
        # CARPETA EXISTE
        # -------------------------------------------------

        if response.status_code == 200:

            folder_id = response.json()["id"]

            logger.info(
                f"📁 Carpeta encontrada: {current_path}"
            )

        # -------------------------------------------------
        # CARPETA NO EXISTE
        # -------------------------------------------------

        elif response.status_code == 404:

            path_parts = current_path.split("/")

            parent_path = "/".join(
                path_parts[:-1]
            )

            if not parent_path:

                create_url = (
                    f"{GRAPH_URL}/users/{USER_EMAIL}"
                    f"/drive/root/children"
                )

            else:

                create_url = (
                    f"{GRAPH_URL}/users/{USER_EMAIL}"
                    f"/drive/root:/{parent_path}:/children"
                )

            create_response = await client.post(
                create_url,
                headers={
                    **headers,
                    "Content-Type": "application/json",
                },
                json={
                    "name": part,
                    "folder": {},
                    "@microsoft.graph.conflictBehavior": "rename",
                },
            )

            if create_response.status_code not in (200, 201):

                logger.error(
                    f"❌ Error creando carpeta "
                    f"{current_path}: "
                    f"{create_response.text}"
                )

                raise HTTPException(
                    status_code=500,
                    detail=(
                        f"No fue posible crear la carpeta "
                        f"{current_path} en OneDrive"
                    ),
                )

            folder_id = create_response.json()["id"]

            logger.info(
                f"📁 Carpeta creada: {current_path}"
            )

        # -------------------------------------------------
        # OTRO ERROR
        # -------------------------------------------------

        else:

            logger.error(
                f"❌ Error consultando carpeta "
                f"{current_path}: "
                f"{response.status_code} - "
                f"{response.text}"
            )

            raise HTTPException(
                status_code=500,
                detail=(
                    "Error accediendo a las carpetas "
                    "de OneDrive"
                ),
            )

    return folder_id


# =========================================================
# SUBIR DOCUMENTOS A ONEDRIVE
# =========================================================

async def GES_Crear_Movil_Subir_Documentos(
    patente: str,
    fecha_ingreso: datetime,
    documentos: list[tuple[str, Optional[UploadFile]]],
) -> list[dict]:

    # -----------------------------------------------------
    # FILTRAR DOCUMENTOS VACÍOS
    # -----------------------------------------------------

    documentos_validos = [
        (nombre, archivo)
        for nombre, archivo in documentos
        if archivo is not None
    ]

    if not documentos_validos:

        logger.info(
            "ℹ️ No se recibieron documentos para subir"
        )

        return []

    # -----------------------------------------------------
    # VALIDAR PATENTE
    # -----------------------------------------------------

    patente = (
        patente
        .strip()
        .upper()
    )

    if not patente:

        raise HTTPException(
            status_code=400,
            detail="La patente es obligatoria para subir documentos"
        )

    # -----------------------------------------------------
    # OBTENER TOKEN
    # -----------------------------------------------------

    token = await GES_Crear_Movil_Get_Token()

    headers = {
        "Authorization": f"Bearer {token}"
    }

    # -----------------------------------------------------
    # CREAR RUTA
    # -----------------------------------------------------

    fecha_str = fecha_ingreso.strftime(
        "%Y-%m-%d"
    )

    folder_path = (
        f"{ONEDRIVE_ROOT}/"
        f"{patente}/"
        f"{fecha_str}-DOC-INGRESO"
    )

    logger.info(
        f"📁 Carpeta DOC-INGRESO: {folder_path}"
    )

    resultados = []

    # -----------------------------------------------------
    # CLIENTE HTTP
    # -----------------------------------------------------

    async with httpx.AsyncClient(
        timeout=UPLOAD_TIMEOUT
    ) as client:

        # -------------------------------------------------
        # ASEGURAR CARPETA
        # -------------------------------------------------

        folder_id = await GES_Crear_Movil_Ensure_Folder(
            client=client,
            headers=headers,
            folder_path=folder_path,
        )

        # -------------------------------------------------
        # SUBIR CADA DOCUMENTO
        # -------------------------------------------------

        for nombre_documento, archivo in documentos_validos:

            if archivo is None:
                continue

            try:

                contenido = await archivo.read()

                # -----------------------------------------
                # VALIDAR ARCHIVO VACÍO
                # -----------------------------------------

                if not contenido:

                    logger.warning(
                        f"⚠️ Documento vacío: "
                        f"{nombre_documento}"
                    )

                    continue

                # -----------------------------------------
                # VALIDAR TAMAÑO
                # -----------------------------------------

                if len(contenido) > MAX_FILE_SIZE:

                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"El documento "
                            f"{nombre_documento} "
                            f"excede el tamaño máximo "
                            f"permitido de 10 MB"
                        ),
                    )

                # -----------------------------------------
                # EXTENSIÓN
                # -----------------------------------------

                extension = ""

                if archivo.filename:

                    nombre_original = archivo.filename

                    if "." in nombre_original:

                        extension = (
                            "."
                            + nombre_original
                            .rsplit(".", 1)[1]
                            .lower()
                        )

                if not extension:

                    extension = ".pdf"

                # -----------------------------------------
                # NOMBRE FINAL
                # -----------------------------------------

                filename = (
                    f"{patente}_"
                    f"{nombre_documento}"
                    f"{extension}"
                )

                filename = (
                    filename
                    .replace("/", "_")
                    .replace("\\", "_")
                )

                # -----------------------------------------
                # URL UPLOAD GRAPH
                # -----------------------------------------

                upload_url = (
                    f"{GRAPH_URL}/users/{USER_EMAIL}"
                    f"/drive/items/{folder_id}:/"
                    f"{filename}:/content"
                )

                content_type = (
                    archivo.content_type
                    or "application/octet-stream"
                )

                logger.info(
                    f"⬆️ Subiendo documento: "
                    f"{filename}"
                )

                # -----------------------------------------
                # SUBIR
                # -----------------------------------------

                response = await client.put(
                    upload_url,
                    headers={
                        **headers,
                        "Content-Type": content_type,
                    },
                    content=contenido,
                )

                # -----------------------------------------
                # VALIDAR RESPUESTA
                # -----------------------------------------

                if response.status_code not in (200, 201):

                    logger.error(
                        f"❌ Error subiendo "
                        f"{filename}: "
                        f"{response.status_code} - "
                        f"{response.text}"
                    )

                    raise HTTPException(
                        status_code=500,
                        detail=(
                            f"No fue posible subir "
                            f"el documento "
                            f"{nombre_documento}"
                        ),
                    )

                # -----------------------------------------
                # RESPUESTA GRAPH
                # -----------------------------------------

                response_data = response.json()

                item_id = response_data.get(
                    "id",
                    ""
                )

                resultados.append({
                    "nombre_documento": nombre_documento,
                    "filename": filename,
                    "item_id": item_id,
                    "path": (
                        f"{folder_path}/"
                        f"{filename}"
                    ),
                    "content_type": content_type,
                })

                logger.info(
                    f"✅ Documento subido: "
                    f"{filename}"
                )

            finally:

                await archivo.close()

    logger.info(
        f"✅ Total documentos subidos: "
        f"{len(resultados)}"
    )

    return resultados


# =========================================================
# CREAR MOVIL
# =========================================================

@router.post("/crearmovil")
async def crear_movil(
    request: Request,

    # -----------------------------------------------------
    # JSON DEL FORMULARIO
    # -----------------------------------------------------

    data: str = Form(...),

    # -----------------------------------------------------
    # DOCUMENTOS
    # -----------------------------------------------------

    licencia_conducir: Optional[UploadFile] = File(None),

    revision_tecnica: Optional[UploadFile] = File(None),

    soap: Optional[UploadFile] = File(None),

    seguro_asiento: Optional[UploadFile] = File(None),

    permiso_circulacion: Optional[UploadFile] = File(None),

    carton_recorrido: Optional[UploadFile] = File(None),

    hoja_vida_conductor: Optional[UploadFile] = File(None),

    certificado_antecedentes: Optional[UploadFile] = File(None),

    poder_notarial: Optional[UploadFile] = File(None),

    poder_simple: Optional[UploadFile] = File(None),

    padron: Optional[UploadFile] = File(None),

    cedula_identidad_dueno: Optional[UploadFile] = File(None),

    cedula_identidad_conductor: Optional[UploadFile] = File(None),

):

    conn = None

    cursor = None

    try:

        # =================================================
        # CONVERTIR JSON
        # =================================================

        try:

            data_dict = json.loads(data)

        except json.JSONDecodeError:

            raise HTTPException(
                status_code=400,
                detail="El campo data contiene un JSON inválido"
            )

        # =================================================
        # VALIDAR JSON
        # =================================================

        if not data_dict:

            raise HTTPException(
                status_code=400,
                detail="El JSON no puede estar vacío"
            )

        # =================================================
        # VALIDAR USUARIO
        # =================================================

        usuario_id = data_dict.get(
            "usuario_id"
        )

        if not usuario_id:

            raise HTTPException(
                status_code=400,
                detail="usuario_id es obligatorio"
            )

        # =================================================
        # OBTENER PATENTE
        # =================================================

        patente = (
            data_dict
            .get("vehiculo", {})
            .get("patente", "")
        )

        patente = (
            patente
            .strip()
            .upper()
        )

        if not patente:

            raise HTTPException(
                status_code=400,
                detail="La patente es obligatoria"
            )

        # =================================================
        # CONVERTIR JSON
        # =================================================

        json_data = json.dumps(
            data_dict,
            ensure_ascii=False
        )

        logger.info(
            "Ejecutando SP_GES_CREAR_MOVIL - "
            f"usuario_id: {usuario_id} - "
            f"patente: {patente}"
        )

        # =================================================
        # CONECTAR BD
        # =================================================

        conn = GES_Crear_Movil_Conexion_DB()

        cursor = conn.cursor()

        # =================================================
        # EJECUTAR PROCEDIMIENTO
        # =================================================

        cursor.callproc(
            "SP_GES_CREAR_MOVIL",
            [json_data]
        )

        # =================================================
        # OBTENER RESULTADO
        # =================================================

        result = None

        for stored_result in cursor.stored_results():

            result = stored_result.fetchall()

            break

        # =================================================
        # VALIDAR RESULTADO
        # =================================================

        if not result:

            logger.error(
                "SP_GES_CREAR_MOVIL no devolvió resultado"
            )

            raise HTTPException(
                status_code=500,
                detail="El procedimiento no devolvió información"
            )

        # =================================================
        # CONFIRMAR TRANSACCIÓN
        # =================================================

        conn.commit()

        logger.info(
            "✅ Móvil creado correctamente - "
            f"usuario_id: {usuario_id} - "
            f"patente: {patente}"
        )

        # =================================================
        # DOCUMENTOS ESTÁTICOS
        # =================================================

        documentos = [

            (
                "licencia_conducir",
                licencia_conducir
            ),

            (
                "revision_tecnica",
                revision_tecnica
            ),

            (
                "soap",
                soap
            ),

            (
                "seguro_asiento",
                seguro_asiento
            ),

            (
                "permiso_circulacion",
                permiso_circulacion
            ),

            (
                "carton_recorrido",
                carton_recorrido
            ),

            (
                "hoja_vida_conductor",
                hoja_vida_conductor
            ),

            (
                "certificado_antecedentes",
                certificado_antecedentes
            ),

            (
                "poder_notarial",
                poder_notarial
            ),

            (
                "poder_simple",
                poder_simple
            ),

            (
                "padron",
                padron
            ),

            (
                "cedula_identidad_dueno",
                cedula_identidad_dueno
            ),

            (
                "cedula_identidad_conductor",
                cedula_identidad_conductor
            ),

        ]

        # =================================================
        # RESCATAR DOCUMENTOS ADICIONALES DINÁMICOS
        # =================================================

        # Estos campos:
        #
        # documento_adicional_<codigo>
        #
        # no tienen parámetro declarado arriba porque son
        # dinámicos según el catálogo.
        #
        # Por eso se leen directamente desde el formulario.

        form = await request.form()

        for key, value in form.multi_items():

            if (
                key.startswith("documento_adicional_")
                and hasattr(value, "filename")
            ):

                codigo = key[
                    len("documento_adicional_"):
                ]

                documentos.append(
                    (
                        f"adicional_{codigo}",
                        value
                    )
                )

                logger.info(
                    "📄 Documento adicional detectado: "
                    f"{key}"
                )

        # =================================================
        # SUBIR DOCUMENTOS A ONEDRIVE
        # =================================================

        documentos_subidos = (
            await GES_Crear_Movil_Subir_Documentos(
                patente=patente,
                fecha_ingreso=datetime.now(),
                documentos=documentos,
            )
        )

        # =================================================
        # RESPUESTA
        # =================================================

        return {

            "success": True,

            "data": result[0],

            "documentos": documentos_subidos,

        }

    # =====================================================
    # HTTP EXCEPTION
    # =====================================================

    except HTTPException:

        if conn:

            conn.rollback()

        raise

    # =====================================================
    # ERROR MYSQL
    # =====================================================

    except Error as e:

        if conn:

            conn.rollback()

        logger.error(
            f"❌ Error MySQL en crear_movil: {e}",
            exc_info=True
        )

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    # =====================================================
    # ERROR GENERAL
    # =====================================================

    except Exception as e:

        if conn:

            conn.rollback()

        logger.error(
            f"❌ Error en crear_movil: {e}",
            exc_info=True
        )

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    # =====================================================
    # CERRAR RECURSOS
    # =====================================================

    finally:

        if cursor:

            cursor.close()

        if conn:

            conn.close()