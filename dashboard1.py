import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import plotly.express as px
import plotly.graph_objects as go
import io
from fredapi import Fred

from datetime import datetime
import matplotlib.pyplot as plt
# --------------------------------------
# SCRAPER Y TRANSFORMADOR DE DATOS
# --------------------------------------

@st.cache_data
def obtener_datos_tesoro(periodos):
    all_data = []
    headers = []
    for year in periodos:
        url = f'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve&field_tdr_date_value={year}'
        response = requests.get(url)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            table = soup.find('table', {'class': 'usa-table views-table views-view-table cols-26'})
            if table:
                headers = [header.text.strip() for header in table.find_all('th')]
                for row in table.find_all('tr')[1:]:
                    cells = [year] + [cell.text.strip() for cell in row.find_all('td')]
                    all_data.append(cells)

    if all_data:
        headers = ['Year'] + headers
        df = pd.DataFrame(all_data, columns=headers)
        df = df.drop(columns=['1.5 Mo'], errors='ignore')
        df = df.apply(lambda x: x.replace('N/A', pd.NA) if x.dtype == "object" else x)
        df = df.dropna(axis=1, how='all')
        df = df.fillna(0)
        for col in df.columns[2:]:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date")
        return df
    else:
        return pd.DataFrame()

# --------------------------------------
# FUNCIONES FRED
# --------------------------------------
    
def obtener_datos_fred():
    codigos = {
        # Labor Market
        "Total Nonfarm Payrolls": "PAYEMS",
        "Unemployment Rate": "UNRATE",
        "Labor Force Participation Rate": "CIVPART",
        "Job Openings (JOLTS)": "JTSJOL",
        "Average Hourly Earnings (Total Private)": "CES0500000003",
        "U-6 Unemployment Rate": "U6RATE",
        "Quits Rate (JOLTS)": "JTSQUR",

        # Credit/Market
        "Rating AAA": "BAMLC0A1CAAA",
        "Rating AA": "BAMLC0A2CAA",
        "Rating A": "BAMLC0A3CA",
        "Rating BBB": "BAMLC0A4CBBB",
        "BBB o superior": "BAMLC0A0CM",
        "High Yield": "BAMLH0A0HYM2EY",
        "Investment Grade": "BAMLC0A4CBBBEY",
        "Rating AAA ": "BAMLC0A1CAAASYTW",
        "Rating AA ": "BAMLC0A2CAASYTW",
        "Rating A ": "BAMLC0A3CASYTW",
        "Rating BBB ": "BAMLC0A4CBBBSYTW",
        "High Yield ": "BAMLH0A0HYM2SYTW",
        "10-Year Treasury Market Yield ": "DGS10",
        "5-Year Inflation Expectation ": "T5YIFR",
        "2-Year Treasury Market Yield ": "DGS2",
        "Rating AAA Corporate Yield ": "BAMLC0A1CAAAEY",
        
        # YTW bonds to economic zone
        "Global": "BAMLEMUBCRPIUSSYTW",
        "Euro": "BAMLEMEBCRPIESYTW",
        "Latin America": "BAMLEMRLCRPILASYTW",
        "Asia": "BAMLEMRACRPIASIASYTW",
        "EMEA": "BAMLEMRECRPIEMEASYTW"
    }
    datos = {}
    fred = Fred(api_key='762e2ee1c8fab5d038ce317929d47226')
    for nombre, codigo in codigos.items():
        serie = fred.get_series(codigo)
        serie.name = nombre
        datos[nombre] = serie
    return datos

def graficar_fred(datos, titulo, series, zoom=False):
    fig = go.Figure()
    for serie in series:
        data = datos[serie].tail(30) if zoom else datos[serie]
        fig.add_trace(go.Scatter(x=data.index, y=data.values, mode='lines', name=serie))
    fig.update_layout(title=titulo, xaxis_title="Fecha", yaxis_title="Valor", template="plotly_white")
    return fig

# --------------------------------------
# STREAMLIT UI
# --------------------------------------

