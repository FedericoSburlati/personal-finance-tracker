import streamlit as st
import altair as alt
from db import run_query
import pandas as pd
from datetime import timedelta, date
import calendar

st.set_page_config(page_title="Personal Finance", page_icon="💸", layout="wide")

###
# MODIFICHE CSS PER MIGLIORARE L'ESTETICA
st.markdown("""
<style>
    /* Card Glassmorphism con profilo arrotondato continuo e ombre */
    .glass-card {
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(18px);
        -webkit-backdrop-filter: blur(18px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 22px;
        padding: 22px 20px;
        box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.55), 
                    inset 0 1px 1px 0 rgba(255, 255, 255, 0.12);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }

    .glass-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 14px 34px -8px rgba(0, 0, 0, 0.7), 
                    inset 0 1px 2px 0 rgba(255, 255, 255, 0.18);
    }

    /* Tipografia interna alle card */
    .card-label {
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        font-weight: 600;
        color: #94a3b8;
        margin-bottom: 6px;
    }

    .card-num {
        font-size: 1.85rem;
        font-weight: 700;
        letter-spacing: -0.02em;
    }
    .cat-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 14px;
        margin-bottom: 8px;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 12px;
        backdrop-filter: blur(10px);
    }
    .cat-row:hover {
        background: rgba(255, 255, 255, 0.06);
        border-color: rgba(255, 255, 255, 0.12);
    }
    .cat-name {
        font-size: 0.9rem;
        font-weight: 500;
        color: #e2e8f0;
    }
    .cat-val {
        font-size: 0.92rem;
        font-weight: 700;
        color: #f8fafc;
    }
    .cat-pct {
        font-size: 0.78rem;
        color: #94a3b8;
        margin-left: 6px;
    }

    /* Colori semantici */
    .c-saldo { color: #f8fafc; }
    .c-entrate { color: #34d399; }
    .c-uscite { color: #f87171; }
</style>
""", unsafe_allow_html=True)
###


st.header("💸 Dashboard Finanziaria")
st.write("Monitoraggio e categorizzazione automatica delle transazioni bancarie.")
st.caption("*Portfolio* | **Sburlati Federico**")

st.divider()

st.subheader("Panoramica Mensile")
met1, met2, met3 = st.columns(3)

# query con COALESCE per forzare 0 al posto di NULL se la tabella è vuota
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

#MODIFICA METRICHE IN CSS
with met1:
    st.markdown(f"""
    <div class="glass-card">
        <div class="card-label">💼 Saldo Globale</div>
        <div class="card-num c-saldo">{format_currency(val_saldo)}</div>
    </div>
    """, unsafe_allow_html=True)

with met2:
    st.markdown(f"""
    <div class="glass-card">
        <div class="card-label">📈 Totale Entrate</div>
        <div class="card-num c-entrate">{format_currency(val_entrate)}</div>
    </div>
    """, unsafe_allow_html=True)

with met3:
    st.markdown(f"""
    <div class="glass-card">
        <div class="card-label">📉 Totale Uscite</div>
        <div class="card-num c-uscite">{format_currency(abs(float(val_uscite)))}</div>
    </div>
    """, unsafe_allow_html=True)

###

st.subheader("📊 Analisi Spese Interattiva")

# FILTRI TEMPORALI GLOGABI
st.write("### Seleziona il periodo di analisi")

# rilevamento dinamico degli anni e della data più recente presente nel DB per selezione periodo di tempo
anni_db = run_query("""
    SELECT DISTINCT YEAR(CASE WHEN Data LIKE '__-__-____' THEN STR_TO_DATE(Data, '%d-%m-%Y') ELSE Data END) as anno 
    FROM TRANSAZIONE 
    WHERE Data IS NOT NULL 
    ORDER BY anno DESC
""")
anni_disponibili = [int(a) for a in anni_db['anno'].dropna().tolist()] if not anni_db.empty else [2026, 2025, 2024]
if not anni_disponibili:
    anni_disponibili = [date.today().year]

max_d_query = run_query("SELECT MAX(CASE WHEN Data LIKE '__-__-____' THEN STR_TO_DATE(Data, '%d-%m-%Y') ELSE Data END) as max_d FROM TRANSAZIONE")
data_default = pd.to_datetime(max_d_query['max_d'][0]).date() if not max_d_query.empty and pd.notna(max_d_query['max_d'][0]) else date.today()

col_vista, col_dettaglio = st.columns(2)
#selezione lasso di tempo
with col_vista:
    vista = st.radio(
        "Granularità:",
        ["Settimanale (giorni)", "Mensile (giorni)", "Annuale (mesi)"],
        horizontal=True
    )

