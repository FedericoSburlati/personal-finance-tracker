"""
Pagina "Categorizzazione"

Gestione dell'assegnazione delle categorie attraverso pipeline gerarchica
Funzionalità:
- Livello 1: applicazione di regole fisse basate su espressioni regolari (RegEx)
- Livello 2: classificazione tramite memoria vettoriale e inferenza tramite LLM locale

"""


import streamlit as st
import pandas as pd
from src.database.db import run_query, execute_query
from src.core.categorizer import categorizza_con_regole, REGOLE_FISSE
from src.core.llm_classifier import classifica_con_rag, get_vector_store

st.set_page_config(page_title="Categorizzazione Spese", page_icon="🏷️", layout="wide")

CATEGORIE_LISTA = sorted(list(set(REGOLE_FISSE.values())))

# Query di aggiornamento batch parametrizzata con alias esplicito
QUERY_UPDATE_CATEGORIA = """
    UPDATE TRANSAZIONE T 
    SET T.Categoria = :cat 
    WHERE T.Id = :id
"""

@st.cache_resource
def load_cached_vector_store():
    return get_vector_store()

vs = load_cached_vector_store()

st.header("🏷️ Categorizzazione Automatica")
st.caption("Pipeline di classificazione gerarchica: RegEx deterministiche, memoria episodica (RAG) e inferenza LLM locale.")

st.divider()

# Recupero transazioni prive di classificazione
df_uncat = run_query(
    "SELECT T.Id, T.Data, T.Importo, T.Causale, T.Banca, T.Categoria "
    "FROM TRANSAZIONE T "
    "WHERE T.Categoria = 'Non Categorizzato' "
    "ORDER BY T.Data DESC"
)

col_kpi1, col_kpi2 = st.columns([2, 1])
with col_kpi1:
    st.metric("Transazioni da categorizzare", len(df_uncat))
with col_kpi2:
    st.metric("Memoria vettoriale attiva (Seed + Storico)", len(vs.categorie))

