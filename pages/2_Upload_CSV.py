"""
Pagina 'Upload CSV"

Gestione del caricamento e salvataggio dei file CSV nel DB.
Funzionalità:
- Selezione della banca di origine e caricamento file
- Elaborazione file (formati accettati .csv e .txt)
- Parsing ed elaborazione dei dati
- Anteprima dati
- Salvataggio nel DB escludendo transazioni già caricate
"""
import streamlit as st
import pandas as pd
from src.etl.etl import parse_estratto_conto, salva_transazioni

st.set_page_config(page_title="Upload Estratto Conto", page_icon="📥", layout="wide")

st.header("📥 Ingestion & Normalizzazione ETL")
st.write("Carica il file CSV del tuo estratto conto per la normalizzazione dei campi e la deduplicazione automatica.")

st.divider()

col_config, col_file = st.columns([1, 2])

with col_config:
    banca_selezionata = st.selectbox(
        "1. Istituto Bancario:",
        ["Intesa Sanpaolo", "Hype", "Satispay"]
    )
    separatore = st.radio("Separatore CSV (fallback):", [",", ";", "\t"], horizontal=True)

with col_file:
    uploaded_file = st.file_uploader("2. Seleziona file", type=["csv", "txt"])

if uploaded_file is not None:
    try:
        # Parsing e normalizzazione tramite modulo ETL dedicato
        df_preview = parse_estratto_conto(uploaded_file, banca=banca_selezionata, separatore=separatore)

        st.subheader("🔍 Anteprima Dati Normalizzati")
        st.dataframe(df_preview.head(10), use_container_width=True, hide_index=True)
        st.caption(f"Totale movimenti rilevati nel file: **{len(df_preview)}**")

        if st.button("🚀 Salva Transazioni nel Database", type="primary"):
            with st.spinner("Salvataggio e deduplicazione batch in corso..."):
                inseriti, duplicati = salva_transazioni(df_preview)

            st.success("Operazione di ingestion completata con successo.")
            res1, res2 = st.columns(2)
            res1.metric("Transazioni inserite", inseriti)
            res2.metric("Scartate (Già presenti)", duplicati)

    except Exception as e:
        st.error(f"Errore durante l'elaborazione del file: {e}")