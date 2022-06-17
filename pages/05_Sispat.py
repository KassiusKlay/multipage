import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import altair as alt

st.set_page_config(layout="centered")


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
interpolate = "step"


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


@st.experimental_memo
def get_stored_data():
    return pd.read_sql(
        "SELECT * FROM sispat", engine, parse_dates=["entrada", "expedido"]
    )


def show_geral_casos(df):
    df = df.loc[
        ~df.tipo_exame.str.contains("Aditamento")
        & ~df.tipo_exame.str.contains("Tipagem")
    ]
    st.subheader("Total de Exames")
    anual = st.checkbox("Anual", key="exame_anual")
    if anual:
        freq = "Y"
        x_axis = "year(expedido):T"
        tick_count = "year"
        first_domain = df.expedido.min() - pd.DateOffset(years=1)
        last_domain = df.expedido.max() + pd.DateOffset(months=1)
    else:
        freq = "M"
        x_axis = "yearmonth(expedido):T"
        tick_count = {"interval": "month", "step": 6}
        first_domain = df.expedido.min() - pd.DateOffset(months=1)
        last_domain = df.expedido.max() + pd.DateOffset(months=1)

    df = df.groupby([pd.Grouper(key="expedido", freq=freq), "exame"]).agg(
        {"nr_exame": "count", "imuno": "sum"}
    )

    imuno = df.groupby("expedido").agg({"imuno": "sum"})
    imuno["exame"] = "Imuno"
    imuno.columns = ["nr_exame", "exame"]

    df = pd.concat([df.reset_index(), imuno.reset_index()]).drop(columns="imuno")

    selection = alt.selection_multi(empty="all", fields=["exame"])
    color = alt.condition(
        selection, alt.Color("exame:N", legend=None), alt.value("lightgray")
    )
    opacity = alt.condition(selection, alt.value(1), alt.value(0.1))

    line = (
        alt.Chart(df)
        .mark_line(point=True, interpolate=interpolate)
        .encode(
            x=alt.X(
                x_axis,
                axis=alt.Axis(tickCount=tick_count),
                scale=alt.Scale(domain=(first_domain, last_domain)),
            ),
            y="nr_exame",
            color=color,
            tooltip="nr_exame",
            opacity=opacity,
        )
    )

    rule = (
        alt.Chart(df)
        .mark_rule(strokeDash=[12, 6], size=2)
        .encode(
            y=alt.Y(
                "mean(nr_exame)",
            ),
            color=color,
            size=alt.value(2),
            opacity=opacity,
        )
    )

    text_rule = (
        alt.Chart(df)
        .mark_text(
            align="left",
            baseline="bottom",
            fontSize=14,
            fontWeight=600,
        )
        .encode(
            x=alt.value(1),
            y="mean(nr_exame)",
            color=color,
            text=alt.Text("mean(nr_exame)", format=".0f"),
            opacity=opacity,
        )
    )
    right = (
        alt.Chart(df)
        .mark_point()
        .encode(y=alt.Y("exame:N", axis=alt.Axis(orient="right")), color=color)
        .add_selection(selection)
    )

    left = alt.layer(line + rule + text_rule)

    chart = (
        alt.hconcat(left, right)
        .configure_axis(grid=False, title="")
        .configure_view(strokeWidth=0)
    )

    st.altair_chart(chart, use_container_width=True)


def show_geral_tipos_de_exame(df):
    st.subheader("Tipo de Exame")
    tipo_exame = st.selectbox("", df.tipo_exame.sort_values().unique().tolist())
    df = df[df.tipo_exame == tipo_exame]
    anual = st.checkbox("Anual", key="tipo_exame_anual")
    if anual:
        freq = "Y"
        x_axis = "year(expedido):T"
        tick_count = "year"
        first_domain = df.expedido.min() - pd.DateOffset(years=1)
        last_domain = df.expedido.max() + pd.DateOffset(months=1)
    else:
        freq = "M"
        x_axis = "yearmonth(expedido):T"
        tick_count = {"interval": "month", "step": 6}
        first_domain = df.expedido.min() - pd.DateOffset(months=1)
        last_domain = df.expedido.max() + pd.DateOffset(months=1)

    df = (
        df.groupby([pd.Grouper(key="expedido", freq=freq), "tipo_exame"])
        .agg({"nr_exame": "count"})
        .reset_index()
    )

    line = (
        alt.Chart(df)
        .mark_line(point=True, interpolate=interpolate)
        .encode(
            x=alt.X(
                x_axis,
                axis=alt.Axis(tickCount=tick_count),
                scale=alt.Scale(domain=(first_domain, last_domain)),
            ),
            y="mean(nr_exame)",
            tooltip="mean(nr_exame)",
        )
    )

    rule = (
        alt.Chart(df)
        .mark_rule(strokeDash=[12, 6], size=2)
        .encode(
            y=alt.Y(
                "mean(nr_exame)",
            ),
            color=alt.value("lightgrey"),
            size=alt.value(2),
        )
    )

    text_rule = (
        alt.Chart(df)
        .mark_text(
            align="left",
            baseline="bottom",
            fontSize=14,
            fontWeight=600,
            color="lightgrey",
        )
        .encode(
            x=alt.value(1),
            y="mean(nr_exame)",
            text=alt.Text("mean(nr_exame)", format=".0f"),
        )
    )

    chart = (
        alt.layer(line + rule + text_rule)
        .configure_axis(grid=False, title="")
        .configure_view(strokeWidth=0)
    )

    st.altair_chart(chart, use_container_width=True)


