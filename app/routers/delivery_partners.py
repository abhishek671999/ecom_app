"""
routers/delivery_partners.py
----------------------------
Full CRUD endpoints for the delivery_partners table.
"""

from fastapi import APIRouter, Depends, HTTPException
import MySQLdb

from app.db.connection import get_db, get_cursor
from app.models.schemas import (
    DeliveryPartnerCreate, DeliveryPartnerUpdate, DeliveryPartnerResponse,
)

router = APIRouter(prefix="/delivery-partners", tags=["Delivery Partners"])


@router.get("/", response_model=list[DeliveryPartnerResponse])
def list_delivery_partners(
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: MySQLdb.Connection = Depends(get_db),
):
    """List delivery partners. Filter by status (available | on_trip | offline)."""
    sql = "SELECT * FROM delivery_partners WHERE 1=1"
    params = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    sql += " ORDER BY name LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    with get_cursor(db) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


@router.get("/available", response_model=list[DeliveryPartnerResponse])
def list_available_partners(db: MySQLdb.Connection = Depends(get_db)):
    """Shortcut — list only available delivery partners."""
    with get_cursor(db) as cur:
        cur.execute(
            "SELECT * FROM delivery_partners WHERE status = 'available' ORDER BY name"
        )
        return cur.fetchall()


@router.get("/{partner_id}", response_model=DeliveryPartnerResponse)
def get_delivery_partner(partner_id: int, db: MySQLdb.Connection = Depends(get_db)):
    """Get a single delivery partner by ID."""
    with get_cursor(db) as cur:
        cur.execute(
            "SELECT * FROM delivery_partners WHERE id = %s", (partner_id,)
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Delivery partner not found")
    return row


@router.post("/", response_model=DeliveryPartnerResponse, status_code=201)
def create_delivery_partner(
    payload: DeliveryPartnerCreate,
    db: MySQLdb.Connection = Depends(get_db),
):
    """Register a new delivery partner."""
    sql = """
        INSERT INTO delivery_partners (address_id, name, mobile_number, status)
        VALUES (%s, %s, %s, %s)
    """
    try:
        with get_cursor(db) as cur:
            cur.execute(sql, (
                payload.address_id, payload.name,
                payload.mobile_number, payload.status,
            ))
            new_id = cur.lastrowid
            cur.execute(
                "SELECT * FROM delivery_partners WHERE id = %s", (new_id,)
            )
            return cur.fetchone()
    except MySQLdb.IntegrityError as e:
        raise HTTPException(status_code=409, detail=f"Conflict: {e.args[1]}")


@router.put("/{partner_id}", response_model=DeliveryPartnerResponse)
def update_delivery_partner(
    partner_id: int,
    payload: DeliveryPartnerUpdate,
    db: MySQLdb.Connection = Depends(get_db),
):
    """Update delivery partner details or status."""
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"{col} = %s" for col in updates)
    sql = f"UPDATE delivery_partners SET {set_clause} WHERE id = %s"

    with get_cursor(db) as cur:
        cur.execute(sql, (*updates.values(), partner_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Delivery partner not found")
        cur.execute(
            "SELECT * FROM delivery_partners WHERE id = %s", (partner_id,)
        )
        return cur.fetchone()


@router.delete("/{partner_id}", status_code=204)
def deactivate_delivery_partner(
    partner_id: int, db: MySQLdb.Connection = Depends(get_db)
):
    """Soft delete — sets status to suspended."""
    with get_cursor(db) as cur:
        cur.execute(
            "UPDATE delivery_partners SET status = 'suspended' WHERE id = %s",
            (partner_id,)
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Delivery partner not found")