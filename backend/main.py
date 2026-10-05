# main.py
from fastapi import FastAPI
# Rutas Asociadas
import time

inicio = time.perf_counter()

def log_import(nombre):
    print(f"[IMPORT] {nombre} - {time.perf_counter() - inicio:.3f}s")


from fastapi import FastAPI
log_import("fastapi")

from AUTH_Roles import router as AUTH_Roles
log_import("AUTH_Roles")

from AUTH_Users import router as AUTH_Users
log_import("AUTH_Users")

from AUTH_Validate import router as AUTH_Validate
log_import("AUTH_Validate")

from OWA_Headers_test import router as OWA_Headers_test
log_import("OWA_Headers_test")

from OWA_Headers_v2 import router as OWA_Headers_v2
log_import("OWA_Headers_v2")

from OWA_Bodys import router as OWA_Bodys
log_import("OWA_Bodys")

from INFO_Pasajero import router as INFO_Pasajero
log_import("INFO_Pasajero")

from FLT_Manager import router as FLT_Manager
log_import("FLT_Manager")

from INS_Inspecciones import router as INS_Inspecciones
log_import("INS_Inspecciones")

from CM_Empresa import router as CM_Empresa
log_import("CM_Empresa")

from CM_Pasajero import router as CM_Pasajero
log_import("CM_Pasajero")

from CRUD_AUTH_Portal import router as CRUD_AUTH_Portal
log_import("CRUD_AUTH_Portal")

from CAT_Bancos import router as CAT_Bancos
log_import("CAT_Bancos")

from CAT_Regiones import router as CAT_Regiones
log_import("CAT_Regiones")

from CAT_Comunas import router as CAT_Comunas
log_import("CAT_Comunas")

from CAT_Tipos_Contrato import router as CAT_Tipos_Contrato
log_import("CAT_Tipos_Contrato")

from CAT_Cobro_Aplicaciones import router as CAT_Cobro_Aplicaciones
log_import("CAT_Cobro_Aplicaciones")

from GES_Pre_Aprobacion import router as GES_Pre_Aprobacion
log_import("GES_Pre_Aprobacion")

from GES_Crear_Movil import router as ges_moviles_router
log_import("GES_Crear_Movil")

from CAT_Documentos_Adicionales import router as CAT_Documentos_Adicionales
log_import("CAT_Documentos_Adicionales")

from GES_Pre_Contratos import router as GES_Pre_Contratos
log_import("GES_Pre_Contratos")

from GES_Valida_Contratos import router as GES_Valida_Contratos
log_import("GES_Valida_Contratos")

from GES_Firmas import router as GES_Firmas
log_import("GES_Firmas")

from VIEW_Ficha_Ingreso import router as VIEW_Ficha_Ingreso
log_import("VIEW_Ficha_Ingreso")

# VISTAS PARA INTRANET
from VIEW_Ficha_Ingreso import router as VIEW_Ficha_Ingreso

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Ecotrans API", version="1.0")

origins = [
    "http://localhost:3000",
    "https://ecotrans-intranet-822834268126.southamerica-west1.run.app",  # <-- frontend
    "https://ecotrans-intranet-370980788525.europe-west1.run.app",        # <-- API
    "https://intranet-next-822834268126.us-central1.run.app", # nueva url
    "https://intranet2.ecotranschile.cl",
    "https://intranet2-680442911672.us-central1.run.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar routers
app.include_router(AUTH_Roles)
app.include_router(AUTH_Users)
app.include_router(AUTH_Validate)
app.include_router(OWA_Headers_test)
app.include_router(OWA_Headers_v2)
app.include_router(OWA_Bodys)
app.include_router(INFO_Pasajero)
app.include_router(FLT_Manager)
app.include_router(INS_Inspecciones)
app.include_router(CM_Empresa)
app.include_router(CM_Pasajero)
app.include_router(CRUD_AUTH_Portal)
app.include_router(CAT_Bancos)
app.include_router(CAT_Regiones)
app.include_router(CAT_Comunas)
app.include_router(CAT_Tipos_Contrato)
app.include_router(CAT_Cobro_Aplicaciones)
app.include_router(GES_Pre_Aprobacion)
app.include_router(ges_moviles_router)
app.include_router(CAT_Documentos_Adicionales)
app.include_router(GES_Pre_Contratos)
app.include_router(GES_Valida_Contratos)
app.include_router(GES_Firmas)

# VISTAS
app.include_router(VIEW_Ficha_Ingreso)

@app.get("/health")
def health_check():
    return {"status": "ok"}