def select_gerais(df):
    option = st.radio("", ["Geral", "Por Patologista"], horizontal=True)
    if option == "Por Patologista":
        patologista = st.selectbox(
            "Seleccione um patologista",
            df.patologista.sort_values().unique(),
            key="patologista",
        )
        df = df[df.patologista == patologista]
    else:
        excluir_hba = st.checkbox("Excluir HBA", key="imuno_hba")
        if excluir_hba:
            df = df[~df.tipo_exame.str.contains("hba", case=False)]
    show_geral_casos(df)
    show_geral_tipos_de_exame(df)


def show_media_tempo_de_resposta(df):
    df = df.loc[
        ~df.tipo_exame.str.contains("Aditamento")
        & ~df.tipo_exame.str.contains("Tipagem")
        & ~df.tipo_exame.str.contains("Aut")
        & ~(
            df.patologista.isin(
                [
                    "Dra. Helena Oliveira",
                    "Dra. Rosa Madureira",
                    "Dr. Paulo Bernardo",
                    "Prof. António Medina de Almeida",
                    "Dra. Maria Delfina Brito",
                ]
            )
        )
        & ~(
            (df.patologista == "Dra. Ana Catarino")
            & (df.expedido.dt.to_period("M") == "2022-05")
        )
    ]

    df = df.groupby([pd.Grouper(key="expedido", freq="M"), "patologista", "exame"]).agg(
        {"tempo_de_resposta": "mean"}
    )

    total = df.groupby(["expedido", "exame"]).agg({"tempo_de_resposta": "mean"})
    total["patologista"] = "Total"
    df = pd.concat([df.reset_index(), total.reset_index()])
    plot_media(
        df,
        ("Histologia", "Citologia"),
        "mean(tempo_de_resposta)",
        "patologista",
        "x",
        ".1f",
    )


def plot_media(df, exame_tuple, x, y, x_sort, text_format):
    for i in exame_tuple:
        first_domain = df.expedido.min() - pd.DateOffset(years=1)
        last_domain = df.expedido.max() + pd.DateOffset(years=1)

        selector = alt.selection_single(empty="none", fields=[y])

        bar = (
            alt.Chart(df, title=f"{i}")
            .mark_bar()
            .encode(
                x=alt.X(x, axis=None),
                y=alt.Y(y, sort=x_sort, title=""),
                color=alt.condition(
                    selector, alt.value("steelblue"), alt.value("lightgrey")
                ),
            )
        )

        text = (
            alt.Chart(df)
            .mark_text(align="left", color="black", dx=3)
            .encode(
                x=x,
                y=alt.Y(y, sort=x_sort),
                text=alt.Text(x, format=text_format),
            )
        )

        left = (
            alt.layer(bar + text)
            .add_selection(selector)
            .transform_filter(alt.datum.exame == i)
        )

        rule = (
            alt.Chart(df)
            .mark_rule(strokeDash=[12, 6], size=2)
            .encode(
                y=alt.Y(
                    x,
                ),
                color=alt.value("lightgrey"),
                size=alt.value(2),
            )
        )

        text_rule = (
            alt.Chart(df)
            .mark_text(
                align="left",
                baseline="bottom",
                fontSize=14,
                fontWeight=600,
                color="lightgrey",
            )
            .encode(
                x=alt.value(1),
                y=x,
                text=alt.value(["Média"]),
            )
        )

        line = (
            alt.Chart(df)
            .mark_line(point=True)
            .encode(
                x=alt.X(
                    "year(expedido):T",
                    title="",
                    scale=alt.Scale(domain=(first_domain, last_domain)),
                    axis=alt.Axis(tickCount="year"),
                ),
                y=alt.Y(
                    x,
                    title="",
                ),
            )
        )

        text_line = line.mark_text(color="steelblue", dy=-10, size=15).encode(
            text=alt.Text(x, format=text_format)
        )

        right = (
            alt.layer(rule + text_rule + line + text_line)
            .transform_filter(selector)
            .transform_filter(alt.datum.exame == i)
        )

        chart = (
            alt.hconcat(left, right)
            .configure_axis(grid=False)
            .configure_view(strokeWidth=0)
            .configure_title(anchor="start")
        ).configure_title(fontSize=20, anchor="start")

        st.altair_chart(chart, use_container_width=True)


