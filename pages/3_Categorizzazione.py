import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

import streamlit as st
import pandas as pd
from db import run_query, execute_query
from categorizer import categorizza_con_regole

st.set_page_config(page_title="Categorizzazione Spese", page_icon="🏷️", layout="wide")

st.header("🏷️ Categorizzazione Intelligente a Cascata")
st.write("Assegna le categorie di spesa combinando regole RegEx deterministiche e modelli linguistici.")

st.divider()

# Recupera transazioni non categorizzate
df_uncat = run_query("SELECT Id, Data, Importo, Causale, Banca, Categoria FROM TRANSAZIONE WHERE Categoria = 'Non Categorizzato'")

col1, col2 = st.columns([2, 1])
with col1:
    st.metric("Transazioni in attesa di categorizzazione", len(df_uncat))

if not df_uncat.empty:
    st.subheader("🔍 Transazioni da Classificare")
    st.dataframe(df_uncat[['Data', 'Importo', 'Banca', 'Causale']], use_container_width=True)

    st.subheader("1️⃣ Fase 1: Classificazione tramite Regole (RegEx)")
    if st.button("🚀 Esegui Categorizzazione RegEx", type="primary"):
        with st.spinner("Applicazione regole in corso..."):
            aggiornate = 0
            for _, row in df_uncat.iterrows():
                testo_causale = str(row['Causale'])
                nuova_cat = categorizza_con_regole(testo_causale)
                
                if nuova_cat != "Non Categorizzato":
                    execute_query(
                        "UPDATE TRANSAZIONE SET Categoria = %s WHERE Id = %s",
                        (nuova_cat, int(row['Id']))
                    )
                    aggiornate += 1
            
            if aggiornate > 0:
                st.success(f" Categorizzate con successo {aggiornate} transazioni!")
                st.rerun()
            else:
                st.warning(" Nessuna corrispondenza trovata con le RegEx attuali.")
else:
    st.success("🎉 Tutte le transazioni presenti nel database sono state categorizzate!")