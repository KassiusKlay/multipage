import streamlit as st
import pandas as pd
import altair as alt
import xlrd
import bcrypt
from db import engine
from datetime import datetime
from sqlalchemy import text


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


def diff_honorarios(uploaded_df, stored_df):
    pk = ["ano", "nr_exame", "tipo_exame"]
    compare_cols = ["pvp", "honorarios"]

    m = uploaded_df.merge(
        stored_df,
        on=pk,
        how="left",
        suffixes=("", "_stored"),
        indicator=True,
    )

    # 1. Inserts
    inserts = m[m["_merge"] == "left_only"][uploaded_df.columns].copy()

    # 2. Compare only rows present in both
    diffs = m[m["_merge"] == "both"].copy()

    # Updates: uploaded > stored
    need_update = (diffs["pvp"] > diffs["pvp_stored"]) | (
        diffs["honorarios"] > diffs["honorarios_stored"]
    )
    updates = diffs.loc[need_update, pk + compare_cols].copy()

    # Warnings: uploaded < stored
    need_warn = (diffs["pvp"] < diffs["pvp_stored"]) | (
        diffs["honorarios"] < diffs["honorarios_stored"]
    )
    warnings = diffs.loc[need_warn, pk + compare_cols].copy()

    return pk, inserts, updates, warnings


def apply_honorarios_changes(engine, pk, inserts, updates, warnings):
    if not warnings.empty:
        st.warning("Casos com pvp/honorarios menores que armazenados")
        st.write(warnings)
        st.stop()  # stop before doing anything else

    if not inserts.empty:
        inserts.to_sql("honorarios", engine, if_exists="append", index=False)
        st.success(f"{len(inserts)} novos casos inseridos")
    else:
        st.info("Sem novas entradas")

    if not updates.empty:
        update_cols = ["pvp", "honorarios"]
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS _honorarios_updates"))
            cols = ", ".join([f'"{c}"' for c in (pk + update_cols)])
            conn.execute(
                text(
                    f"""
                    CREATE TEMP TABLE _honorarios_updates AS
                    SELECT {cols} FROM honorarios LIMIT 0;
                    """
                )
            )
            updates.to_sql("_honorarios_updates", conn, if_exists="append", index=False)

            join_cond = " AND ".join([f'h."{k}" = u."{k}"' for k in pk])
            set_clause = ", ".join([f"{c} = u.{c}" for c in update_cols])

            res = conn.execute(
                text(
                    f"""
                    UPDATE honorarios h
                       SET {set_clause}
                      FROM _honorarios_updates u
                     WHERE {join_cond};
                    """
                )
            )
        st.success(f"Updated rows: {res.rowcount}")
    else:
        st.info("Sem actualizações")

    st.cache_data.clear()


def upload_files():
    # Retrieve stored data
    stored_df, sispat_df = get_stored_data()

    # Upload file
    uploaded_file = st.file_uploader(
        "Carregar Ficheiro", type="xlsb", accept_multiple_files=False
    )

    if uploaded_file:
        file_df = pd.read_excel(uploaded_file, None)
        uploaded_df = process_file_df(file_df)
        pk, inserts_df, updates_df, warnings_df = diff_honorarios(
            uploaded_df, stored_df
        )
        apply_honorarios_changes(engine, pk, inserts_df, updates_df, warnings_df)


def from_excel_datetime(x):
    return xlrd.xldate_as_datetime(x, 0)


@st.cache_data
def process_df(df):
    empty_rows = df.index[df.isna().all(axis=1)]

    if len(empty_rows) > 0:
        last_empty = empty_rows.max()
        df = df.loc[last_empty + 1 :]
        df = df.reset_index(drop=True)
    df.columns = df.iloc[0]
    if "QT" in df.columns:
        df = df.rename(columns={"QT": "qt imuno"})
    df = df[
        [
            "Ano",
            "Nº Exame",
            "Entrada",
            "Expedido",
            "Exame",
            "Entidade",
            "PVP",
            "% Hon.",
            "Honorários",
            "qt imuno",
            "Unidade",
        ]
    ]
    df.columns = [
        "ano",
        "nr_exame",
        "entrada",
        "expedido",
        "tipo_exame",
        "entidade",
        "pvp",
        "percentagem",
        "honorarios",
        "quantidade",
        "unidade",
    ]
    df = df[df["ano"].astype(str).str.startswith("20")]
    df[["entrada", "expedido"]] = df[["entrada", "expedido"]].map(from_excel_datetime)
    df["ano"] = df["ano"].astype("int64")
    df["nr_exame"] = df["nr_exame"].astype("int64")
    df["pvp"] = df["pvp"].astype("float").round(3)
    df["honorarios"] = df["honorarios"].astype("float").round(3)
    df["percentagem"] = df["percentagem"].astype("float").round(3)
    df["quantidade"] = df["quantidade"].astype("float")
    cols = [c for c in df.columns if c not in ["pvp", "honorarios"]]

    df = df.loc[df.groupby(cols, dropna=False)["pvp"].idxmax()].reset_index(drop=True)
    if "Estudo Imunocitoquímico (p/Anticorpo)" in df["tipo_exame"].unique():
        df["tipo_exame"] = "Aditamento Imunocitoquímica"
    else:
        df = df.drop(columns=["quantidade"])

    return df


