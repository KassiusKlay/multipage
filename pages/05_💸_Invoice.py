import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import altair as alt
import xlrd
import bcrypt

st.set_page_config(layout="wide")


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
        or st.session_state.username != st.secrets["app"]["user"]
        or not bcrypt.checkpw(
            st.session_state.password.encode(), st.secrets["app"]["password"].encode()
        )
    ):
        st.warning("Tente novamente")
    else:
        st.session_state.logged_in = True


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
            st.cache_data.clear()
        else:
            st.info("Sem entradas novas")


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
    df.pvp = df.pvp.abs()
    df.honorarios = df.honorarios.abs()
    df = df.drop_duplicates(keep=False)
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
        "SELECT * FROM sispat",
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
            & (sispat.patologista == "Dr. João Cassis")
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


def timeline_pvp(df):
    df = df[
        (~df.tipo_exame.str.contains("hba", case=False))
        & ~(df.tipo_exame.str.contains("citologia", case=False))
    ]
    tipo_exame = st.selectbox("Tipo de Exame", df.tipo_exame.sort_values().unique())
    exam_df = df[df.tipo_exame == tipo_exame]
    exam_df = exam_df.copy()
    exam_df["quantidade"] = exam_df["quantidade"].fillna(1)
    selection = alt.selection_point(fields=["entidade"], bind="legend")
    line = (
        alt.Chart(exam_df)
        .transform_calculate(pvp_per_quantidade="datum.pvp / datum.quantidade")
        .mark_line(point=True)
        .encode(
            x=alt.X(
                "yearmonth(expedido)",
                axis=alt.Axis(tickCount="month"),
            ),
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
    layer = (line).configure_view(strokeWidth=0).configure_axis(grid=False)
    st.altair_chart(layer, use_container_width=True)


def mean_pvp_biopsia(df):
    last_date = df["expedido"].max()
    tipo_exame_order = [
        "Histológico - biópsia (1 frasco)",
        "Histológico - biópsia (2 frascos)",
        "Histológico - biópsia (+ de 2 frascos)",
    ]
    colors = {
        "Histológico - biópsia (1 frasco)": "#aee2ff",
        "Histológico - biópsia (2 frascos)": "#6ca2de",
        "Histológico - biópsia (+ de 2 frascos)": "#23679e",
    }

    last_month_data = df[
        (df["expedido"] > (last_date - pd.DateOffset(months=1)))
        & (df.tipo_exame.isin(tipo_exame_order))
    ]
    mean_pvp = (
        last_month_data.groupby(["entidade", "tipo_exame"])["pvp"].mean().reset_index()
    )

    pivot_mean_pvp = mean_pvp.pivot(
        index="entidade", columns="tipo_exame", values="pvp"
    )

    condition_met = pivot_mean_pvp.apply(
        lambda x: x["Histológico - biópsia (1 frasco)"]
        < x["Histológico - biópsia (2 frascos)"]
        and x["Histológico - biópsia (2 frascos)"]
        < x["Histológico - biópsia (+ de 2 frascos)"],
        axis=1,
    )

    entidade_to_plot = pivot_mean_pvp[~condition_met].index.tolist()
    data_to_plot = mean_pvp[mean_pvp["entidade"].isin(entidade_to_plot)]

    for entidade in entidade_to_plot:
        data_to_plot = mean_pvp[mean_pvp["entidade"] == entidade]

        if data_to_plot["tipo_exame"].nunique() == len(tipo_exame_order):
            bar = (
                alt.Chart(data_to_plot)
                .mark_bar()
                .encode(
                    x=alt.X(
                        "tipo_exame:N",
                        sort=tipo_exame_order,
                        title="Tipo de Exame",
                        axis=alt.Axis(labelAngle=0),
                    ),
                    y=alt.Y("mean(pvp):Q", title="PVP"),
                    color=alt.Color(
                        "tipo_exame:N",
                        scale=alt.Scale(
                            domain=list(colors.keys()), range=list(colors.values())
                        ),
                        legend=None,
                    ),
                    tooltip=["tipo_exame", "mean(pvp)"],
                )
                .properties(width=1000, height=500)
            )
            text = (
                alt.Chart(data_to_plot)
                .mark_text(
                    align="center",
                    baseline="bottom",
                    dy=-5,
                    color="black",
                )
                .encode(
                    x=alt.X("tipo_exame:N", sort=tipo_exame_order),
                    y=alt.Y("mean(pvp):Q", aggregate="mean"),
                    text=alt.Text("mean(pvp):Q", format=".2f"),
                )
            )
            st.write(f"#### {entidade}")
            st.altair_chart(
                (bar + text).configure_axis(labelLimit=0), use_container_width=False
            )


def faturacao(df, sispat):
    sispat = sispat[
        (sispat.expedido >= "2022-01") & ~(sispat.tipo_exame.str.contains("Aditamento"))
    ]
    grouped_df = df.groupby(["tipo_exame"])["honorarios"].mean().reset_index()
    merged_df = sispat.merge(grouped_df, on=["tipo_exame"], how="left")
    merged_df["total_honorarios"] = merged_df.honorarios + merged_df.imuno * 12.72
    df = merged_df[merged_df.ano >= 2022]

    sum_honorarios = df.groupby("patologista")["total_honorarios"].sum().reset_index()
    sum_honorarios["total_honorarios"] = (
        sum_honorarios["total_honorarios"].round().astype(int)
    )

    chart = (
        alt.Chart(sum_honorarios)
        .mark_bar()
        .encode(
            x=alt.X("patologista:N", sort="-y"),
            y="total_honorarios:Q",
            tooltip=["patologista", "total_honorarios"],
        )
        .properties(width=600, height=400)
    )
    st.altair_chart(chart, use_container_width=True)

    years = df["ano"].sort_values().unique()
    cols = st.columns(len(years))
    for i, year in enumerate(years):
        df_year = df[df["ano"] == year]
        sum_honorarios_year = (
            df_year.groupby("patologista")["total_honorarios"].sum().reset_index()
        )
        chart_year = (
            alt.Chart(sum_honorarios_year)
            .mark_bar()
            .encode(
                x=alt.X("patologista:N", sort="-y"),
                y="total_honorarios:Q",
                tooltip=["patologista", "total_honorarios"],
            )
            .properties(
                title=f"Year: {year}",
            )
        )
        cols[i].altair_chart(chart_year, use_container_width=True)


def percentage_entidades(df):
    filtered_df = df[(~df.tipo_exame.str.contains("HBA"))]
    percentages = (filtered_df["entidade"].value_counts(normalize=True) * 100).round(2)
    st.write(pd.DataFrame(percentages).head(10))


def main_page():
    df, sispat = get_stored_data()
    options = [
        "Check Susana",
        "Honorários por Exame",
        "Peso das entidades",
        "Timeline PVP por Entidade",
        "PVP por Biópsia",
        "Faturação",
    ]
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(options)

    with tab1:
        check_susana(df.copy(), sispat.copy())
    with tab2:
        honorarios_por_exame(df.copy())
    with tab3:
        percentage_entidades(df.copy())
    with tab4:
        timeline_pvp(df.copy())
    with tab5:
        mean_pvp_biopsia(df.copy())
    with tab6:
        faturacao(df.copy(), sispat.copy())


if "logged_in" not in st.session_state:
    login()
    st.stop()

option = st.sidebar.radio(
    "options", ["Ver Dados", "Carregar Ficheiros"], label_visibility="collapsed"
)

if option == "Ver Dados":
    main_page()
else:
    upload_files()
