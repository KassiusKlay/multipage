import streamlit as st
import pandas as pd
import altair as alt
from db import engine


@st.cache_data
def get_stored_data():
    return pd.read_sql("SELECT * FROM r4c", engine, parse_dates=["entrada"])


def plot_monthly_cases(df):
    monthly = (
        df.groupby(pd.Grouper(key="entrada", freq="ME"))
        .agg(casos=("nr_exame", "count"))
        .reset_index()
    )
    chart = (
        alt.Chart(monthly)
        .mark_line(point=True, interpolate="step")
        .encode(
            x=alt.X(
                "yearmonth(entrada):T",
                axis=alt.Axis(tickCount={"interval": "month", "step": 1}),
                scale=alt.Scale(padding=20),
                title="",
            ),
            y=alt.Y("casos:Q", title=""),
            tooltip=[
                alt.Text("yearmonth(entrada):T", format="%b-%Y"),
                alt.Text("casos:Q", format=".0f"),
            ],
        )
        .configure_axis(grid=False)
        .configure_view(strokeWidth=0)
        .properties(width=700, title="Casos por mês")
    )
    st.altair_chart(chart)


def plot_monthly_imuno(df):
    monthly = (
        df.groupby(pd.Grouper(key="entrada", freq="ME"))
        .agg(imuno=("imuno", "sum"))
        .reset_index()
    )
    chart = (
        alt.Chart(monthly)
        .mark_line(point=True, interpolate="step")
        .encode(
            x=alt.X(
                "yearmonth(entrada):T",
                axis=alt.Axis(tickCount={"interval": "month", "step": 1}),
                scale=alt.Scale(padding=20),
                title="",
            ),
            y=alt.Y("imuno:Q", title=""),
            tooltip=[
                alt.Text("yearmonth(entrada):T", format="%b-%Y"),
                alt.Text("imuno:Q", format=".0f"),
            ],
        )
        .configure_axis(grid=False)
        .configure_view(strokeWidth=0)
        .properties(width=700, title="Imuno por mês")
    )
    st.altair_chart(chart)


def plot_tipo_exame(df):
    counts = (
        df.groupby("tipo_exame", as_index=False)
        .agg(casos=("nr_exame", "count"))
        .sort_values("casos", ascending=False)
    )
    chart = (
        alt.Chart(counts)
        .mark_bar()
        .encode(
            x=alt.X("casos:Q", axis=None),
            y=alt.Y("tipo_exame:N", sort="-x", title=""),
            tooltip=["tipo_exame", alt.Text("casos:Q", format=".0f")],
        )
    )
    text = (
        alt.Chart(counts)
        .mark_text(align="left", dx=2)
        .encode(
            x="casos:Q",
            y=alt.Y("tipo_exame:N", sort="-x"),
            text=alt.Text("casos:Q", format=".0f"),
        )
    )
    layered = (
        alt.layer(chart, text)
        .configure_axis(grid=False, title="")
        .configure_view(strokeWidth=0)
        .properties(width=700, title="Casos por tipo de exame")
    )
    st.altair_chart(layered)


def main_page():
    df = get_stored_data()
    if df.empty:
        st.info("Sem dados. Carrega ficheiros Imunos + Serviços.")
        return

    st.subheader(f"{len(df)} casos")
    plot_monthly_cases(df)
    plot_monthly_imuno(df)
    plot_tipo_exame(df)
    with st.expander("Tabela"):
        st.dataframe(df.sort_values("entrada", ascending=False), use_container_width=True)


def _classify_upload(file_df):
    cols = set(file_df.columns)
    is_imunos = {"Número do caso", "Data de receção"} <= cols
    is_servicos = {
        "Número do caso",
        "Códigos de faturação",
        "Quantidade",
    } <= cols
    if is_imunos and not is_servicos:
        return "imunos"
    if is_servicos and not is_imunos:
        return "servicos"
    if is_imunos and is_servicos:
        # Prefer servicos when all three activity cols are present
        return "servicos"
    return None