st.set_page_config(layout="wide")
st.image("https://media.licdn.com/dms/image/v2/C4E0BAQHGRK4sbvBk8w/company-logo_200_200/company-logo_200_200/0/1664209061611/decision_capital_eirl_logo?e=2147483647&v=beta&t=dS9RqOZoCN82k_Jqg6JF9Fm7MAQlNUSfIrEuQdLg_qQ", 
         width=200)
st.title("Global Fixed Income Dashboard - Franco Olivares")

tab1, tab2, tab3 = st.tabs(["Treasury Yields", "US Corporate Bonds", "US Labor Market"])

# --------------------------------------
# TAB 1: CURVAS DEL TESORO
# --------------------------------------
with tab1:
    años = st.multiselect("Selecciona año(s):", list(range(2006, 2026)), default=[2025])
    df = obtener_datos_tesoro(años)

    if not df.empty:
        st.success(f"{df.shape[0]} registros obtenidos.")

        fechas = sorted(df["Date"].unique())
        fechas_seleccionadas = st.multiselect("Selecciona una o más fechas para comparar curvas:", fechas[-10:], default=fechas[-3:])

        if "10 Yr" in df.columns and "2 Yr" in df.columns:
            df["Spread 10Y - 2Y"] = df["10 Yr"] - df["2 Yr"]
            st.metric("📉 Spread 10Y - 2Y actual", f"{df['Spread 10Y - 2Y'].iloc[-1]:.2f} %")
            fig_spread = px.line(df, x="Date", y="Spread 10Y - 2Y", title="Evolución del Spread 10Y - 2Y")
            st.plotly_chart(fig_spread, use_container_width=True)

        st.subheader("Comparación de curvas por fecha")
        fig_comparacion = px.line()

        for fecha in fechas_seleccionadas:
            datos_fecha = df[df["Date"] == fecha].iloc[0]
            maturities = df.columns[2:-2]
            tasas = datos_fecha[maturities].values.astype(float)
            fig_comparacion.add_scatter(x=maturities, y=tasas, mode="lines+markers", name=str(fecha.date()))

        fig_comparacion.update_layout(title="Curvas de rendimiento comparadas", xaxis_title="Plazo", yaxis_title="Rendimiento (%)")
        st.plotly_chart(fig_comparacion, use_container_width=True)

        st.subheader("Rendimiento de los bonos del Tesoro a la par")
        df_anim = df.copy()
        df_anim = df_anim.melt(id_vars=["Date"], value_vars=maturities, var_name="Maturity", value_name="Yield")

        fig_anim = px.line(df_anim, x="Maturity", y="Yield", animation_frame=df_anim["Date"].dt.strftime("%Y-%m-%d"),
                        title="Evolución diaria de la curva de rendimiento")
        fig_anim.update_layout(xaxis_title="Plazo", yaxis_title="Rendimiento (%)")
        st.plotly_chart(fig_anim, use_container_width=True)

        st.subheader("Exportar datos")
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Yield Curve')
            if "Spread 10Y - 2Y" in df.columns:
                df[['Date', 'Spread 10Y - 2Y']].to_excel(writer, index=False, sheet_name='Spread')

        st.download_button(label="⬇️ Descargar Excel", data=output.getvalue(), file_name="treasury_yield_curve.xlsx")

    else:
        st.warning("No se encontraron datos para los años seleccionados.")

# --------------------------------------
# TAB 2: SPREADS FRED
# --------------------------------------
with tab2:
    st.subheader("Spreads de bonos corporativos ajustado por cualquier opcionalidad(OAS) en USA")

    datos_fred = obtener_datos_fred()
    series_ids = ["Rating AAA", "Rating AA", "Rating A", "Rating BBB", "High Yield"]
    series_ids2 = ["Rating AAA ", "Rating AA ", "Rating A ", "Rating BBB ", "High Yield "]
    if datos_fred:
        fig_fred = graficar_fred(datos_fred, "Spreads de bonos corporativos por calificación", series_ids)
        st.plotly_chart(fig_fred, use_container_width=True)

        st.subheader("Emerging Markets - YTW")
        fig3 = graficar_fred(datos_fred, "ICE BofA Emerging Markets Corporate Plus Index Semi-Annual Yield to Worst", ["Global", "Euro", "Latin America", "Asia", "EMEA"])
        st.plotly_chart(fig3, use_container_width=True)

        st.subheader("US Investment Grade vs US High Yield - YTW")
        fig4 = graficar_fred(datos_fred, "ICE BofA US Index Semi-Annual Yield to Worst", ["Rating AAA ", "Rating AA ", "Rating A ", "Rating BBB ", "High Yield "])
        st.plotly_chart(fig4, use_container_width=True)
        
        st.subheader("US bond yields vs. Median of US 5-year inflation expectation")
        fig5 = graficar_fred(datos_fred, "Bonos de alta calidad vs. Inflación esperada a 5 años(media) en USA", ["10-Year Treasury Market Yield ", "2-Year Treasury Market Yield ", "5-Year Inflation Expectation ", "Rating AAA Corporate Yield "])
        st.plotly_chart(fig5, use_container_width=True)        
        
        

