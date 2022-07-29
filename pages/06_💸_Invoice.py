import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import altair as alt
import xlrd

st.set_page_config(layout="wide")


@st.experimental_singleton
def init_engine():
    return create_engine(
        f"postgresql://"
        f'{st.secrets["postgres"]["user"]}:'
        f'{st.secrets["postgres"]["password"]}@'
        f'{st.secrets["postgres"]["host"]}:'
        f'{st.secrets["postgres"]["port"]}/'
        f'{st.secrets["postgres"]["dbname"]}',
    )


engine = init_engine()


def check_credentials():
    if (
        not st.session_state.username
        or not st.session_state.password
        or st.session_state.username not in st.secrets.keys()
        or st.secrets[st.session_state.username] != st.session_state.password
    ):
        st.warning("Tente novamente")
        return
    else:
        st.session_state.user = st.session_state.username
        return


def login():
    with st.form("login"):
        st.text_input("Username", key="username")
        st.text_input("Password", key="password", type="password")
        st.form_submit_button("Login", on_click=check_credentials)


def upload_files():
    stored_df, _ = get_stored_data()

    uploaded_files = st.file_uploader(
        "",
        type="xlsb",
        accept_multiple_files=True,
    )

    uploaded_df = pd.DataFrame()
    if uploaded_files:
        for file in uploaded_files:
            file_df = pd.read_excel(file, None)
            df = process_file_df(file_df)
            uploaded_df = pd.concat([uploaded_df, df])
        uploaded_df = pd.concat([stored_df, uploaded_df, stored_df]).drop_duplicates(
            keep=False,
        )
        if not uploaded_df.empty:
            uploaded_df.to_sql("honorarios", engine, if_exists="append", index=False)
            st.success("Ficheiro actualizado")
        else:
            st.info("Sem entradas novas")
        st.experimental_memo.clear()


def from_excel_datetime(x):
    return xlrd.xldate_as_datetime(x, 0)


def process_df(df):
    df = df[::-1].reset_index(drop=True)
    last_row = df[df["Unnamed: 0"] == "Ano"].index[0]
    df.columns = df.iloc[last_row]
    df = df.iloc[1:last_row]
    df = df[
        [
            "Ano",
            "Nº Exame",
            "Entrada",
            "Expedido",
            "Exame",
            "Entidade",
            "Plano SS",
            "PVP",
            "% Hon.",
            "Honorários",
        ]
    ]
    df.columns = [
        "ano",
        "nr_exame",
        "entrada",
        "expedido",
        "tipo_exame",
        "entidade",
        "plano",
        "pvp",
        "percentagem",
        "honorarios",
    ]
    df[["entrada", "expedido"]] = df[["entrada", "expedido"]].applymap(
        from_excel_datetime
    )
    df.honorarios = round(df.honorarios.astype(float), 3)
    return df


def process_file_df(file_df):
    hluz = process_df(file_df["Actividade HLUZ"])
    torres = process_df(file_df["Actividade HLTL"])
    odivelas = process_df(file_df["Actividade HLOD"])
    hba = process_df(file_df["Actividade HBA"])
    cca = process_df(file_df["Actividade CCA"])
    cpp = process_df(file_df["Actividade CPP"])
    df = (
        pd.concat([hluz, torres, odivelas, hba, cpp, cca], ignore_index=True)
        .sort_values(by="entrada")
        .reset_index(drop=True)
    )
    return df


@st.experimental_memo
def get_stored_data():
    return pd.read_sql(
        "SELECT * FROM honorarios", engine, parse_dates=["entrada", "expedido"]
    ), pd.read_sql(
        "SELECT * FROM sispat WHERE sispat.patologista = 'Dr. João Cassis'",
        engine,
        parse_dates=["entrada", "expedido"],
    )


def check_susana(df, sispat):
    with st.form("cotovio"):
        cols = st.columns(2)
        mes = cols[0].selectbox("Mês", df.expedido.dt.month.sort_values().unique())
        ano = cols[1].selectbox("Ano", df.expedido.dt.year.sort_values().unique())
        ok = st.form_submit_button("Confirmar")
    if ok:
        df = df[(df.expedido.dt.year == ano) & (df.expedido.dt.month == mes)]
        if df.empty:
            st.warning("Escolha uma data válida")
            st.stop()
        sispat = sispat[
            (sispat.expedido.dt.year == ano)
            & (sispat.expedido.dt.month == mes)
            & ~(sispat.tipo_exame.str.contains("Aditamento"))
            & ~(sispat.tipo_exame.str.contains("Tipagem"))
        ]
        diff = list(set(sispat.nr_exame.tolist()) - set(df.nr_exame.tolist()))
        diff = sispat[sispat.nr_exame.isin(diff)]
        if diff.empty:
            st.success("Tudo contemplado")
        else:
            st.write(diff)


def honorarios_por_exame(df):
    luz = df[~df.tipo_exame.str.contains("hba", case=False)]
    hba = df[df.tipo_exame.str.contains("hba", case=False)]
    cols = st.columns(2)
    cols[0].table(
        luz.groupby("tipo_exame")
        .honorarios.agg(["count", "min", "mean", "max"])
        .sort_values(by="count", ascending=False)
    )
    cols[1].table(
        hba.groupby("tipo_exame")
        .honorarios.agg(["count", "min", "mean", "max"])
        .sort_values(by="count", ascending=False)
    )


def pvp_por_entidade(df):
    df = df[
        (~df.tipo_exame.str.contains("hba", case=False))
        & ~(df.tipo_exame.str.contains("citologia", case=False))
    ]
    selection = st.selectbox("Tipo de Exame", df.tipo_exame.sort_values().unique())
    df = df[df.tipo_exame == selection]
    selection = alt.selection_single(fields=["plano"], bind="legend")
    line = (
        alt.Chart(df)
        .mark_line(point=True)
        .encode(
            x=alt.X(
                "yearmonth(expedido)",
                axis=alt.Axis(
                    tickCount="month",
                ),
            ),
            y="mean(pvp)",
            color=alt.Color(
                "plano",
                sort=alt.EncodingSortField("count", op="mean", order="descending"),
                legend=alt.Legend(title="Plano por ordem de frequência"),
            ),
            tooltip="mean(pvp)",
            opacity=alt.condition(selection, alt.value(1.0), alt.value(0.0)),
        )
        .add_selection(selection)
    )
    layer = (line).configure_view(strokeWidth=0).configure_axis(grid=False)
    st.altair_chart(layer, use_container_width=True)


def main_page():
    df, sispat = get_stored_data()
    options = ["Check Susana", "Honorários por Exame", "PVP por Entidade"]
    tab1, tab2, tab3 = st.tabs(options)

    with tab1:
        check_susana(df, sispat)
    with tab2:
        honorarios_por_exame(df)
    with tab3:
        pvp_por_entidade(df)


if "user" not in st.session_state:
    login()
    st.stop()

option = st.sidebar.radio("", ["Ver Dados", "Carregar Ficheiros"])

if option == "Ver Dados":
    main_page()
else:
    upload_files()
