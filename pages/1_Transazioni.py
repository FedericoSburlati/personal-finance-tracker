import streamlit as st
import pandas as pd
from db import run_query

# Configurazione della pagina
st.set_page_config(page_title="Transazioni", page_icon="📝", layout="wide")

st.title("📝 Elenco Transazioni")
st.write("Visualizzazione tabellare di tutti i movimenti bancari registrati.")

st.divider()

# Proiezione degli attributi desiderati e ordinamento delegato al DBMS
query = """
    SELECT T.Data, T.Importo, T.Causale, T.Categoria, T.Banca
    FROM TRANSAZIONE T
    ORDER BY T.Data DESC
"""

# Esecuzione della query
df_transazioni = run_query(query)

# Renderizzazione a schermo
if not df_transazioni.empty:
    # Formattazione della colonna Data per una visualizzazione pulita
    df_transazioni['Data'] = pd.to_datetime(df_transazioni['Data'], errors='coerce')
    df_transazioni['Mese_Anno'] = df_transazioni['Data'].dt.strftime('%B %Y')

    # dizionaro dei mesi per imporre lingua italiana
    mesi_it = {
        'January': 'Gennaio', 'February': 'Febbraio', 'March': 'Marzo', 
        'April': 'Aprile', 'May': 'Maggio', 'June': 'Giugno', 
        'July': 'Luglio', 'August': 'Agosto', 'September': 'Settembre', 
        'October': 'Ottobre', 'November': 'Novembre', 'December': 'Dicembre'
    }

    # traduzione dei mesi nella colonna
    for eng, ita in mesi_it.items():
        df_transazioni['Mese_Anno'] = df_transazioni['Mese_Anno'].str.replace(eng, ita)

    mesi_presenti = df_transazioni['Mese_Anno'].unique()

# iterazione su mesi per avere box separate
    for mese in mesi_presenti:
        st.subheader(f"📅 {mese}")
        
        # Filtra i dati solo per il mese dell'iterazione corrente
        df_mese = df_transazioni[df_transazioni['Mese_Anno'] == mese].copy()
        
        # Formatta la colonna Data nello standard europeo (Giorno/Mese/Anno)
        df_mese['Data'] = df_mese['Data'].dt.strftime('%d/%m/%Y')
        
        # Rimuove la colonna di appoggio per non mostrarla nella tabella
        df_mese.drop(columns=['Mese_Anno'], inplace=True)
        
        # Renderizza la tabella
        st.dataframe(
            df_mese,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Importo": st.column_config.NumberColumn("Importo (€)", format="%.2f"),
                "Data": st.column_config.TextColumn("Data"),
                "Banca": st.column_config.TextColumn("Banca di Provenienza")
            }
        )
        
        # Calcolo dinamico di un piccolo riepilogo mensile (utile per l'analisi finanziaria)
        entrate = df_mese[df_mese['Importo'] > 0]['Importo'].sum()
        uscite = df_mese[(df_mese['Importo'] < 0) & (df_mese['Categoria'] != 'Giroconto')]['Importo'].sum()
        
        st.caption(f"Movimenti: **{len(df_mese)}** | Totale Entrate: **€ {entrate:.2f}** | Uscite nette: **€ {abs(uscite):.2f}**")
        st.write("---") # Linea di separazione per il mese successivo

else:
    st.info("Nessuna transazione presente nel database. Vai alla sezione di Upload per caricare i file CSV.")