def _build_cases(imunos, servicos):
    imunos = imunos.copy()
    servicos = servicos.copy()

    imunos["nr_exame"] = imunos["Número do caso"].astype(str).str.strip()
    servicos["nr_exame"] = servicos["Número do caso"].astype(str).str.strip()

    cases_imunos = set(imunos["nr_exame"])
    cases_servicos = set(servicos["nr_exame"])
    only_imunos = sorted(cases_imunos - cases_servicos)
    only_servicos = sorted(cases_servicos - cases_imunos)
    if only_imunos or only_servicos:
        if only_imunos:
            st.error(f"Só em Imunos ({len(only_imunos)}): {only_imunos}")
        if only_servicos:
            st.error(f"Só em Serviços ({len(only_servicos)}): {only_servicos}")
        st.stop()

    imunos["entrada"] = pd.to_datetime(
        imunos["Data de receção"], dayfirst=True, errors="coerce"
    )
    if imunos["entrada"].isna().any():
        bad = imunos.loc[imunos["entrada"].isna(), "nr_exame"].unique().tolist()
        st.error(f"Data de receção inválida: {bad}")
        st.stop()

    entrada_por_caso = imunos.groupby("nr_exame")["entrada"].min()

    is_ihc = servicos["Códigos de faturação"].astype(str).str.contains(
        "imunocitoquímico", case=False, na=False
    )
    rows = []
    for nr_exame, group in servicos.groupby("nr_exame"):
        non_ihc = group.loc[~is_ihc.loc[group.index]]
        ihc = group.loc[is_ihc.loc[group.index]]
        if len(non_ihc) != 1:
            st.error(
                f"{nr_exame}: esperado exactamente 1 linha não-IHC, "
                f"encontrei {len(non_ihc)}"
            )
            st.write(group[["Códigos de faturação", "Quantidade"]])
            st.stop()
        tipo_exame = non_ihc.iloc[0]["Códigos de faturação"]
        imuno = (
            pd.to_numeric(ihc["Quantidade"], errors="coerce").fillna(0).sum()
            if len(ihc)
            else 0
        )
        rows.append(
            {
                "nr_exame": nr_exame,
                "entrada": entrada_por_caso[nr_exame],
                "tipo_exame": tipo_exame,
                "imuno": int(imuno),
            }
        )
    return pd.DataFrame(rows)


def upload_files():
    stored_df = get_stored_data()
    uploaded_files = st.file_uploader(
        "Select files to upload",
        type="xlsx",
        accept_multiple_files=True,
    )

    if not uploaded_files:
        return

    if len(uploaded_files) != 2:
        st.error("Carrega exactamente 2 ficheiros: Imunos e Serviços (.xlsx).")
        st.stop()

    classified = {}
    for file in uploaded_files:
        file_df = pd.read_excel(file)
        kind = _classify_upload(file_df)
        if kind is None:
            st.error(f"Ficheiro não reconhecido: {file.name}")
            st.write(list(file_df.columns))
            st.stop()
        if kind in classified:
            st.error(f"Dois ficheiros do tipo {kind}.")
            st.stop()
        classified[kind] = file_df

    if set(classified) != {"imunos", "servicos"}:
        st.error("Preciso de exactamente um ficheiro Imunos e um Serviços.")
        st.stop()

    new_df = _build_cases(classified["imunos"], classified["servicos"])

    if not stored_df.empty:
        existing = set(stored_df["nr_exame"].astype(str))
        new_df = new_df[~new_df["nr_exame"].isin(existing)]

    if new_df.empty:
        st.info("Sem dados novos")
        st.stop()

    st.write(new_df)
    new_df.to_sql("r4c", engine, if_exists="append", index=False)
    get_stored_data.clear()
    st.success("Ficheiros Carregados")


def main():
    if st.sidebar.button("Clear Cache"):
        get_stored_data.clear()

    option = st.sidebar.radio(
        "options", ["Ver Dados", "Carregar Ficheiros"], label_visibility="collapsed"
    )

    if option == "Ver Dados":
        main_page()
    else:
        upload_files()


if __name__ == "__main__":
    main()
