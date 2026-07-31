"""
Database connection and utilities for Indoor Positioning System
"""
import mysql.connector
from mysql.connector import Error, pooling
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'indoor_positioning_db'),
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci',
    'autocommit': True
}

# Connection pool
connection_pool: Optional[pooling.MySQLConnectionPool] = None


def init_connection_pool():
    """Initialize database connection pool"""
    global connection_pool
    try:
        connection_pool = pooling.MySQLConnectionPool(
            pool_name="ips_pool",
            pool_size=5,
            pool_reset_session=True,
            **DB_CONFIG
        )
        print("Database connection pool initialized successfully")
    except Error as e:
        print(f"Error initializing connection pool: {e}")
        raise


def get_db_connection():
    """Get a connection from the pool"""
    try:
        if connection_pool is None:
            init_connection_pool()
        return connection_pool.get_connection()
    except Error as e:
        print(f"Error getting connection from pool: {e}")
        raise


def execute_query(query: str, params: tuple = None, fetch: bool = False, fetch_one: bool = False):
    """
    Execute a database query
    
    Args:
        query: SQL query string
        params: Query parameters (tuple)
        fetch: Whether to fetch results
        fetch_one: Whether to fetch only one result
        
    Returns:
        Query results or affected row count
    """
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute(query, params or ())
        
        if fetch:
            return cursor.fetchone() if fetch_one else cursor.fetchall()
        else:
            connection.commit()
            return cursor.lastrowid if cursor.lastrowid else cursor.rowcount
            
    except Error as e:
        if connection:
            connection.rollback()
        print(f"Database error: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def execute_many(query: str, data: list):
    """
    Execute a query with multiple sets of parameters
    
    Args:
        query: SQL query string
        data: List of parameter tuples
        
    Returns:
        Number of affected rows
    """
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.executemany(query, data)
        connection.commit()
        return cursor.rowcount
        
    except Error as e:
        if connection:
            connection.rollback()
        print(f"Database error in executemany: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def test_connection() -> bool:
    """Test database connection"""
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        connection.close()
        print("Database connection test successful")
        return True
    except Error as e:
        print(f"Database connection test failed: {e}")
        return False