# --------------------------------------
# TAB 3: MERCADO LABORAL (FRED)
# --------------------------------------
with tab3:
    st.subheader("Análisis del Mercado Laboral en USA")

    codigos_laborales = {
    "Tasa de desempleo": "UNRATE",
    "Nonfarm Payrolls": "PAYEMS",
    "Ofertas laborales (JOLTS)": "JTSJOL",
    "Renuncias (Quit Rate)": "JTSQUR",
    "Participación laboral": "CIVPART",
    "Initial Claims (ICSA)": "ICSA"
    }


    fred = Fred(api_key='762e2ee1c8fab5d038ce317929d47226')
    datos_laborales = {}

    for nombre, codigo in codigos_laborales.items():
        serie = fred.get_series(codigo)
        serie.name = nombre
        datos_laborales[nombre] = serie.dropna()



    z_scores = {}
    resumen_tabla = []

    for nombre, serie in datos_laborales.items():
        serie = serie.dropna()
        z = (serie - serie.mean()) / serie.std()
        z_scores[nombre] = z
        actual = serie.iloc[-1]
        promedio = serie.mean()
        desv = serie.std()
        z_actual = z.iloc[-1]
        resumen_tabla.append({
            "Indicador": nombre,
            "Último valor": round(actual, 2),
            "Promedio histórico": round(promedio, 2),
            "Z-Score actual": round(z_actual, 2),
            "Desviación estándar": round(desv, 2)
        })

    df_resumen = pd.DataFrame(resumen_tabla).sort_values("Z-Score actual", ascending=False)

    # Tabla resumida
    # Formato con separadores de miles y semáforo de alerta por Z-Score
    def formato_numero(x):
        if isinstance(x, (int, float)):
            return f"{x:,.2f}"
        return x

    def semaforo(z):
        if z > 1:
            return "🔴"
        elif z < -1:
            return "🔵"
        else:
            return "⚪️"

    df_resumen["Alerta"] = df_resumen["Z-Score actual"].apply(semaforo)
    columnas_format = ["Último valor", "Promedio histórico", "Z-Score actual", "Desviación estándar"]
    for col in columnas_format:
        df_resumen[col] = df_resumen[col].apply(formato_numero)

    # Ordenamos para que el semáforo aparezca al principio
    df_resumen = df_resumen[["Alerta", "Indicador"] + columnas_format]

    st.markdown("### Resumen estadístico con alerta visual")
    st.dataframe(df_resumen, use_container_width=True, height=350)


    # Gráfico de barras horizontales tipo Z-Score
    fig_z = px.bar(df_resumen, x="Z-Score actual", y="Indicador", orientation='h',
                   color="Z-Score actual", color_continuous_scale="RdBu_r",
                   title=" Desviación Estándar de Indicadores respecto a su Media Histórica")
    fig_z.update_layout(height=400, xaxis_title="Z-Score", yaxis_title="", template="plotly_white")
    st.plotly_chart(fig_z, use_container_width=True)


    # Preparamos los Z-Scores para el heatmap (excluyendo ICSA)
    df_z_all = pd.DataFrame(z_scores)
    df_z_all.index = pd.to_datetime(df_z_all.index)
    df_z_all = df_z_all.resample("M").mean().interpolate()
    df_z_all = df_z_all[df_z_all.index >= "2018"]

