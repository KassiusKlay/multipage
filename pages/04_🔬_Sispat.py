import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import altair as alt
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


@st.cache_data
def get_stored_data():
    return pd.read_sql(
        "SELECT * FROM sispat", engine, parse_dates=["entrada", "expedido"]
    )


@st.cache_data
def process_df(df):
    df["exame"] = df.tipo_exame.mask(
        (df.tipo_exame.str.contains("citologia", case=False))
        | (df.tipo_exame.str.contains("mielo", case=False)),
        "Citologia",
    )
    df["exame"] = df.exame.mask(
        ~df.exame.str.contains("citologia", case=False), "Histologia"
    )
    df["tempo_de_resposta"] = (df.expedido - df.entrada).apply(lambda x: x.days)

    df = (
        df.groupby(
            [pd.Grouper(key="expedido", freq="M"), "exame", "tipo_exame", "patologista"]
        )
        .agg({"nr_exame": "count", "imuno": "sum", "tempo_de_resposta": "mean"})
        .reset_index()
    )
    return df


def plot_line(df, plot_selection):
    if plot_selection == "Total Mensal":
        freq = "M"
        aggregate = {"nr_exame": "sum"}
        x_axis = "yearmonth(expedido):T"
        y_axis = "nr_exame"
        y_axis_mean = "mean(nr_exame)"
        text_format = ".0f"
        tick_count = {"interval": "month", "step": 6}

    elif plot_selection == "Total Anual":
        freq = "Y"
        aggregate = {"nr_exame": "sum"}
        x_axis = "year(expedido):T"
        y_axis = "nr_exame"
        y_axis_mean = "mean(nr_exame)"
        text_format = ".0f"
        tick_count = "year"

    elif plot_selection == "Media Mensal / Ano":
        freq = "M"
        aggregate = {"nr_exame": "sum"}
        x_axis = "year(expedido):T"
        y_axis = y_axis_mean = "mean(nr_exame)"
        text_format = ".0f"
        tick_count = "year"

    elif plot_selection == "Tempo de Resposta":
        df = df[
            ~(
                (df.patologista == "Dra. Ana Catarino")
                & (df.expedido.dt.to_period("M") == "2022-05")
            )
        ]
        freq = "M"
        aggregate = {"tempo_de_resposta": "mean"}
        x_axis = "year(expedido):T"
        y_axis = y_axis_mean = "mean(tempo_de_resposta)"
        text_format = "0.1f"
        tick_count = "year"

    df = df.groupby(pd.Grouper(key="expedido", freq=freq)).agg(aggregate).reset_index()

    line = (
        alt.Chart()
        .mark_line(point=True, interpolate="step")
        .encode(
            x=alt.X(
                x_axis,
                axis=alt.Axis(tickCount=tick_count),
                scale=alt.Scale(padding=20),
            ),
            y=y_axis,
            tooltip=alt.Text(y_axis, format=text_format),
        )
    )

    rule = (
        alt.Chart()
        .mark_rule(strokeDash=[12, 6], size=2)
        .encode(y=y_axis_mean, color=alt.value("lightgrey"), size=alt.value(2))
    )

    text_rule = (
        alt.Chart()
        .mark_text(align="left", color="lightgrey", dy=10)
        .encode(
            x=alt.value(1),
            y=y_axis_mean,
            text=alt.Text(y_axis_mean, format=text_format),
            size=alt.value(15),
        )
    )
    layer = (
        alt.layer(rule + text_rule + line, data=df)
        .configure_axis(grid=False, title="")
        .configure_view(strokeWidth=0)
        .properties(width=700)
    )
    st.altair_chart(layer)


