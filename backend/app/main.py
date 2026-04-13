from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.auth import router as auth_router
from app.api.jobs import router as jobs_router
from app.api.users import router as users_router
from app.db import get_db

app = FastAPI(title="Field Service App API", version="0.1.0")

app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(users_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    """
    Database connectivity check.

    Explanation:
    - `Depends(get_db)` tells FastAPI: "for this request, call get_db() to obtain a DB session"
    - We run a trivial SQL query: SELECT 1
    - If the query succeeds, Postgres is reachable and working
    """
    db.execute(text("SELECT 1"))
    return {"db": "ok"}
