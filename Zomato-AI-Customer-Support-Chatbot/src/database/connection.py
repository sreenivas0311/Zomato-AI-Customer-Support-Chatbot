from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from config.settings import settings

def get_engine() -> Engine:
    """Initializes and returns an SSL-secured SQLAlchemy engine connected to Aiven MySQL."""
    settings.validate()
    
    connection_url = (
        f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    )
    
    connect_args = {
        "ssl": {
            "ca": str(settings.DB_SSL_CA)
        }
    }
    
    return create_engine(
        connection_url,
        connect_args=connect_args,
        pool_size=5,
        max_overflow=10,
        pool_recycle=3600,
        pool_pre_ping=True
    )

def test_connection():
    """Validates the live database connection and lists existing tables."""
    try:
        print("[INFO] Attempting to connect to Aiven MySQL...")
        engine = get_engine()
        with engine.connect() as conn:
            db_name = conn.execute(text("SELECT DATABASE();")).scalar()
            tables = conn.execute(text("SHOW TABLES;")).fetchall()
            table_names = [t[0] for t in tables]
            print(f"[SUCCESS] Connected to database: '{db_name}'")
            print(f"[SUCCESS] Tables found ({len(table_names)}): {table_names}")
    except Exception as e:
        print(f"[ERROR] Database connection failed: {e}")

if __name__ == "__main__":
    test_connection()