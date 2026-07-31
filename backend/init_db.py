"""Initialize database using Python"""
import mysql.connector
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# Read SQL file
with open("db/init.sql", "r", encoding="utf-8") as f:
    sql_content = f.read()

# Split SQL statements
statements = [stmt.strip() for stmt in sql_content.split(";") if stmt.strip()]

try:
    # Connect to MySQL server (without specifying database)
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("Connected to MySQL server")
    
    # Execute each statement
    for i, statement in enumerate(statements, 1):
        try:
            cursor.execute(statement)
            if cursor.with_rows:
                cursor.fetchall()
            print(f"✓ Statement {i} executed successfully")
        except mysql.connector.Error as err:
            print(f"✗ Statement {i} failed: {err}")
            # Continue with other statements
    
    conn.commit()
    print("\n✓ Database initialized successfully!")
    
    cursor.close()
    conn.close()

except mysql.connector.Error as err:
    print(f"✗ Error: {err}")
    print("\nMake sure:")
    print("1. MySQL server is running")
    print("2. DB_PASSWORD in .env is correct")
