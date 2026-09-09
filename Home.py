import streamlit as st
import altair as alt
from db import run_query
import pandas as pd
from datetime import timedelta, date
import calendar

st.set_page_config(page_title="Personal Finance", page_icon="💸", layout="wide")

st.header("💸 Dashboard Finanziaria")
st.write("Monitoraggio e categorizzazione automatica delle transazioni bancarie.")
st.caption("*Portfolio* | **Sburlati Federico**")

st.divider()

st.subheader("Panoramica Mensile")
met1, met2, met3 = st.columns(3)

# Query con COALESCE per forzare 0 al posto di NULL se la tabella è vuota
saldo_attuale = run_query("SELECT COALESCE(SUM(T.Importo), 0) as tot FROM TRANSAZIONE T")
tot_entrate = run_query("SELECT COALESCE(SUM(T.Importo), 0) as tot FROM TRANSAZIONE T WHERE T.Importo > 0")
tot_uscite = run_query("SELECT COALESCE(SUM(T.Importo), 0) as tot FROM TRANSAZIONE T WHERE T.Importo < 0 AND T.Categoria <> 'Giroconto'")

def format_currency(val):
    if pd.isna(val) or val is None:
        return "€ 0.00"
    return f"€ {float(val):.2f}"

val_saldo = saldo_attuale['tot'][0] if not saldo_attuale.empty and saldo_attuale['tot'][0] is not None else 0
val_entrate = tot_entrate['tot'][0] if not tot_entrate.empty and tot_entrate['tot'][0] is not None else 0
val_uscite = tot_uscite['tot'][0] if not tot_uscite.empty and tot_uscite['tot'][0] is not None else 0

met1.metric("Saldo Globale", format_currency(val_saldo))
met2.metric("Totale Entrate", format_currency(val_entrate))
met3.metric("Totale Uscite", format_currency(abs(float(val_uscite))))

st.subheader("📊 Analisi Spese Interattiva")

# --- 1. SEZIONE FILTRI TEMPORALI GLOBALI ---
st.write("### Seleziona il periodo di analisi")
col_vista, col_dettaglio = st.columns(2)

with col_vista:
    vista = st.radio(
        "Granularità:",
        ["Settimanale (giorni)", "Mensile (giorni)", "Annuale (mesi)"],
        horizontal=True
    )

# Calcolo dinamico di start_date ed end_date
with col_dettaglio:
    if vista == "Settimanale (giorni)":
        # Seleziona un giorno, il sistema calcola in automatico la settimana di appartenenza (Lunedì-Domenica)
        data_sel = st.date_input("Seleziona un giorno qualsiasi della settimana:", value=date.today(), format="DD/MM/YYYY")
        start_date = data_sel - timedelta(days=data_sel.weekday())
        end_date = start_date + timedelta(days=6)
        st.caption(f"Settimana analizzata: {start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}")

    elif vista == "Mensile (giorni)":
        col_mese, col_anno = st.columns(2)
        mesi_dict = {
            "Gennaio": 1, "Febbraio": 2, "Marzo": 3, "Aprile": 4, "Maggio": 5, "Giugno": 6,
            "Luglio": 7, "Agosto": 8, "Settembre": 9, "Ottobre": 10, "Novembre": 11, "Dicembre": 12
        }
        with col_anno:
            anno_sel = st.selectbox("Anno", [2026, 2025, 2024], index=0)
        with col_mese:
            mese_sel = st.selectbox("Mese", list(mesi_dict.keys()), index=date.today().month - 1)
        
        num_mese = mesi_dict[mese_sel]
        start_date = date(anno_sel, num_mese, 1)
        # calcola in automatico se il mese finisce al 28, 29, 30 o 31
        _, ultimo_giorno = calendar.monthrange(anno_sel, num_mese) 
        end_date = date(anno_sel, num_mese, ultimo_giorno)

    else: # Annuale
        anno_sel = st.selectbox("Anno di analisi", [2026, 2025, 2024], index=0)
        start_date = date(anno_sel, 1, 1)
        end_date = date(anno_sel, 12, 31)

# Conversione per compatibilità con il DB
start_str = start_date.strftime('%d-%m-%Y')
end_str = end_date.strftime('%d-%m-%Y')


