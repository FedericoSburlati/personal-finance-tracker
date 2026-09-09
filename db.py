import mysql.connector
import pandas as pd
import streamlit as st
import os
from dotenv import load_dotenv

load_dotenv()
@st.cache_resource
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        # os.getenv restituisce sempre una stringa, se la porta ti serve come intero fai il cast:
        port=int(os.getenv("DB_PORT"))
    )

def run_query(query, params=None):
    conn = get_db_connection()
    return pd.read_sql(query, conn, params=params)

def execute_query(query, params=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(query, params or ())
        conn.commit()
    finally:
        cursor.close()