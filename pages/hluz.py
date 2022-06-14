import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import altair as alt


@st.experimental_singleton
def init_engine():
    return create_engine(
        f'postgresql://'
        f'{st.secrets["postgres"]["user"]}:'
        f'{st.secrets["postgres"]["password"]}@'
        f'{st.secrets["postgres"]["host"]}:'
        f'{st.secrets["postgres"]["port"]}/'
        f'{st.secrets["postgres"]["dbname"]}',
        )


def check_credentials():
    if not st.session_state.username\
            or not st.session_state.password\
            or st.session_state.username not in st.secrets.keys()\
            or st.secrets[st.session_state.username] !=\
            st.session_state.password:
        st.warning('Tente novamente')
        return
    else:
        st.session_state.user = st.session_state.username
        return


def login():
    with st.form('login'):
        st.text_input('Username', key='username')
        st.text_input('Password', key='password')
        st.form_submit_button('Login', on_click=check_credentials)


@st.experimental_memo
def get_stored_data():
    engine = init_engine()
    return pd.read_sql(
            'SELECT * FROM sispat', engine, parse_dates=['entrada', 'expedido']
            )

def show_histology_cytology_plot(df):
    st.title('Total de Exames')
    anual = st.checkbox('Anual', key='total_anual')
    if anual:
        freq = 'Y'
        x_axis = 'year(expedido):T'
        tick_count = 'year'
        label_angle = 0
    else:
        freq = 'M'
        x_axis = 'yearmonth(expedido):T'
        tick_count = 'month'
        label_angle = -90
    excluir = st.checkbox('Excluir HBA', key='total')
    if excluir:
        df = df[~df.tipo_exame.str.contains('hba', case=False)]

    df['exame'] = df.tipo_exame.mask(
            (df.tipo_exame.str.contains('citologia', case=False))
            | (df.tipo_exame.str.contains('mielo', case=False)),
            'Citologia')
    df['exame'] = df.exame.mask(
            ~df.exame.str.contains('citologia', case=False), 'Histologia')
    df = df.loc[
            ~df.tipo_exame.str.contains('Aditamento')
            & ~df.tipo_exame.str.contains('Tipagem')
            ]

    df = df.groupby([pd.Grouper(key='expedido', freq=freq), 'exame']).agg(
            {'nr_exame': 'count'})
    total = df.groupby('expedido').agg({'nr_exame': 'sum'})
    total['exame'] = 'Total'
    df = pd.concat([df.reset_index(), total.reset_index()])

    line = alt.Chart(df.reset_index()).mark_line(
            point=alt.OverlayMarkDef()
            ).encode(
                    x=alt.X(
                        x_axis,
                        axis=alt.Axis(
                            title='', tickCount=tick_count,
                            grid=False, labelAngle=label_angle)
                        ),
                    y=alt.Y('nr_exame', axis=alt.Axis(title='Exames')),
                    color=alt.Color('exame', title=''),
                    tooltip='nr_exame',
                    )

    st.altair_chart(line, use_container_width=True)


def show_cytology_plot(df):
    st.title('Citologia')
    anual = st.checkbox('Anual', key='citologia_anual')
    excluir_hba = st.checkbox('Excluir HBA', key='citologia')
    excluir_ginecologica = st.checkbox(
            'Excluir Ginecologica', key='ginecologica')
    if anual:
        freq = 'Y'
        x_axis = 'year(expedido):T'
        tick_count = 'year'
        label_angle = 0
    else:
        freq = 'M'
        x_axis = 'yearmonth(expedido):T'
        tick_count = 'month'
        label_angle = -90

    if excluir_hba:
        df = df[~df.tipo_exame.str.contains('hba', case=False)]
    if excluir_ginecologica:
        df = df[~df.tipo_exame.str.contains('ginec', case=False)]

    df = df[(df.tipo_exame.str.contains('citologia', case=False))
            | (df.tipo_exame.str.contains('mielo', case=False))]
    tipo_exame = st.multiselect('', df.tipo_exame.sort_values().unique())
    if tipo_exame:
        df = df[df.tipo_exame.isin(tipo_exame)]
    df = df.groupby([pd.Grouper(key='expedido', freq=freq), 'tipo_exame']).agg(
            {'nr_exame': 'count'})
    if len(tipo_exame) != 1:
        total = df.groupby('expedido').agg({'nr_exame': 'sum'})
        total['tipo_exame'] = 'Total'
        df = pd.concat([df.reset_index(), total.reset_index()])

    line = alt.Chart(df.reset_index()).mark_line(
            point=alt.OverlayMarkDef()
            ).encode(
                    x=alt.X(
                        x_axis,
                        axis=alt.Axis(
                            title='', tickCount=tick_count,
                            grid=False, labelAngle=label_angle)
                        ),
                    y=alt.Y('nr_exame', axis=alt.Axis(title='Exames')),
                    color=alt.Color('tipo_exame', title=''),
                    tooltip='nr_exame',
                    )

    st.altair_chart(line, use_container_width=True)


def show_imuno_plot(df):
    st.title('Imuno')
    anual = st.checkbox('Anual', key='imuno_anual')
    excluir_hba = st.checkbox('Excluir HBA', key='imuno')
    if anual:
        freq = 'Y'
        x_axis = 'year(expedido):T'
        tick_count = 'year'
        label_angle = 0
    else:
        freq = 'M'
        x_axis = 'yearmonth(expedido):T'
        tick_count = 'month'
        label_angle = -90

    if excluir_hba:
        df = df[~df.tipo_exame.str.contains('hba', case=False)]


def main_page():
    df = get_stored_data()
    show_histology_cytology_plot(df)
    show_cytology_plot(df)
    show_imuno_plot(df)


def upload_files():
    pass


if 'user' not in st.session_state:
    login()
    st.stop()

option = st.radio('', ['Ver Dados', 'Carregar Ficheiros'], horizontal=True)

if option == 'Ver Dados':
    main_page()
else:
    upload_files()


