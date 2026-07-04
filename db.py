# db.py
import os
import psycopg2

from src.setup.settings import settings


def get_connection():
    """
    Opens a new connection per request. Fine for this app's traffic volume;
    swap for a connection pool (e.g. psycopg2.pool or asyncpg) if this ever
    becomes a bottleneck.
    """
    return psycopg2.connect(settings.database_url)