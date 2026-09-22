"""
Modulo: Database

Funzionalità:
- Accesso al DB
- Esecuzione di Query
"""

import os
import urllib.parse
from typing import Any
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = os.getenv("DB_PORT", "3306")

mancanti = [
    chiave for chiave, valore in {
        "DB_HOST": DB_HOST,
        "DB_USER": DB_USER,
        "DB_NAME": DB_NAME
    }.items() if not valore
]

if mancanti:
    raise ValueError(f"Variabili di configurazione database mancanti nel file .env: {', '.join(mancanti)}")

password_pulita = urllib.parse.quote_plus(DB_PASSWORD) if DB_PASSWORD else ""
DB_URL = f"mysql+pymysql://{DB_USER}:{password_pulita}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# pool_pre_ping=True previene crash dovuti a timeout o riavvii del server MySQL
engine = create_engine(
    DB_URL,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
    pool_pre_ping=True
)

def run_query(query: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
    """Esegue una query SELECT parametrizzata e restituisce un DataFrame."""
    with engine.connect() as conn:
        return pd.read_sql(text(query), conn, params=params)

def execute_query(query: str, params: dict[str, Any] | list[dict[str, Any]] | None = None) -> None:
    """Esegue una query di modifica (INSERT/UPDATE/DELETE) singola o batch (executemany)."""
    with engine.begin() as conn:
        conn.execute(text(query), params)