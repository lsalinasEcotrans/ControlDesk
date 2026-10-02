# AUTH_Users.py
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from typing import Optional, Any
import mysql.connector
from mysql.connector import Error
import os
import json
from Database import get_db_connection
from AUTH import get_current_user

router = APIRouter(prefix="/usuarios", tags=["AUTH - Usuarios"])

# ---------------------------
# Pydantic Models
# ---------------------------

class UserBase(BaseModel):
    username: str = Field(..., example="luis.s")
    full_name: Optional[str] = Field(None, example="Luis Salinas")
    role_id: Optional[int] = Field(None, example=2)
    extra_permissions: Optional[Any] = Field(
        None,
        example={"can_edit": True, "sections": ["dashboard", "reportes"]}
    )

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    username: Optional[str] = None
    full_name: Optional[str] = None
    role_id: Optional[int] = None
    extra_permissions: Optional[Any] = None

# ---------------------------
# Endpoints
# ---------------------------

@router.get("")
def get_all_users(current_user: dict = Depends(get_current_user)):
    """
    Lista todos los usuarios con su rol (si existe)
    """
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="No se pudo conectar a la base de datos")

    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT 
            u.id, u.username, u.full_name, u.role_id, r.name AS role_name, u.extra_permissions, 
            u.created_at, u.cargo, u.departamento, u.nexterno, u.correo
        FROM AUTH_USERS u
        LEFT JOIN AUTH_ROLES r ON u.role_id = r.id
        ORDER BY u.id ASC;
    """
    try:
        cursor.execute(query)
        result = cursor.fetchall()
        for row in result:
            if isinstance(row["extra_permissions"], str):
                try:
                    row["extra_permissions"] = json.loads(row["extra_permissions"])
                except:
                    row["extra_permissions"] = None
        return result
    except Error as e:
        raise HTTPException(status_code=500, detail=f"Error ejecutando query: {e}")
    finally:
        cursor.close()
        conn.close()


@router.get("/{user_id}")
def get_user_by_id(user_id: int = Path(..., description="ID del usuario")):
    """
    Obtiene un usuario por su ID
    """
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="No se pudo conectar a la base de datos")

    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT u.id, u.username, u.full_name, u.role_id, r.name AS role_name,
               u.extra_permissions, u.created_at, u.cargo, u.departamento, u.nexterno, u.correo
        FROM AUTH_USERS u
        LEFT JOIN AUTH_ROLES r ON u.role_id = r.id
        WHERE u.id = %s;
    """
    try:
        cursor.execute(query, (user_id,))
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        if isinstance(result["extra_permissions"], str):
            try:
                result["extra_permissions"] = json.loads(result["extra_permissions"])
            except:
                result["extra_permissions"] = None
        return result
    except Error as e:
        raise HTTPException(status_code=500, detail=f"Error ejecutando query: {e}")
    finally:
        cursor.close()
        conn.close()


@router.post("")
def create_user(user: UserCreate):
    """
    Crea un nuevo usuario
    """
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="No se pudo conectar a la base de datos")

    cursor = conn.cursor()
    query = """
        INSERT INTO AUTH_USERS (username, full_name, role_id, extra_permissions)
        VALUES (%s, %s, %s, %s);
    """
    try:
        extra_json = json.dumps(user.extra_permissions) if user.extra_permissions else None
        cursor.execute(query, (user.username, user.full_name, user.role_id, extra_json))
        conn.commit()
        return {"message": "Usuario creado exitosamente", "user_id": cursor.lastrowid}
    except Error as e:
        conn.rollback()
        if "Duplicate entry" in str(e):
            raise HTTPException(status_code=400, detail="El nombre de usuario ya existe")
        raise HTTPException(status_code=500, detail=f"Error insertando usuario: {e}")
    finally:
        cursor.close()
        conn.close()


@router.put("/{user_id}")
def update_user(user_id: int, user: UserUpdate):
    """
    Actualiza un usuario existente
    """
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="No se pudo conectar a la base de datos")

    cursor = conn.cursor()
    fields = []
    values = []

    for field, value in user.dict(exclude_unset=True).items():
        if field == "extra_permissions" and value is not None:
            value = json.dumps(value)
        fields.append(f"{field} = %s")
        values.append(value)

    if not fields:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")

    query = f"UPDATE AUTH_USERS SET {', '.join(fields)} WHERE id = %s"
    values.append(user_id)

    try:
        cursor.execute(query, tuple(values))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        return {"message": "Usuario actualizado correctamente"}
    except Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error actualizando usuario: {e}")
    finally:
        cursor.close()
        conn.close()


@router.delete("/{user_id}")
def delete_user(user_id: int):
    """
    Elimina un usuario por su ID
    """
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="No se pudo conectar a la base de datos")

    cursor = conn.cursor()
    query = "DELETE FROM AUTH_USERS WHERE id = %s;"
    try:
        cursor.execute(query, (user_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        return {"message": "Usuario eliminado correctamente"}
    except Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error eliminando usuario: {e}")
    finally:
        cursor.close()
        conn.close()
