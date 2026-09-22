"""
Pagina: Pagina principale

Funzionalità:
- Visualizzazione totali
- Visualizzaizone grafici con filtraggio per periodo di tempo
- Visualizzazione generica di entrate/uscite o suddivisione per categoria
"""

import streamlit as st
import pandas as pd
import altair as alt
from datetime import timedelta, date
import calendar
from src.database.db import run_query

st.set_page_config(page_title="Personal Finance", page_icon="💸", layout="wide")

st.title("💸 Dashboard Finanziaria")
st.caption("Monitoraggio delle spese personali e analisi dei flussi di cassa")

st.divider()

st.subheader("Panoramica Globale")

# i giroconti vengono esclusi dalle uscite per non alterare il calcolo delle spese reali
saldo_query = run_query("SELECT COALESCE(SUM(T.Importo), 0) AS tot FROM TRANSAZIONE T")
entrate_query = run_query("SELECT COALESCE(SUM(T.Importo), 0) AS tot FROM TRANSAZIONE T WHERE T.Importo > 0")
uscite_query = run_query(
    "SELECT COALESCE(SUM(T.Importo), 0) AS tot "
    "FROM TRANSAZIONE T "
    "WHERE T.Importo < 0 AND T.Categoria <> 'Giroconto'"
)

val_saldo = float(saldo_query["tot"].iloc[0]) if not saldo_query.empty else 0.0
val_entrate = float(entrate_query["tot"].iloc[0]) if not entrate_query.empty else 0.0
val_uscite = abs(float(uscite_query["tot"].iloc[0])) if not uscite_query.empty else 0.0

col_saldo, col_entrate, col_uscite = st.columns(3)

with col_saldo:
    with st.container(border=True):
        st.metric(label="Saldo Globale", value=f"€ {val_saldo:,.2f}")

with col_entrate:
    with st.container(border=True):
        st.metric(label="Totale Entrate", value=f"€ {val_entrate:,.2f}")

with col_uscite:
    with st.container(border=True):
        st.metric(label="Totale Uscite", value=f"€ {val_uscite:,.2f}")

st.divider()

#FILTRI TEMPORALI
st.subheader("Analisi Dettagliata")

anni_db = run_query("""
    SELECT DISTINCT YEAR(T.Data) AS anno 
    FROM TRANSAZIONE T 
    WHERE T.Data IS NOT NULL 
    ORDER BY anno DESC
""")
anni_disponibili = [int(a) for a in anni_db["anno"].dropna().tolist()] if not anni_db.empty else [date.today().year]

max_d_query = run_query("SELECT MAX(T.Data) AS max_d FROM TRANSAZIONE T")
data_default = (
    pd.to_datetime(max_d_query["max_d"].iloc[0]).date()
    if not max_d_query.empty and pd.notna(max_d_query["max_d"].iloc[0])
    else date.today()
)

col_vista, col_dettaglio = st.columns([1, 2])

with col_vista:
    vista = st.radio(
        "Intervallo temporale:",
        ["Settimanale", "Mensile", "Annuale"],
        horizontal=True
    )

with col_dettaglio:
    if vista == "Settimanale":
        data_sel = st.date_input("Giorno di riferimento:", value=data_default, format="DD/MM/YYYY")
        start_date = data_sel - timedelta(days=data_sel.weekday())
        end_date = start_date + timedelta(days=6)
        st.caption(f"Finestra attiva: {start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}")

    elif vista == "Mensile":
        col_mese, col_anno = st.columns(2)
        mesi_nomi = [
            "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
            "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"
        ]
        with col_anno:
            idx_anno_def = anni_disponibili.index(data_default.year) if data_default.year in anni_disponibili else 0
            anno_sel = st.selectbox("Anno", anni_disponibili, index=idx_anno_def)
        with col_mese:
            mese_sel = st.selectbox("Mese", mesi_nomi, index=data_default.month - 1)
        
        num_mese = mesi_nomi.index(mese_sel) + 1
        start_date = date(anno_sel, num_mese, 1)
        _, ultimo_giorno = calendar.monthrange(anno_sel, num_mese)
        end_date = date(anno_sel, num_mese, ultimo_giorno)

    else:
        idx_anno_def = anni_disponibili.index(data_default.year) if data_default.year in anni_disponibili else 0
        anno_sel = st.selectbox("Anno di riferimento", anni_disponibili, index=idx_anno_def)
        start_date = date(anno_sel, 1, 1)
        end_date = date(anno_sel, 12, 31)

start_iso = start_date.strftime("%Y-%m-%d")
end_iso = end_date.strftime("%Y-%m-%d")

query_time = """
    SELECT 
        T.Data AS Data,
        SUM(T.Importo) AS Totale 
    FROM TRANSAZIONE T
    WHERE T.Data BETWEEN :start_date AND :end_date
    GROUP BY T.Data 
    ORDER BY T.Data
"""
df_time = run_query(query_time, params={"start_date": start_iso, "end_date": end_iso})