def plot_bar(df, plot_selection):
    if "Tempo de Resposta" in plot_selection:
        df = df[
            ~df.tipo_exame.str.contains("Aditamento")
            & ~df.tipo_exame.str.contains("Tipagem")
            & ~df.tipo_exame.str.contains("Captura")
            & ~df.tipo_exame.str.contains("Aut")
            & ~(df.tipo_exame == "Caso de Consulta")
            & ~(
                (df.patologista == "Dra. Ana Catarino")
                & (df.expedido.dt.to_period("M") == "2022-05")
            )
            & ~(
                df.patologista.isin(
                    [
                        "Dra. Helena Oliveira",
                        "Dr. Paulo Bernardo",
                        "Prof. António Medina de Almeida",
                    ]
                )
            )
        ]
        aggregate = {"tempo_de_resposta": "mean"}
        patologista = "Media"
        x_axis = "mean(tempo_de_resposta)"
        sort = "x"
        text_format = ".1f"
        transform_filter = "datum.patologista != 'Dra. Helena Oliveira'"
    elif "Media de Casos" in plot_selection:
        aggregate = {"nr_exame": "sum"}
        patologista = "Total"
        x_axis = "mean(nr_exame)"
        sort = "-x"
        text_format = ".0f"
        transform_filter = "datum.mean_nr_exame > 10"

    start_year, end_year = st.select_slider(
        "options",
        range(df.expedido.min().year, df.expedido.max().year + 1),
        value=(df.expedido.min().year, df.expedido.max().year),
        label_visibility="collapsed",
    )

    df = df[df.expedido.dt.year.between(start_year, end_year)]

    df = df.groupby([pd.Grouper(key="expedido", freq="M"), "patologista"]).agg(
        aggregate
    )
    total = df.groupby("expedido").agg(aggregate)
    total["patologista"] = patologista
    df = pd.concat([df.reset_index(), total.reset_index()])

    bar = (
        alt.Chart()
        .mark_bar()
        .encode(
            x=alt.X(
                x_axis,
                axis=None,
            ),
            y=alt.Y("patologista", sort=sort),
            color=alt.condition(
                f"datum.patologista == '{patologista}'",
                alt.value("orange"),
                alt.value("steelblue"),
            ),
        )
    )

    text = (
        alt.Chart()
        .mark_text(align="left", dx=2)
        .encode(
            x=x_axis,
            y=alt.Y("patologista", sort=sort),
            text=alt.Text(x_axis, format=text_format),
        )
    )

    chart = (
        alt.layer(bar + text, data=df)
        .configure_axis(grid=False, title="")
        .configure_view(strokeWidth=0)
        .properties(width=700)
        .transform_joinaggregate(
            mean_nr_exame="mean(nr_exame)", groupby=["patologista"]
        )
        .transform_filter(transform_filter)
    )

    st.altair_chart(chart)


def main_page():
    df = get_stored_data()
    df = process_df(df)
    lista_patologistas = df.patologista.sort_values().unique().tolist()
    lista_patologistas.insert(0, "Todos")

    cols = st.columns(3)

    data_selection = cols[0].selectbox(
        "Tipo de Dados", ["Histologia", "Citologia", "Imuno", "Comparativos"]
    )
    if data_selection in ["Histologia", "Citologia", "Imuno"]:
        filter_patologista = cols[1].selectbox("Patologista", lista_patologistas, 0)
        if filter_patologista != "Todos":
            df = df[df.patologista == filter_patologista]
        if data_selection in ["Histologia", "Citologia"]:
            df = df[df.exame == data_selection]
            lista_tipos_exame = df.tipo_exame.sort_values().unique().tolist()
            lista_tipos_exame.insert(0, "Todos")
            filter_tipo_exame = cols[2].selectbox("Tipo de Exame", lista_tipos_exame, 0)
            if filter_tipo_exame != "Todos":
                df = df[df.tipo_exame == filter_tipo_exame]
            else:
                df = df[
                    ~df.tipo_exame.str.contains("Aditamento")
                    & ~df.tipo_exame.str.contains("Tipagem")
                    & ~df.tipo_exame.str.contains("Captura")
                    & ~df.tipo_exame.str.contains("Aut")
                    & ~(df.tipo_exame == "Caso de Consulta")
                ]
        else:
            df = df[["expedido", "tipo_exame", "imuno"]]
            df.columns = ["expedido", "tipo_exame", "nr_exame"]
        lista_graficos = ["Total Mensal", "Total Anual", "Media Mensal / Ano"]
        if data_selection != "Imuno":
            lista_graficos.insert(3, "Tempo de Resposta")
    else:
        df = df[
            ~df.tipo_exame.str.contains("Aditamento")
            & ~df.tipo_exame.str.contains("Tipagem")
            & ~df.tipo_exame.str.contains("Aut")
            & ~(df.tipo_exame == "Caso de Consulta")
        ]
        filter_exame = cols[1].selectbox(
            "Tipo de Dados", ["Histologia", "Citologia", "Imuno"]
        )
        if filter_exame in ["Histologia", "Citologia"]:
            df = df[df.exame == filter_exame]
        else:
            df = df[["expedido", "patologista", "tipo_exame", "imuno"]]
            df.columns = ["expedido", "patologista", "tipo_exame", "nr_exame"]
        lista_graficos = ["Media de Casos por Mes"]
        if filter_exame != "Imuno":
            lista_graficos.insert(1, "Tempo de Resposta")

    excluir_hba = st.checkbox("Excluir HBA")
    if excluir_hba:
        df = df[~df.tipo_exame.str.contains("hba", case=False)]

    plot_selection = st.radio(
        "options", lista_graficos, horizontal=True, label_visibility="collapsed"
    )
    if data_selection == "Comparativos":
        plot_bar(df, plot_selection)
    else:
        plot_line(df, plot_selection)


def upload_files():
    df = get_stored_data()
    uploaded_files = st.file_uploader(
        "",
        type="xls",
        accept_multiple_files=True,
    )

    if uploaded_files:
        new_df = pd.DataFrame()
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
            new_df = pd.concat([new_df, file_df])
        df = pd.concat([df, new_df, df]).drop_duplicates(keep=False)
        st.write(df)
        df.to_sql("sispat", engine, if_exists="append", index=False)
        get_stored_data.clear()
        st.success("Ficheiros Carregados")


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
