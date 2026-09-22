"""
Pagina 'Transazioni'

Visualizzazione dell'elenco di tutte le transazioni registrate nel database.
Funzionalità:
- Filtraggio dei movimenti per periodo (mese e anno).
- Ricerca transazioni tramite testo libero nella causale.
"""

import streamlit as st
import pandas as pd
from src.database.db import run_query

st.set_page_config(page_title="Elenco Transazioni", page_icon="📝", layout="wide")

st.title("📝 Elenco Transazioni")
st.write("Visualizzazione tabellare di tutti i movimenti bancari registrati.")

st.divider()

query = """
    SELECT T.Data, T.Importo, T.Causale, T.Categoria, T.Banca
    FROM TRANSAZIONE T
    ORDER BY T.Data DESC
"""

df_transazioni = run_query(query)

if df_transazioni.empty:
    st.info("Nessuna transazione presente nel database. Vai alla sezione di Upload per caricare i file CSV.")
    st.stop()

df_transazioni['Data_dt'] = pd.to_datetime(df_transazioni['Data'], dayfirst=True, errors='coerce')

MESI_IT = {
    1: 'Gennaio', 2: 'Febbraio', 3: 'Marzo', 4: 'Aprile',
    5: 'Maggio', 6: 'Giugno', 7: 'Luglio', 8: 'Agosto',
    9: 'Settembre', 10: 'Ottobre', 11: 'Novembre', 12: 'Dicembre'
}

df_transazioni['Mese_Anno'] = df_transazioni['Data_dt'].apply(
    lambda d: f"{MESI_IT.get(d.month, '')} {d.year}" if pd.notna(d) else "Data non definita"
)

mesi_disponibili = ["Tutti i mesi"] + [m for m in df_transazioni['Mese_Anno'].unique() if m != "Data non definita"]

col_filtro, col_search = st.columns([1, 2])
with col_filtro:
    mese_scelto = st.selectbox("Seleziona periodo da visualizzare:", mesi_disponibili, index=0)
with col_search:
    testo_ricerca = st.text_input("Cerca per testo nella causale:", placeholder="es. Conad, Amazon, Stipendio...")


df_filtrato = df_transazioni.copy()
if mese_scelto != "Tutti i mesi":
    df_filtrato = df_filtrato[df_filtrato['Mese_Anno'] == mese_scelto]

if testo_ricerca.strip():
    df_filtrato = df_filtrato[df_filtrato['Causale'].str.contains(testo_ricerca.strip(), case=False, na=False)]

entrate = df_filtrato[df_filtrato['Importo'] > 0]['Importo'].sum()
uscite = df_filtrato[(df_filtrato['Importo'] < 0) & (df_filtrato['Categoria'] != 'Giroconto')]['Importo'].sum()

kpi1, kpi2, kpi3 = st.columns(3)
with kpi1:
    st.metric("Movimenti", len(df_filtrato))
with kpi2:
    st.metric("Totale Entrate", f"€ {entrate:,.2f}")
with kpi3:
    st.metric("Uscite Nette", f"€ {abs(uscite):,.2f}")

st.write("")

df_visualizzazione = df_filtrato[['Data_dt', 'Importo', 'Causale', 'Categoria', 'Banca']].copy()
df_visualizzazione['Data'] = df_visualizzazione['Data_dt'].dt.strftime('%d/%m/%Y').fillna(df_filtrato['Data'])
df_visualizzazione = df_visualizzazione[['Data', 'Importo', 'Causale', 'Categoria', 'Banca']]

st.dataframe(
    df_visualizzazione,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Importo": st.column_config.NumberColumn("Importo (€)", format="%.2f"),
        "Data": st.column_config.TextColumn("Data"),
        "Banca": st.column_config.TextColumn("Banca di Provenienza"),
        "Causale": st.column_config.TextColumn("Causale"),
        "Categoria": st.column_config.TextColumn("Categoria")
    }
)