query_cat = """
    SELECT T.Categoria, SUM(T.Importo) AS Totale 
    FROM TRANSAZIONE T 
    WHERE T.Data BETWEEN :start_date AND :end_date
      AND T.Importo < 0 
      AND T.Categoria <> 'Giroconto' 
    GROUP BY T.Categoria
"""
df_cat = run_query(query_cat, params={"start_date": start_iso, "end_date": end_iso})

# GRAFICI
tab_andamento, tab_categorie = st.tabs(["📈 Andamento Temporale", "🏷️ Spese per Categoria"])

with tab_andamento:
    if not df_time.empty:
        df_time["Data"] = pd.to_datetime(df_time["Data"])
        df_time.set_index("Data", inplace=True)

        if vista == "Annuale":
            try:
                df_plot = df_time.resample("ME").sum()
            except ValueError:
                df_plot = df_time.resample("M").sum()
        else:
            fine_finestra = min(end_date, date.today()) if start_date <= date.today() <= end_date else end_date
            idx_range = pd.date_range(start=start_date, end=fine_finestra)
            df_plot = df_time.reindex(idx_range, fill_value=0)

        df_plot = df_plot.reset_index()
        df_plot.columns = ["Data", "Totale"]

        n_punti = len(df_plot)
        bar_size = max(10, min(32, int(500 / max(n_punti, 1))))

        with st.container(border=True):
            bars = alt.Chart(df_plot).mark_bar(
                size=bar_size,
                cornerRadiusTopLeft=4,
                cornerRadiusTopRight=4,
                cornerRadiusBottomLeft=4,
                cornerRadiusBottomRight=4
            ).encode(
                x=alt.X(
                    "Data:T",
                    title=None,
                    axis=alt.Axis(
                        format="%d/%m" if vista != "Annuale" else "%b %Y",
                        labelAngle=-30
                    )
                ),
                y=alt.Y("Totale:Q", title="Netto (€)", axis=alt.Axis(format=",.2f")),
                color=alt.condition(
                    alt.datum.Totale >= 0,
                    alt.value("#34d399"),
                    alt.value("#f87171")
                ),
                tooltip=[
                    alt.Tooltip("Data:T", title="Data", format="%d/%m/%Y"),
                    alt.Tooltip("Totale:Q", title="Totale (€)", format=",.2f")
                ]
            )

            zero_line = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(
                strokeDash=[4, 4],
                strokeWidth=1
            ).encode(y="y:Q")

            chart_final = (bars + zero_line).properties(height=340).configure_view(strokeOpacity=0)
            st.altair_chart(chart_final, use_container_width=True)
    else:
        st.info("Nessuna transazione registrata nel periodo selezionato.")

with tab_categorie:
    if not df_cat.empty:
        df_cat["Totale"] = df_cat["Totale"].abs()
        df_cat = df_cat.sort_values("Totale", ascending=False)
        totale_spese = float(df_cat["Totale"].sum())
        df_cat["Percentuale"] = (df_cat["Totale"] / totale_spese) * 100

        with st.container(border=True):
            col_chart, col_table = st.columns([1.2, 1], gap="medium")

            with col_chart:
                donut = alt.Chart(df_cat).mark_arc(
                    innerRadius=85,
                    outerRadius=135,
                    padAngle=0.02
                ).encode(
                    theta=alt.Theta("Totale:Q", stack=True),
                    color=alt.Color("Categoria:N", scale=alt.Scale(scheme="category10"), legend=None),
                    tooltip=[
                        alt.Tooltip("Categoria:N"),
                        alt.Tooltip("Totale:Q", title="Spesa (€)", format=",.2f"),
                        alt.Tooltip("Percentuale:Q", title="Incidenza", format=".1f")
                    ]
                )

                label_totale = alt.Chart(pd.DataFrame({"val": [totale_spese]})).mark_text(
                    text=f"€ {totale_spese:,.2f}",
                    fontSize=19,
                    fontWeight=600,
                    yOffset=-6,
                    color="#94a3b8"
                )

                label_desc = alt.Chart(pd.DataFrame({"txt": ["Uscite Totali"]})).mark_text(
                    text="Uscite Totali",
                    fontSize=11,
                    yOffset=14,
                    color="#94a3b8"
                )

                donut_chart = (donut + label_totale + label_desc).properties(height=330).configure_view(strokeOpacity=0)
                st.altair_chart(donut_chart, use_container_width=True)

            with col_table:
                st.markdown("##### Ripartizione Spese")
                st.dataframe(
                    df_cat,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "Categoria": st.column_config.TextColumn("Categoria", width="medium"),
                        "Totale": st.column_config.NumberColumn("Importo", format="€ %.2f", width="small"),
                        "Percentuale": st.column_config.ProgressColumn(
                            "Incidenza",
                            format="%.1f%%",
                            min_value=0.0,
                            max_value=100.0,
                            width="small"
                        )
                    }
                )
    else:
        st.info("Nessuna spesa registrata nel periodo selezionato.")