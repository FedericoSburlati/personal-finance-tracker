import sys
from pathlib import Path

# Aggiunge la cartella radice (project) al PYTHONPATH
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

import streamlit as st
import pandas as pd
from etl import parse_intesa, parse_hype, parse_satispay, transform_and_load

st.set_page_config(page_title="Upload Estratto Conto", page_icon="📥", layout="wide")

st.header("📥 Ingestion & Normalizzazione ETL")
st.write("Carica il file CSV del tuo estratto conto. Il sistema normalizzerà le colonne e scarterà i duplicati già registrati.")

st.divider()

col1, col2 = st.columns([1, 2])

with col1:
    banca_selezionata = st.selectbox(
        "1. Seleziona l'Istituto Bancario:",
        ["Intesa Sanpaolo", "Hype", "Satispay"]
    )
    separatore = st.radio("Separatore CSV:", [",", ";", "\t"], horizontal=True)

with col2:
    uploaded_file = st.file_uploader("2. Carica il file CSV", type=["csv", "txt"])

if uploaded_file is not None:
    try:
        # 1. Parsing in base alla banca selezionata
        if banca_selezionata == "Intesa Sanpaolo":
            df_preview = parse_intesa(uploaded_file)
        elif banca_selezionata == "Hype":
            df_preview = parse_hype(uploaded_file)
        elif banca_selezionata == "Satispay":
            uploaded_file.seek(0)
            #modifica csv per caratteri non ASCII
            df_grezzo = pd.read_csv(uploaded_file, sep=';', encoding='latin1')
            df_preview = parse_satispay(df_grezzo)
        else:
            # Satispay o fallback generico
            uploaded_file.seek(0)
            df_preview = pd.read_csv(uploaded_file, sep=separatore)

        # 2. Visualizzazione unica e pulita
        st.subheader("🔍 Anteprima Dati Normalizzati")
        st.dataframe(df_preview.head(10), use_container_width=True)
        st.caption(f"Totale transazioni rilevate: {len(df_preview)}")

        # 3. Pulsante di salvataggio con deduplicazione
        if st.button("🚀 Salva Transazioni nel Database", type="primary"):
            with st.spinner("Salvataggio e deduplicazione in corso..."):
                from db import execute_query
                from etl import calcola_hash

                df_preview['Hash_Duplicato'] = df_preview.apply(
                    lambda r: calcola_hash(r['Data'], r['Importo'], r['Causale']), axis=1
                )

                query = """
                INSERT INTO TRANSAZIONE (Data, Importo, Causale, Banca, Categoria, Hash_Duplicato)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE Id = Id;
                """

                inseriti = 0
                duplicati = 0

                for _, row in df_preview.iterrows():
                    try:
                        execute_query(query, (
                            row['Data'],
                            float(row['Importo']),
                            str(row['Causale']),
                            row['Banca'],
                            'Non Categorizzato',
                            row['Hash_Duplicato']
                        ))
                        inseriti += 1
                    except Exception:
                        duplicati += 1

                st.success("Caricamento completato!")
                col_res1, col_res2 = st.columns(2)
                col_res1.metric("Transazioni elaborate", inseriti)
                col_res2.metric("Scartate / Duplicati", duplicati)

    except Exception as e:
        st.error(f"Errore durante l'elaborazione del file: {e}")