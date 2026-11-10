from typing import List, Dict, Any
from sqlalchemy import text
from src.database.connection import get_engine

FORBIDDEN_KEYWORDS = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "RENAME"]

def execute_readonly_sql(query: str) -> List[Dict[str, Any]]:
    """
    Executes a read-only SQL SELECT query against the Aiven database.
    Rejects any destructive or modifying statements.
    """
    clean_query = query.strip()
    upper_query = clean_query.upper()

    # Security check: strictly allow only SELECT statements
    if not upper_query.startswith("SELECT"):
        return [{"error": "Permission denied: Only SELECT queries are permitted in this tool."}]

    for keyword in FORBIDDEN_KEYWORDS:
        if f" {keyword} " in f" {upper_query} ":
            return [{"error": f"Permission denied: Query contains forbidden keyword '{keyword}'."}]

    engine = get_engine()
    try:
        with engine.connect() as conn:
            result = conn.execute(text(clean_query))
            records = [dict(row) for row in result.mappings().all()]
            return records if records else [{"message": "Query executed successfully, but 0 records were returned."}]
    except Exception as e:
        return [{"error": f"Database execution error: {str(e)}"}]

if __name__ == "__main__":
    test_sql = "SELECT order_id, restaurant_name, total_amount FROM orders WHERE user_id = 1964 LIMIT 2;"
    res = execute_readonly_sql(test_sql)
    print(f"[TEST] SQL Query Tool Result:\n{res}")