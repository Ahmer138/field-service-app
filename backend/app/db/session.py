from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings


# This is the main SQLAlchemy engine.
# It knows HOW to connect to Postgres and manages connection pooling.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # checks connections before using them (prevents stale connections)
)


# This is a session factory.
# Each API request will get its own Session instance.
SessionLocal = sessionmaker(
    autocommit=False,  # we explicitly commit changes (safer)
    autoflush=False,   # prevents automatic writes at unexpected times
    bind=engine,
)


def get_db():
    """
    Provides a database session to FastAPI endpoints.

    Flow:
    - Create a new DB session
    - Yield it to the endpoint
    - Always close it after the request finishes

    This prevents database connection leaks.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
