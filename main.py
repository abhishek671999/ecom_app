"""
main.py
-------
FastAPI application entry point.
Registers all routers and configures the app.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import addresses, customers, restaurants, items, orders, delivery_partners

app = FastAPI(
    title="Ecom OLTP API",
    description="FastAPI + mysqlclient REST API for the ecom food delivery OLTP database.",
    version="1.0.0",
    docs_url="/docs",       # Swagger UI
    redoc_url="/redoc",     # ReDoc UI
)

# ---------------------------------------------------------------------------
# CORS — adjust origins for your frontend / environment
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # tighten this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(addresses.router)
app.include_router(customers.router)
app.include_router(restaurants.router)
app.include_router(items.router)
app.include_router(orders.router)
app.include_router(delivery_partners.router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Run directly with: python main.py
# Or: uvicorn main:app --reload
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)