# --- 2. ESTRAZIONE DATI FILTRATI (con utilizzo degli ALIAS e clausola WHERE) ---
# Query per l'andamento nel tempo
query_time = f"""
    SELECT T.Data, SUM(T.Importo) as Totale 
    FROM TRANSAZIONE T
    WHERE T.Data >= '{start_str}' AND T.Data <= '{end_str}'
    GROUP BY T.Data 
    ORDER BY T.Data
"""
df_time = run_query(query_time)

# Query per le categorie (solo uscite, ignorando i giroconti)
query_cat = f"""
    SELECT T.Categoria, SUM(T.Importo) as Totale 
    FROM TRANSAZIONE T 
    WHERE T.Data >= '{start_str}' AND T.Data <= '{end_str}'
      AND T.Importo < 0 
      AND T.Categoria <> 'Giroconto' 
    GROUP BY T.Categoria
"""
df_cat = run_query(query_cat)


# --- 3. TAB VISUALIZZAZIONI ---
tab_andamento, tab_categorie = st.tabs(["📈 Andamento nel Tempo", "🏷️ Spese per Categoria"])

with tab_andamento:
    if not df_time.empty:
        df_time['Data'] = pd.to_datetime(df_time['Data'])
        df_time.set_index('Data', inplace=True)

        if vista == "Annuale (mesi)":
            # Raggruppa le somme per fine mese (ME)
            df_plot = df_time.resample('ME').sum()
        else:
            # Crea un indice con tutti i giorni dell'intervallo
            idx_completo = pd.date_range(start=start_str, end=end_str)
            df_plot = df_time.reindex(idx_completo, fill_value=0)

        # Preparazione del DataFrame per Altair
        df_plot = df_plot.reset_index()
        df_plot.columns = ['Data', 'Totale']

        # Configurazione grafico Altair
        chart_time = alt.Chart(df_plot).mark_bar(
            size=19,
            cornerRadiusTopLeft=4,
            cornerRadiusTopRight=4,
            cornerRadiusBottomLeft=4, # Arrotonda anche la base per le barre negative
            cornerRadiusBottomRight=4,
            opacity=0.9
        ).encode(
            x=alt.X(
                'Data:T', 
                title=None, 
                axis=alt.Axis(
                    # Formatta le date in base alla vista: "05 Mag" o "Mag 2026"
                    format='%d %b' if vista != "Annuale (mesi)" else '%b %Y',
                    labelAngle=-45,
                    labelColor='#a3a8b8',
                    grid=False
                )
            ),
            y=alt.Y(
                'Totale:Q', 
                title="Importo (€)", 
                axis=alt.Axis(grid=True, gridColor='#333333', gridDash=[2, 2])
            ),
            # Formattazione condizionale: verde per le entrate, rosso tenue per le uscite
            color=alt.condition(
                alt.datum.Totale >= 0,
                alt.value('#2ecc71'), 
                alt.value('#ff4b4b')  
            ),
            tooltip=[
                alt.Tooltip('Data:T', title="Data", format='%d %m %Y' if vista != "Annuale (mesi)" else '%B %Y'),
                alt.Tooltip('Totale:Q', title="Totale (€)", format=",.2f")
            ]
        ).properties(
            height=380
        )

        st.altair_chart(chart_time, use_container_width=True)
    else:
        st.info("Nessuna transazione registrata nel periodo selezionato.")

with tab_categorie:
    if not df_cat.empty:
        df_cat['Totale'] = df_cat['Totale'].abs()
        df_cat = df_cat.sort_values('Totale', ascending=False)

        # Grafico Altair per Spese per Categoria
        chart_cat = alt.Chart(df_cat).mark_bar(cornerRadiusEnd=6, height=28).encode(
            x=alt.X('Totale:Q', title="Importo Speso (€)", axis=alt.Axis(format="~s", grid=True)),
            y=alt.Y('Categoria:N', sort='-x', title=None, axis=alt.Axis(labelAngle=0, labelFontSize=12)),
            color=alt.Color('Totale:Q', scale=alt.Scale(scheme='tealblues'), legend=None),
            tooltip=[
                alt.Tooltip('Categoria:N', title="Categoria"),
                alt.Tooltip('Totale:Q', title="Spesa Totale", format=",.2f")
            ]
        ).properties(
            height=max(180, len(df_cat) * 45)
        )

        st.altair_chart(chart_cat, use_container_width=True)
    else:
        st.info("Nessuna categoria assegnata nel periodo selezionato.")