def show_media_casos(df):
    df = df.loc[
        ~df.tipo_exame.str.contains("Aditamento")
        & ~df.tipo_exame.str.contains("Tipagem")
    ]
    excluir_hba = st.checkbox("Excluir HBA", key="imuno_hba")
    if excluir_hba:
        df = df[~df.tipo_exame.str.contains("hba", case=False)]
    df = df.groupby([pd.Grouper(key="expedido", freq="M"), "patologista", "exame"]).agg(
        {"nr_exame": "count", "imuno": "sum"}
    )

    imuno = df.groupby(["expedido", "patologista"]).agg({"imuno": "sum"})
    imuno["exame"] = "Imuno"
    imuno.columns = ["nr_exame", "exame"]

    df = pd.concat([df.reset_index(), imuno.reset_index()]).drop(columns="imuno")

    total = df.groupby(["expedido", "exame"]).agg({"nr_exame": "sum"})
    total["patologista"] = "Total"
    df = pd.concat([df, total.reset_index()])
    plot_media(
        df,
        ("Histologia", "Citologia", "Imuno"),
        "mean(nr_exame)",
        "patologista",
        "-x",
        ".0f",
    )


def show_media_tipos_de_exame(df):
    excluir_hba = st.checkbox("Excluir HBA", key="imuno_hba")
    if excluir_hba:
        df = df[~df.tipo_exame.str.contains("hba", case=False)]
    df = (
        df.groupby([pd.Grouper(key="expedido", freq="M"), "exame", "tipo_exame"])
        .agg({"nr_exame": "count"})
        .reset_index()
    )

    total = df.groupby(["expedido", "exame"]).agg({"nr_exame": "sum"})
    total["tipo_exame"] = "Total"

    df = pd.concat([df, total.reset_index()])

    plot_media(
        df, ("Histologia", "Citologia"), "mean(nr_exame)", "tipo_exame", "-x", ".0f"
    )


def select_medias(df):
    option = st.radio(
        "",
        ["Casos por Mês", "Tipos de Exame por Mês", "Tempo de Resposta"],
        horizontal=True,
    )

    if option == "Casos por Mês":
        show_media_casos(df)
    elif option == "Tipos de Exame por Mês":
        show_media_tipos_de_exame(df)
    elif option == "Tempo de Resposta":
        show_media_tempo_de_resposta(df)


def main_page():
    df = get_stored_data()
    df["exame"] = df.tipo_exame.mask(
        (df.tipo_exame.str.contains("citologia", case=False))
        | (df.tipo_exame.str.contains("mielo", case=False)),
        "Citologia",
    )
    df["exame"] = df.exame.mask(
        ~df.exame.str.contains("citologia", case=False), "Histologia"
    )
    df["tempo_de_resposta"] = (df.expedido - df.entrada).apply(lambda x: x.days)
    options = [
        "Gerais",
        "Médias",
    ]

    selection = st.selectbox("", options, index=0)

    if selection == options[0]:
        select_gerais(df)
    elif selection == options[1]:
        select_medias(df)


def upload_files():
    df = get_stored_data()
    uploaded_files = st.file_uploader(
        "",
        type="xls",
        accept_multiple_files=True,
    )

    if uploaded_files:
        for file in uploaded_files:
            file_df = pd.read_html(file, header=0)[0][:-1]
            unidade = file.name.split(".")[0]
            if (unidade not in df.unidade.unique()) or (len(file_df.columns) != 12):
                st.error(f"Ficheiro errado: {file.name}")
                st.stop()
            file_df.drop(
                columns=["Paciente", "Cód. Facturação", "NHC", "Episódio", "Soarian"],
                inplace=True,
            )
            file_df["unidade"] = unidade
            file_df.columns = df.columns
            file_df = file_df.replace("....", None).fillna(0)
            file_df[["ano", "nr_exame", "imuno"]] = file_df[
                ["ano", "nr_exame", "imuno"]
            ].astype(int)
            file_df[["entrada", "expedido"]] = file_df[["entrada", "expedido"]].apply(
                pd.to_datetime, format="%d-%m-%Y"
            )
            df = pd.concat([df, file_df, df])
        df.drop_duplicates(keep=False, inplace=True)
        df.to_sql("sispat", engine, if_exists="append", index=False)
        st.success("Ficheiros Carregados")


if "user" not in st.session_state:
    login()
    st.stop()

option = st.sidebar.radio("", ["Ver Dados", "Carregar Ficheiros"])

if option == "Ver Dados":
    main_page()
else:
    upload_files()
