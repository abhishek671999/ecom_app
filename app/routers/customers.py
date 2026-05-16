"""
routers/customers.py
--------------------
Full CRUD endpoints for the customers table.
"""

from fastapi import APIRouter, Depends, HTTPException
import MySQLdb

from app.db.connection import get_db, get_cursor
from app.models.schemas import CustomerCreate, CustomerUpdate, CustomerResponse

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get("/", response_model=list[CustomerResponse])
def list_customers(
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: MySQLdb.Connection = Depends(get_db),
):
    """List all customers with optional status filter."""
    sql = "SELECT * FROM customers WHERE 1=1"
    params = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    sql += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    with get_cursor(db) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(customer_id: int, db: MySQLdb.Connection = Depends(get_db)):
    """Get a single customer by ID."""
    with get_cursor(db) as cur:
        cur.execute("SELECT * FROM customers WHERE id = %s", (customer_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")
    return row


@router.post("/", response_model=CustomerResponse, status_code=201)
def create_customer(payload: CustomerCreate, db: MySQLdb.Connection = Depends(get_db)):
    """Create a new customer."""
    sql = """
        INSERT INTO customers (address_id, name, mobile_number, email, status)
        VALUES (%s, %s, %s, %s, %s)
    """
    try:
        with get_cursor(db) as cur:
            cur.execute(sql, (
                payload.address_id, payload.name,
                payload.mobile_number, payload.email, payload.status,
            ))
            new_id = cur.lastrowid
            cur.execute("SELECT * FROM customers WHERE id = %s", (new_id,))
            return cur.fetchone()
    except MySQLdb.IntegrityError as e:
        raise HTTPException(status_code=409, detail=f"Conflict: {e.args[1]}")


@router.put("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: int,
    payload: CustomerUpdate,
    db: MySQLdb.Connection = Depends(get_db),
):
    """Partially update a customer."""
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"{col} = %s" for col in updates)
    sql = f"UPDATE customers SET {set_clause} WHERE id = %s"

    with get_cursor(db) as cur:
        cur.execute(sql, (*updates.values(), customer_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Customer not found")
        cur.execute("SELECT * FROM customers WHERE id = %s", (customer_id,))
        return cur.fetchone()


@router.delete("/{customer_id}", status_code=204)
def delete_customer(customer_id: int, db: MySQLdb.Connection = Depends(get_db)):
    """Soft delete — sets status to inactive instead of hard delete."""
    with get_cursor(db) as cur:
        cur.execute(
            "UPDATE customers SET status = 'inactive' WHERE id = %s", (customer_id,)
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Customer not found")