# Calcolo dinamico di start_date ed end_date
with col_dettaglio:
    if vista == "Settimanale (giorni)":
        data_sel = st.date_input("Seleziona un giorno qualsiasi della settimana:", value=data_default, format="DD/MM/YYYY")
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
            idx_anno_def = anni_disponibili.index(data_default.year) if data_default.year in anni_disponibili else 0
            anno_sel = st.selectbox("Anno", anni_disponibili, index=idx_anno_def)
        with col_mese:
            mese_sel = st.selectbox("Mese", list(mesi_dict.keys()), index=data_default.month - 1)
        
        num_mese = mesi_dict[mese_sel]
        start_date = date(anno_sel, num_mese, 1)
        _, ultimo_giorno = calendar.monthrange(anno_sel, num_mese) 
        end_date = date(anno_sel, num_mese, ultimo_giorno)

    else: # Annuale
        idx_anno_def = anni_disponibili.index(data_default.year) if data_default.year in anni_disponibili else 0
        anno_sel = st.selectbox("Anno di analisi", anni_disponibili, index=idx_anno_def)
        start_date = date(anno_sel, 1, 1)
        end_date = date(anno_sel, 12, 31)

# Conversione in formato ISO per garantire il filtraggio su MySQL
start_iso = start_date.strftime('%Y-%m-%d')
end_iso = end_date.strftime('%Y-%m-%d')


#ESTRAZIONE DATI FILTRATI
# Query per l'andamento nel tempo
query_time = f"""
    SELECT 
        (CASE WHEN T.Data LIKE '__-__-____' THEN STR_TO_DATE(T.Data, '%d-%m-%Y') ELSE T.Data END) as Data,
        SUM(T.Importo) as Totale 
    FROM TRANSAZIONE T
    WHERE (CASE WHEN T.Data LIKE '__-__-____' THEN STR_TO_DATE(T.Data, '%d-%m-%Y') ELSE T.Data END) 
          BETWEEN '{start_iso}' AND '{end_iso}'
    GROUP BY 1 
    ORDER BY 1
"""
df_time = run_query(query_time)

# Query per le categorie (solo uscite, ignorando i giroconti)
query_cat = f"""
    SELECT T.Categoria, SUM(T.Importo) as Totale 
    FROM TRANSAZIONE T 
    WHERE (CASE WHEN T.Data LIKE '__-__-____' THEN STR_TO_DATE(T.Data, '%d-%m-%Y') ELSE T.Data END) 
          BETWEEN '{start_iso}' AND '{end_iso}'
      AND T.Importo < 0 
      AND T.Categoria <> 'Giroconto' 
    GROUP BY T.Categoria
"""
df_cat = run_query(query_cat)


#TAB VISUALIZZAZIONI
tab_andamento, tab_categorie = st.tabs(["📈 Andamento nel Tempo", "🏷️ Spese per Categoria"])

with tab_andamento:
    if not df_time.empty:
        df_time['Data'] = pd.to_datetime(df_time['Data'], dayfirst=True)
        df_time.set_index('Data', inplace=True)

        if vista == "Annuale (mesi)":
            try:
                df_plot = df_time.resample('ME').sum()
            except ValueError:
                df_plot = df_time.resample('M').sum()
        else:
            # se siamo nel mese/settimana corrente, si limita l'asse alla data odierna per non avere il vuoto a destra
            data_fine_effettiva = min(end_date, date.today()) if start_date <= date.today() <= end_date else end_date
            idx_completo = pd.date_range(start=start_date, end=data_fine_effettiva)
            df_plot = df_time.reindex(idx_completo, fill_value=0)

        df_plot = df_plot.reset_index()
        df_plot.columns = ['Data', 'Totale']

        # Calcolo larghezza dinamica delle barre
        n_punti = len(df_plot)
        bar_size = max(12, min(36, int(600 / max(n_punti, 1))))

        #estetica
        with st.container(border=True):
            # 1. Barre dell'andamento
            bars = alt.Chart(df_plot).mark_bar(
                size=bar_size,
                cornerRadiusTopLeft=5,
                cornerRadiusTopRight=5,
                cornerRadiusBottomLeft=5,
                cornerRadiusBottomRight=5,
                opacity=0.9
            ).encode(
                x=alt.X(
                    'Data:T', 
                    title=None, 
                    axis=alt.Axis(
                        format='%d/%m/%Y' if vista != "Annuale (mesi)" else '%m/%Y',
                        labelAngle=-40,
                        labelColor='#94a3b8',
                        labelFontSize=11,
                        grid=False,
                        tickColor='rgba(255, 255, 255, 0.1)'
                    )
                ),
                y=alt.Y(
                    'Totale:Q', 
                    title="Importo Netto (€)", 
                    axis=alt.Axis(
                        grid=True, 
                        gridColor='rgba(255, 255, 255, 0.05)', 
                        gridDash=[3, 3],
                        labelColor='#94a3b8',
                        titleColor='#94a3b8',
                        format=",.2f"
                    )
                ),
                color=alt.condition(
                    alt.datum.Totale >= 0,
                    alt.value('#34d399'), 
                    alt.value('#f87171')  
                ),
                tooltip=[
                    alt.Tooltip('Data:T', title="Data", format='%d/%m/%Y'),
                    alt.Tooltip('Totale:Q', title="Totale (€)", format=",.2f")
                ]
            )

            # 2. Linea di riferimento sullo zero
            zero_rule = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(
                color='rgba(255, 255, 255, 0.25)',
                strokeWidth=1.2,
                strokeDash=[4, 4]
            ).encode(y='y:Q')

            chart_final = (bars + zero_rule).properties(
                height=350
            ).configure_view(
                strokeOpacity=0
            ).configure(
                background='transparent'
            )

            st.altair_chart(chart_final, use_container_width=True)
    else:
        st.info("Nessuna transazione registrata nel periodo selezionato.")

