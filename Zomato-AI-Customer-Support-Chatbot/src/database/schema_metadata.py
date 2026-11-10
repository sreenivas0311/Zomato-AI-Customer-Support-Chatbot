from sqlalchemy import text
from src.database.connection import get_engine

def print_table_schemas():
    """Inspects and prints all columns for the four project tables."""
    tables = ['users', 'orders', 'order_items', 'support_tickets']
    engine = get_engine()
    
    with engine.connect() as conn:
        for table in tables:
            print(f"\n==================== {table.upper()} ====================")
            try:
                columns = conn.execute(text(f"DESCRIBE {table};")).fetchall()
                for col in columns:
                    field_name = col[0]
                    field_type = col[1]
                    null_allowed = "NULL" if col[2] == "YES" else "NOT NULL"
                    print(f"  - {field_name:<20} {field_type:<15} {null_allowed}")
            except Exception as e:
                print(f"  Error inspecting {table}: {e}")

if __name__ == "__main__":
    print_table_schemas()