@st.cache_data
def process_file_df(file_df):
    hluz = process_df(file_df["Actividade HLUZ"])
    torres = process_df(file_df["Actividade HLTL"])
    odivelas = process_df(file_df["Actividade HLOD"])
    cca = process_df(file_df["Actividade HLA"])
    cpp = process_df(file_df["Actividade HLO"])
    xira = process_df(file_df["Actividade HLVFX"])
    estudos = process_df(file_df["Estudos"])
    df = (
        pd.concat([hluz, torres, odivelas, cpp, cca, xira, estudos], ignore_index=True)
        .sort_values(by="entrada")
        .reset_index(drop=True)
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
    df = df.copy()
    aditamento_mask = df["tipo_exame"].str.contains("Aditamento", na=False)
    df.loc[aditamento_mask, "pvp"] = (
        df.loc[aditamento_mask, "pvp"] / df.loc[aditamento_mask, "quantidade"]
    )

    with st.form("cotovio"):
        cols = st.columns(2)
        max_date = df.expedido.max()
        default_month = max_date.month
        default_year = max_date.year
        months = df.expedido.dt.month.sort_values().unique()
        years = df.expedido.dt.year.sort_values().unique()
        month_index = list(months).index(default_month)
        year_index = list(years).index(default_year)
        mes = cols[0].selectbox("Mês", months, index=month_index)
        ano = cols[1].selectbox("Ano", years, index=year_index)
        ok = st.form_submit_button("Confirmar")
    if ok:
        df_filtered = df[(df.expedido.dt.year == ano) & (df.expedido.dt.month == mes)]
        if df_filtered.empty:
            st.warning("Escolha uma data válida")
            st.stop()
        sispat = sispat[
            (sispat.expedido.dt.year == ano)
            & (sispat.expedido.dt.month == mes)
            & ~(sispat.tipo_exame.str.contains("Aditamento"))
            & ~(sispat.tipo_exame.str.contains("Tipagem"))
            & (sispat.patologista == "Dr. João Cassis")
        ]

        imuno_sispat = sispat.imuno.sum()
        imuno_susana = (
            df_filtered[df_filtered.tipo_exame.str.contains("Aditamento")]
            .quantidade.sum()
            .astype(int)
        )
        st.write("Imuno sispat:", imuno_sispat, "Imuno Honorarios:", imuno_susana)

        casos_sispat = sispat[~sispat.tipo_exame.str.contains("Aditamento")].shape[0]
        casos_susana = df_filtered[
            ~df_filtered.tipo_exame.str.contains("Aditamento")
        ].shape[0]
        st.write("Casos sispat:", casos_sispat, "Casos Honorarios:", casos_susana)
        if casos_sispat != casos_susana:
            # Sispat not in Susana
            diff_sispat = list(
                set(sispat.nr_exame.tolist()) - set(df_filtered.nr_exame.tolist())
            )
            diff_sispat = sispat[sispat.nr_exame.isin(diff_sispat)]
            if not diff_sispat.empty:
                st.warning("Exames em Sispat mas não em Honorarios")
                st.write(diff_sispat)

            # Susana not in Sispat
            diff_susana = list(
                set(df_filtered.nr_exame.tolist()) - set(sispat.nr_exame.tolist())
            )
            diff_susana = df_filtered[df_filtered.nr_exame.isin(diff_susana)]
            if not diff_susana.empty:
                st.warning("Exames em Honorarios mas não em Sispat")
                st.write(diff_susana)
            dupes = df_filtered[
                df_filtered.duplicated(
                    subset=["ano", "nr_exame", "tipo_exame"], keep=False
                )
            ]
            st.write("Duplicados em Honorarios:", dupes)

        selected_grouped = (
            df_filtered.groupby(["tipo_exame", "entidade"])["pvp"].mean().reset_index()
        )
        comparisons = []
        for _, row in selected_grouped.iterrows():
            tipo_exame = row["tipo_exame"]
            entidade = row["entidade"]
            pvp_selected = row["pvp"]

            df_prior = df[
                (df.expedido < datetime(ano, mes, 1))
                & (df.tipo_exame == tipo_exame)
                & (df.entidade == entidade)
            ]

            if not df_prior.empty:
                max_prior_date = df_prior.expedido.max()
                df_most_recent = df_prior[
                    df_prior.expedido.dt.year == max_prior_date.year
                ]
                df_most_recent = df_most_recent[
                    df_most_recent.expedido.dt.month == max_prior_date.month
                ]

                prior_grouped = (
                    df_most_recent.groupby(["tipo_exame", "entidade"])["pvp"]
                    .mean()
                    .reset_index()
                )
                pvp_previous = prior_grouped[
                    (prior_grouped.tipo_exame == tipo_exame)
                    & (prior_grouped.entidade == entidade)
                ]["pvp"]

                if not pvp_previous.empty:
                    pvp_previous = pvp_previous.iloc[0]
                    pvp_difference = pvp_selected - pvp_previous
                    if pvp_difference <= -0.50:
                        comparisons.append(
                            {
                                "tipo_exame": tipo_exame,
                                "entidade": entidade,
                                "pvp_previous": pvp_previous,
                                "pvp_selected": pvp_selected,
                                "pvp_difference": pvp_difference,
                                "prev_month": max_prior_date.month,
                                "prev_year": max_prior_date.year,
                            }
                        )

        changes = pd.DataFrame(comparisons)

        if changes.empty:
            st.success(
                "Nenhuma redução de PVP de 0,50 ou mais encontrada em relação aos meses anteriores."
            )
        else:
            st.warning(
                "Reduções de PVP de 0,50 ou mais detectadas em relação aos meses anteriores:"
            )
            changes_display = changes[
                [
                    "tipo_exame",
                    "entidade",
                    "pvp_previous",
                    "pvp_selected",
                    "pvp_difference",
                    "prev_month",
                    "prev_year",
                ]
            ]
            changes_display.columns = [
                "Tipo de Exame",
                "Entidade",
                "PVP Mês Anterior",
                f"PVP {mes}/{ano}",
                "Diferença",
                "Mês Anterior",
                "Ano Anterior",
            ]
            st.dataframe(changes_display)

        random_top5_rows = []
        # Group by tipo_exame to iterate over each tipo_exame
        grouped_by_exame = df_filtered.groupby("tipo_exame")
        for tipo_exame, exame_group in grouped_by_exame:
            # Count rows per entidade within this tipo_exame
            entidade_counts = (
                exame_group.groupby("entidade").size().reset_index(name="row_count")
            )
            # Get top 5 entidade by row count
            top5_entidade = entidade_counts.nlargest(5, "row_count")[
                "entidade"
            ].tolist()
            # For each top entidade, select a random row from df_filtered
            for entidade in top5_entidade:
                entity_rows = exame_group[exame_group["entidade"] == entidade]
                if not entity_rows.empty:
                    random_row = entity_rows.sample(n=1, random_state=None)
                    random_top5_rows.append(random_row)

        # Combine the randomly selected rows into a DataFrame
        random_top5_df = (
            pd.concat(random_top5_rows, ignore_index=True)
            if random_top5_rows
            else pd.DataFrame()
        )

        # Display the new DataFrame
        if random_top5_df.empty:
            st.warning(
                "Nenhuma linha encontrada para os grupos de tipo_exame no mês selecionado."
            )
        else:
            st.subheader(
                "Amostra Aleatória de Linhas das Top 5 Entidades por Contagem de Linhas por Tipo de Exame"
            )
            st.dataframe(
                random_top5_df.drop(columns=["percentagem", "honorarios", "quantidade"])
            )


def honorarios_por_exame(df):
    # Add year selection
    years = df.expedido.dt.year.sort_values().unique().tolist()[::-1]
    years.insert(0, "All Data")  # Add "All Data" option at the start
    selected_year = st.selectbox("Ano", years, index=0)  # Default to "All Data"

    # Filter by selected year, unless "All Data" is chosen
    if selected_year != "All Data":
        df = df[df.expedido.dt.year == int(selected_year)]

    # Original calculations
    df["quantidade"] = df["quantidade"].fillna(1)
    df["pvp"] = df["pvp"] / df["quantidade"]
    df["honorarios"] = df["pvp"] * df["percentagem"]
    luz = df[~df.tipo_exame.str.contains("hba", case=False)]
    hba = df[df.tipo_exame.str.contains("hba", case=False)]

    # Display tables
    cols = st.columns(2)
    cols[0].table(
        luz.groupby("tipo_exame")
        .honorarios.agg(["count", "min", "mean", "max"])
        .sort_values(by="count", ascending=False)
    )
    if not hba.empty:
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