with tab_categorie:
    if not df_cat.empty:
        df_cat['Totale'] = df_cat['Totale'].abs()
        df_cat = df_cat.sort_values('Totale', ascending=False)

        totale_spese = float(df_cat['Totale'].sum())
        df_cat['Percentuale'] = (df_cat['Totale'] / totale_spese) * 100

        #estetica contenitore grafico
        with st.container(border=True):
            col_chart, col_details = st.columns([1.3, 1], gap="medium")

            with col_chart:
                #base donut plot
                base_chart = alt.Chart(df_cat).encode(
                    theta=alt.Theta(field="Totale", type="quantitative", stack=True)
                )

                donut = base_chart.mark_arc(
                    innerRadius=95,
                    outerRadius=145,
                    cornerRadius=6,
                    padAngle=0.03
                ).encode(
                    color=alt.Color(
                        field="Categoria", 
                        type="nominal",
                        scale=alt.Scale(scheme='category10'),
                        legend=None  # Nascondiamo la legenda standard, ora gestita dalla card a destra
                    ),
                    tooltip=[
                        alt.Tooltip('Categoria:N', title="Categoria"),
                        alt.Tooltip('Totale:Q', title="Spesa Totale (€)", format=",.2f"),
                        alt.Tooltip('Percentuale:Q', title="Incidenza (%)", format=".1f")
                    ]
                )

                # testo cifra totale al centro del donut plot
                text_importo = alt.Chart(pd.DataFrame({'tot': [totale_spese]})).mark_text(
                    text=f"€ {totale_spese:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                    fontSize=21,
                    fontWeight=700,
                    color="#f8fafc",
                    yOffset=-6
                )

                # etichetta sotto l'importo al centro
                text_label = alt.Chart(pd.DataFrame({'txt': ['Totale Speso']})).mark_text(
                    text="Totale Speso",
                    fontSize=11,
                    fontWeight=600,
                    color="#94a3b8",
                    yOffset=16
                )

                # combinazione layer al centro
                chart_composto = (donut + text_importo + text_label).properties(
                    height=350
                ).configure_view(
                    strokeOpacity=0
                ).configure(
                    background='transparent'
                )

                st.altair_chart(chart_composto, use_container_width=True)

            with col_details:
                st.markdown("#### Principali Categorie")
                
                # visualizzazione top5 categorie
                for _, row in df_cat.head(5).iterrows():
                    valore_formattato = f"€ {row['Totale']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    st.markdown(f"""
                    <div class="cat-row">
                        <span class="cat-name">{row['Categoria']}</span>
                        <div>
                            <span class="cat-val">{valore_formattato}</span>
                            <span class="cat-pct">({row['Percentuale']:.1f}%)</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                # se categorie > 5, Altre()
                if len(df_cat) > 5:
                    altre_tot = df_cat.iloc[5:]['Totale'].sum()
                    altre_pct = (altre_tot / totale_spese) * 100
                    altre_formattato = f"€ {altre_tot:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    st.markdown(f"""
                    <div class="cat-row" style="opacity: 0.75;">
                        <span class="cat-name">Altre ({len(df_cat)-5})</span>
                        <div>
                            <span class="cat-val">{altre_formattato}</span>
                            <span class="cat-pct">({altre_pct:.1f}%)</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
    else:
        st.info("Nessuna spesa o categoria assegnata nel periodo selezionato.")