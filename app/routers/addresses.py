"""
routers/addresses.py
--------------------
Full CRUD endpoints for the address table.
"""

from fastapi import APIRouter, Depends, HTTPException
import MySQLdb

from app.db.connection import get_db, get_cursor
from app.models.schemas import AddressCreate, AddressUpdate, AddressResponse

router = APIRouter(prefix="/addresses", tags=["Addresses"])


@router.get("/", response_model=list[AddressResponse])
def list_addresses(
    city: str | None = None,
    pincode: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: MySQLdb.Connection = Depends(get_db),
):
    """List all addresses with optional filters by city or pincode."""
    sql = "SELECT * FROM address WHERE 1=1"
    params = []
    if city:
        sql += " AND city = %s"
        params.append(city)
    if pincode:
        sql += " AND pincode = %s"
        params.append(pincode)
    sql += " LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    with get_cursor(db) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


@router.get("/{address_id}", response_model=AddressResponse)
def get_address(address_id: int, db: MySQLdb.Connection = Depends(get_db)):
    """Get a single address by ID."""
    with get_cursor(db) as cur:
        cur.execute("SELECT * FROM address WHERE id = %s", (address_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Address not found")
    return row


@router.post("/", response_model=AddressResponse, status_code=201)
def create_address(payload: AddressCreate, db: MySQLdb.Connection = Depends(get_db)):
    """Create a new address."""
    sql = """
        INSERT INTO address (type, house_number, street, locality, city, pincode)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    with get_cursor(db) as cur:
        cur.execute(sql, (
            payload.type, payload.house_number, payload.street,
            payload.locality, payload.city, payload.pincode,
        ))
        new_id = cur.lastrowid
        cur.execute("SELECT * FROM address WHERE id = %s", (new_id,))
        return cur.fetchone()


@router.put("/{address_id}", response_model=AddressResponse)
def update_address(
    address_id: int,
    payload: AddressUpdate,
    db: MySQLdb.Connection = Depends(get_db),
):
    """Partially update an address."""
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"{col} = %s" for col in updates)
    sql = f"UPDATE address SET {set_clause} WHERE id = %s"

    with get_cursor(db) as cur:
        cur.execute(sql, (*updates.values(), address_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Address not found")
        cur.execute("SELECT * FROM address WHERE id = %s", (address_id,))
        return cur.fetchone()


@router.delete("/{address_id}", status_code=204)
def delete_address(address_id: int, db: MySQLdb.Connection = Depends(get_db)):
    """Delete an address by ID."""
    with get_cursor(db) as cur:
        cur.execute("DELETE FROM address WHERE id = %s", (address_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Address not found")