# Excluir ICSA del heatmap si está presente
    if "Initial Claims (ICSA)" in df_z_all.columns: df_z_heatmap = df_z_all.drop(columns=["Initial Claims (ICSA)"])
    else: df_z_heatmap = df_z_all.copy()
    fig_heat = px.imshow(df_z_heatmap.T,
                     aspect="auto",
                     color_continuous_scale="RdBu_r",
                     labels=dict(x="Fecha", y="Indicador", color="Z-Score"),
                     title="Mapa de Calor: ¿Qué tan lejos están los indicadores de su media?")
    fig_heat.update_layout(height=500)
    st.plotly_chart(fig_heat, use_container_width=True)

   # Nuevo gráfico solo para ICSA
    st.markdown("### Evolución de Solicitudes por Desempleo en USA (ICSA)")

# Serie original completa
    icsa = datos_laborales["Initial Claims (ICSA)"]

# Calcular métricas
    z_icsa = (icsa - icsa.mean()) / icsa.std()
    pct_icsa = icsa.pct_change() * 100

# Selector de métrica
    opcion_icsa = st.radio(
    " Métrica a visualizar de ICSA:",
    ["Variación porcentual", "Z-Score", "Nivel absoluto"],
    horizontal=True)

# Escoger la serie base
if opcion_icsa == "Variación porcentual": 
    serie_base = pct_icsa
    titulo = "Variación Porcentual de Solicitudes Iniciales por Desempleo (ICSA)"
    y_label = "% Variación"
elif opcion_icsa == "Z-Score": 
    serie_base = z_icsa
    titulo = "Z-Score de Solicitudes Iniciales por Desempleo (ICSA)"
    y_label = "Z-Score"
else:
    serie_base = icsa
    titulo = "Nivel Absoluto de Solicitudes Iniciales por Desempleo (ICSA)"
    y_label = "Solicitudes"

# Rango de fechas disponible
fecha_min = icsa.index.min().to_pydatetime()
fecha_max = icsa.index.max().to_pydatetime()

# Valor por defecto: mostrar desde 2018
fecha_defecto_inicio = pd.to_datetime("2018-01-01").to_pydatetime()

# Slider de fechas
fecha_slider = st.slider("Rango de fechas para visualizar:", min_value=fecha_min, max_value=fecha_max, value=(fecha_defecto_inicio, fecha_max), format="YYYY-MM")

# Filtrar serie según selección
serie_filtrada = serie_base[(serie_base.index >= fecha_slider[0]) & (serie_base.index <= fecha_slider[1])]

# Crear gráfico
fig_icsa = px.line(serie_filtrada, title=titulo, labels={"value": y_label, "index": "Fecha"})
    # Sombrear períodos históricos relevantes
eventos = [
        {"x0": "1973-10-01", "x1": "1974-03-01", "color": "LightGray", "texto": "Crisis OPEP"},
        {"x0": "1980-01-01", "x1": "1982-08-01", "color": "Thistle", "texto": "Volcker Shock"},
        {"x0": "2000-03-01", "x1": "2002-10-01", "color": "LightSalmon", "texto": "Crisis punto-com"},
        {"x0": "2007-12-01", "x1": "2009-06-01", "color": "LightSalmon", "texto": "Lehman Brothers"},
        {"x0": "2018-07-01", "x1": "2020-01-01", "color": "LightBlue", "texto": "Trump's Tariffs"},
        {"x0": "2020-03-01", "x1": "2021-07-01", "color": "LightSalmon", "texto": "COVID-19"},
        {"x0": "2025-01-20", "x1": "2025-06-01", "color": "LightBlue", "texto": "Trump's Tariffs II"}
    ]

for evento in eventos:
        fig_icsa.add_vrect(x0=evento["x0"], x1=evento["x1"],
                           fillcolor=evento["color"], opacity=0.15, layer="below", line_width=0,
                           annotation_text=evento["texto"], annotation_position="top left")

fig_icsa.update_layout(template="plotly_white", height=400)
st.plotly_chart(fig_icsa, use_container_width=True)