if not df_uncat.empty:
    st.subheader("🔍 Transazioni in Coda")
    st.dataframe(df_uncat[['Data', 'Importo', 'Banca', 'Causale']], use_container_width=True, hide_index=True)

    # --- LIVELLO 1: REGEX DETERMINISTICHE ---
    st.subheader("1️⃣ Livello 1: Regole Deterministiche (RegEx)")
    if st.button("🚀 Esegui RegEx", type="primary"):
        with st.spinner("Scansione causali tramite espressioni regolari..."):
            updates = []
            for _, row in df_uncat.iterrows():
                nuova_cat = categorizza_con_regole(str(row['Causale']))
                if nuova_cat != "Non Categorizzato":
                    updates.append({"cat": nuova_cat, "id": int(row['Id'])})
            
            if updates:
                # Esecuzione batch in singola transazione atomica
                execute_query(QUERY_UPDATE_CATEGORIA, updates)
                vs.ricarica_indice()
                st.success(f"Categorizzate con successo {len(updates)} transazioni con RegEx.")
                st.rerun()
            else:
                st.warning("Nessuna causale risolta tramite le RegEx correnti. Procedi al Livello 2.")

    st.divider()

    # --- LIVELLO 2: RAG VETTORIALE + LLM LOCALE ---
    st.subheader("2️⃣ Livello 2: RAG Vettoriale & Inferenza LLM Locale")
    st.caption(
        "Interroga il modello locale (Llama 3.2 3B) combinando similarità vettoriale e few-shot learning dallo storico. "
        "Tutte le categorie proposte richiedono conferma manuale."
    )

    col_conf, _ = st.columns([1, 1])
    with col_conf:
        soglia_confidenza = st.slider(
            "Soglia minima di confidenza accettata",
            min_value=0.50,
            max_value=0.95,
            value=0.80,
            step=0.05,
            help="Le proposte con punteggio inferiore a questo valore non saranno selezionate di default."
        )

    if st.button("🤖 Genera Proposte AI", type="secondary"):
        totale = len(df_uncat)
        proposte = []
        
        with st.status("Elaborazione causali in corso...", expanded=True) as status_box:
            barra_progresso = st.progress(0.0)
            dettaglio_live = st.empty()
            
            for idx, row in df_uncat.iterrows():
                causale_troncata = str(row['Causale'])[:40]
                dettaglio_live.markdown(f"**Analisi [{idx + 1}/{totale}]**: `{causale_troncata}...`")
                
                risultato = classifica_con_rag(
                    causale=str(row['Causale']),
                    importo=float(row['Importo']),
                    banca=str(row['Banca'])
                )
                
                conf = float(risultato['confidenza'])
                cat = risultato['categoria']
                metodo = risultato['metodo']
                
                if "Zona Calda" in metodo:
                    st.write(f"⚡ *{causale_troncata}* $\\rightarrow$ **{cat}** (RAG Diretto, {risultato.get('motivo', '')})")
                else:
                    st.write(f"🤖 *{causale_troncata}* $\\rightarrow$ **{cat}** (LLM Few-Shot, conf: {conf:.2f})")
                
                approva_default = (cat != "Non Categorizzato") and (conf >= soglia_confidenza)
                proposte.append({
                    "Id": int(row['Id']),
                    "Data": row['Data'],
                    "Importo": float(row['Importo']),
                    "Causale": str(row['Causale']),
                    "Banca": str(row['Banca']),
                    "Categoria Proposta": cat,
                    "Confidenza": conf,
                    "Metodo": metodo,
                    "Motivo": risultato.get('motivo', ''),
                    "Approva": approva_default
                })
                
                barra_progresso.progress((idx + 1) / totale)
            
            dettaglio_live.empty()
            status_box.update(
                label=f"Classificazione completata su {totale} movimenti.",
                state="complete",
                expanded=False
            )
            
        st.session_state["proposte_ai"] = pd.DataFrame(proposte)
        st.rerun()

    # Tabella di revisione e validazione umana
    if "proposte_ai" in st.session_state and not st.session_state["proposte_ai"].empty:
        st.subheader("📋 Revisione Proposte")
        st.caption("Verifica i suggerimenti del modello, modifica i valori non corretti e conferma il salvataggio.")
        
        editor_config = {
            "Id": st.column_config.NumberColumn("Id", disabled=True),
            "Data": st.column_config.DateColumn("Data", disabled=True),
            "Causale": st.column_config.TextColumn("Causale", disabled=True, width="large"),
            "Importo": st.column_config.NumberColumn("Importo (€)", format="%.2f €", disabled=True),
            "Banca": st.column_config.TextColumn("Banca", disabled=True),
            "Categoria Proposta": st.column_config.SelectboxColumn(
                "Categoria Suggerita",
                options=CATEGORIE_LISTA,
                required=True,
                width="medium"
            ),
            "Confidenza": st.column_config.ProgressColumn(
                "Confidenza",
                format="%.2f",
                min_value=0.0,
                max_value=1.0,
                width="small"
            ),
            "Metodo": st.column_config.TextColumn("Metodo", disabled=True),
            "Motivo": st.column_config.TextColumn("Motivo", disabled=True),
            "Approva": st.column_config.CheckboxColumn("Approva", default=True)
        }
        
        df_revisionato = st.data_editor(
            st.session_state["proposte_ai"],
            column_config=editor_config,
            use_container_width=True,
            hide_index=True,
            key="editor_proposte"
        )

        col_btn1, col_btn2 = st.columns([2, 8])
        with col_btn1:
            if st.button("💾 Salva Selezionate nel DB", type="primary"):
                da_salvare = df_revisionato[df_revisionato["Approva"] == True]
             
                if da_salvare.empty:
                    st.warning("Nessuna transazione contrassegnata per l'approvazione.")
                else:
                    # Inserimento batch in una singola transazione
                    updates_ai = [
                        {"cat": str(r["Categoria Proposta"]), "id": int(r["Id"])}
                        for _, r in da_salvare.iterrows()
                    ]
                    execute_query(QUERY_UPDATE_CATEGORIA, updates_ai)
                    
                    vs.ricarica_indice()
                    st.success(f"Salvate con successo {len(updates_ai)} transazioni.")
                    del st.session_state["proposte_ai"]
                    st.rerun()

        with col_btn2:
            if st.button("❌ Annulla Proposte"):
                del st.session_state["proposte_ai"]
                st.rerun()

else:
    st.success("Tutte le transazioni presenti nel database risultano categorizzate.")