import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import altair as alt
import xlrd
import hashlib

st.set_page_config(layout="wide")
user_hex = (
    "033758f933cd377cf41ff7c43997bd00e9a8284694935be5435ace73ff277c3457a8ed7f18"
    "b81822eca326b1324d20496681ec0d5e514e90816fdc036fbcc0a1"
)


@st.cache_resource
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
        or hashlib.sha512(st.session_state.username.encode()).hexdigest() != user_hex
        or st.secrets[st.session_state.username] != st.session_state.password
    ):
        st.warning("Tente novamente")
    else:
        st.session_state.invoice = True


def login():
    with st.form("login"):
        st.text_input("Username", key="username")
        st.text_input("Password", key="password", type="password")
        st.form_submit_button("Login", on_click=check_credentials)


def upload_files():
    stored_df, _ = get_stored_data()

    uploaded_file = st.file_uploader(
        "Carregar Ficheiro",
        type="xlsb",
        accept_multiple_files=False,
    )

    if uploaded_file:
        file_df = pd.read_excel(uploaded_file, None)
        uploaded_df = process_file_df(file_df)
        merged_df = pd.merge(stored_df, uploaded_df, how="outer", indicator=True)
        final_df = merged_df[merged_df["_merge"] == "right_only"]
        final_df = final_df.drop("_merge", axis=1)
        if not final_df.empty:
            st.write(final_df)
            final_df.to_sql("honorarios", engine, if_exists="append", index=False)
            st.success("Ficheiro actualizado")
        else:
            st.info("Sem entradas novas")
        st.cache_data.clear()


def from_excel_datetime(x):
    return xlrd.xldate_as_datetime(x, 0)


def process_df(df):
    df = df.dropna(axis=0, thresh=6)
    df = df.dropna(axis=1, how="all").reset_index(drop=True)
    if not df.columns[df.apply(lambda col: col.count() == 1)].empty:
        df = df.loc[1:, df.apply(lambda col: col.count() != 1)]
        if df.empty:
            return
    df.columns = df.iloc[0]
    df.rename(columns={"QT": "qt imuno"}, inplace=True)
    df = df[df["Ano"].astype(str).str.startswith("20")]
    if (
        "Estudo Imunocitoquímico (p/Anticorpo)" in df["Exame"].unique()
        or "Estudo Imunocitoquímico (p/Anticorpo)" in df["Cód. Facturação"].unique()
    ):
        df["Exame"] = "Aditamento Imunocitoquímica"
    else:
        df["qt imuno"] = None
    if "Plano SS" not in df.columns:
        df["Plano SS"] = "Desconhecido"
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
            "qt imuno",
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
        "quantidade",
    ]
    df[["entrada", "expedido"]] = df[["entrada", "expedido"]].applymap(
        from_excel_datetime
    )
    df["ano"] = df["ano"].astype("int64")
    df["nr_exame"] = df["nr_exame"].astype("int64")
    df["pvp"] = df["pvp"].astype("float").round(3)
    df["honorarios"] = df["honorarios"].astype("float").round(3)
    df["percentagem"] = df["percentagem"].astype("float").round(3)
    return df


def process_file_df(file_df):
    hluz = process_df(file_df["Actividade HLUZ"])
    torres = process_df(file_df["Actividade HLTL"])
    odivelas = process_df(file_df["Actividade HLOD"])
    cca = process_df(file_df["Actividade CCA"])
    cpp = process_df(file_df["Actividade CPP"])
    estudos = process_df(file_df["Estudos"])
    df = (
        pd.concat([hluz, torres, odivelas, cpp, cca, estudos], ignore_index=True)
        .sort_values(by="entrada")
        .reset_index(drop=True)
        .dropna(subset="ano")
    )
    return df


@st.cache_data
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
            st.warning("Exames não contemplados")
            st.write(diff)
        imuno_sispat = sispat.imuno.sum()
        imuno_susana = df[df.tipo_exame.str.contains("Aditamento")].quantidade.sum()
        st.write("Imuno real:", imuno_sispat, "Imuno Honorarios:", imuno_susana)


def honorarios_por_exame(df):
    df["quantidade"] = df["quantidade"].fillna(1)
    df["pvp"] = df["pvp"] / df["quantidade"]
    df["honorarios"] = df["pvp"] * df["percentagem"]
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
    tipo_exame = st.selectbox("Tipo de Exame", df.tipo_exame.sort_values().unique())
    df = df[df.tipo_exame == tipo_exame]
    df["quantidade"] = df["quantidade"].fillna(1)
    selection = alt.selection_point(fields=["entidade"], bind="legend")

    line = (
        alt.Chart(df)
        .transform_calculate(pvp_per_quantidade="datum.pvp / datum.quantidade")
        .mark_line(point=True)
        .encode(
            x=alt.X(
                "yearmonth(expedido)",
                axis=alt.Axis(tickCount="month"),
            ),
            # Calculate the mean of the new field
            y=alt.Y("mean(pvp_per_quantidade):Q", title="PVP"),
            color=alt.Color(
                "entidade",
                sort=alt.EncodingSortField("count", op="count", order="descending"),
                legend=alt.Legend(title="Plano por ordem de frequência"),
            ),
            tooltip="mean(pvp_per_quantidade):Q",
            opacity=alt.condition(selection, alt.value(1.0), alt.value(0.0)),
        )
        .add_params(selection)
    )

    # line = (
    # alt.Chart(df)
    # .mark_line(point=True)
    # .encode(
    # x=alt.X(
    # "yearmonth(expedido)",
    # axis=alt.Axis(
    # tickCount="month",
    # ),
    # ),
    # y="mean(pvp)",
    # color=alt.Color(
    # "entidade",
    # sort=alt.EncodingSortField("count", op="count", order="descending"),
    # legend=alt.Legend(title="Plano por ordem de frequência"),
    # ),
    # tooltip="mean(pvp)",
    # opacity=alt.condition(selection, alt.value(1.0), alt.value(0.0)),
    # )
    # .add_params(selection)
    # )
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


if "invoice" not in st.session_state:
    login()
    st.stop()

option = st.sidebar.radio(
    "options", ["Ver Dados", "Carregar Ficheiros"], label_visibility="collapsed"
)

if option == "Ver Dados":
    main_page()
else:
    upload_files()
