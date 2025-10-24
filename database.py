"""
Simple database for storing user OAuth tokens
Using SQLite for simplicity - can be upgraded to PostgreSQL later
"""
import sqlite3
import logging
from typing import Optional, Tuple
from datetime import datetime
import threading

logger = logging.getLogger(__name__)

# Thread-local storage for database connections
_local = threading.local()

def get_connection():
    """Get thread-local database connection"""
    if not hasattr(_local, 'conn'):
        _local.conn = sqlite3.connect('users.db', check_same_thread=False)
    return _local.conn


def init_db():
    """Initialize the database with required tables"""
    conn = get_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            google_user_id TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            name TEXT,
            access_token TEXT NOT NULL,
            refresh_token TEXT,
            token_expiry TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    logger.info("✅ Database initialized")


def save_user(
    google_user_id: str,
    email: str,
    access_token: str,
    refresh_token: Optional[str] = None,
    name: Optional[str] = None
) -> None:
    """
    Save or update user OAuth tokens
    
    Args:
        google_user_id: Google user ID
        email: User email
        access_token: OAuth access token
        refresh_token: OAuth refresh token (optional)
        name: User's display name (optional)
    """
    conn = get_connection()
    try:
        conn.execute('''
            INSERT OR REPLACE INTO users 
            (google_user_id, email, name, access_token, refresh_token, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            google_user_id,
            email,
            name,
            access_token,
            refresh_token,
            datetime.utcnow()
        ))
        conn.commit()
        logger.info(f"✅ Saved tokens for user: {email}")
    except Exception as e:
        logger.error(f"❌ Failed to save user: {e}")
        raise


def get_user_tokens(google_user_id: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Get user's OAuth tokens from database
    
    Args:
        google_user_id: Google user ID
        
    Returns:
        Tuple of (access_token, refresh_token) or (None, None) if not found
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            'SELECT access_token, refresh_token FROM users WHERE google_user_id = ?',
            (google_user_id,)
        )
        row = cursor.fetchone()
        if row:
            logger.info(f"✅ Retrieved tokens for user: {google_user_id}")
            return row[0], row[1]
        else:
            logger.warning(f"⚠️  No tokens found for user: {google_user_id}")
            return None, None
    except Exception as e:
        logger.error(f"❌ Failed to get user tokens: {e}")
        return None, None


def get_user_info(google_user_id: str) -> Optional[dict]:
    """
    Get user information from database
    
    Args:
        google_user_id: Google user ID
        
    Returns:
        Dict with user info or None if not found
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            'SELECT google_user_id, email, name, created_at FROM users WHERE google_user_id = ?',
            (google_user_id,)
        )
        row = cursor.fetchone()
        if row:
            return {
                "google_user_id": row[0],
                "email": row[1],
                "name": row[2],
                "created_at": row[3]
            }
        return None
    except Exception as e:
        logger.error(f"❌ Failed to get user info: {e}")
        return None


def update_tokens(google_user_id: str, access_token: str, refresh_token: Optional[str] = None) -> None:
    """
    Update user's tokens (for token refresh)
    
    Args:
        google_user_id: Google user ID
        access_token: New access token
        refresh_token: New refresh token (optional)
    """
    conn = get_connection()
    try:
        if refresh_token:
            conn.execute('''
                UPDATE users 
                SET access_token = ?, refresh_token = ?, updated_at = ?
                WHERE google_user_id = ?
            ''', (access_token, refresh_token, datetime.utcnow(), google_user_id))
        else:
            conn.execute('''
                UPDATE users 
                SET access_token = ?, updated_at = ?
                WHERE google_user_id = ?
            ''', (access_token, datetime.utcnow(), google_user_id))
        conn.commit()
        logger.info(f"✅ Updated tokens for user: {google_user_id}")
    except Exception as e:
        logger.error(f"❌ Failed to update tokens: {e}")
        raise


def delete_user(google_user_id: str) -> bool:
    """
    Delete user and their tokens
    
    Args:
        google_user_id: Google user ID
        
    Returns:
        True if deleted, False if not found
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            'DELETE FROM users WHERE google_user_id = ?',
            (google_user_id,)
        )
        conn.commit()
        if cursor.rowcount > 0:
            logger.info(f"✅ Deleted user: {google_user_id}")
            return True
        else:
            logger.warning(f"⚠️  User not found: {google_user_id}")
            return False
    except Exception as e:
        logger.error(f"❌ Failed to delete user: {e}")
        return False


def list_users() -> list:
    """
    List all users (for admin purposes)
    
    Returns:
        List of user dictionaries
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            'SELECT google_user_id, email, name, created_at FROM users ORDER BY created_at DESC'
        )
        rows = cursor.fetchall()
        return [
            {
                "google_user_id": row[0],
                "email": row[1],
                "name": row[2],
                "created_at": row[3]
            }
            for row in rows
        ]
    except Exception as e:
        logger.error(f"❌ Failed to list users: {e}")
        return []
