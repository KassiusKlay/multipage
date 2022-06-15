import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import altair as alt

st.set_page_config(layout='centered')


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


engine = init_engine()


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
    return pd.read_sql(
            'SELECT * FROM sispat', engine, parse_dates=['entrada', 'expedido']
            )


def show_total_plot(df):
    df = df.loc[
            ~df.tipo_exame.str.contains('Aditamento')
            & ~df.tipo_exame.str.contains('Tipagem')
            ]
    st.title('Total de Exames')

    excluir = st.checkbox('Excluir HBA', key='total_hba')
    if excluir:
        df = df[~df.tipo_exame.str.contains('hba', case=False)]
    anual = st.checkbox('Anual', key='total_anual')
    if anual:
        freq = 'Y'
        x_axis = 'year(expedido):T'
        tick_count = 'year'
    else:
        freq = 'M'
        x_axis = 'yearmonth(expedido):T'
        tick_count = {"interval": "month", "step": 3}

    df = df.groupby([pd.Grouper(key='expedido', freq=freq), 'exame']).agg(
            {'nr_exame': 'count'})
    total = df.groupby('expedido').agg({'nr_exame': 'sum'})
    total['exame'] = 'Total'
    df = pd.concat([df.reset_index(), total.reset_index()])

    line = alt.Chart(df.reset_index()).mark_line(
            ).encode(
                    x=alt.X(x_axis, axis=alt.Axis(tickCount=tick_count)),
                    y='nr_exame',
                    color=alt.Color('exame', title=''),
                    tooltip='nr_exame',
                    ).configure_axis(grid=False, title='').configure_view(
                            strokeWidth=0)

    st.altair_chart(line, use_container_width=True)


def show_tipo_de_exame_plot(df):
    st.title('Tipo de Exame')

    tipo_exame = st.multiselect('', df.tipo_exame.sort_values().unique())
    if tipo_exame:
        anual = st.checkbox('Anual', key='tipo_exame_anual')
        if anual:
            freq = 'Y'
            x_axis = 'year(expedido):T'
            tick_count = 'year'
        else:
            freq = 'M'
            x_axis = 'yearmonth(expedido):T'
            tick_count = {"interval": "month", "step": 3}
        df = df[df.tipo_exame.isin(tipo_exame)]
        df = df.groupby([
            pd.Grouper(key='expedido', freq=freq), 'tipo_exame'
            ]).agg({'nr_exame': 'count'})

        line = alt.Chart(df.reset_index()).mark_line(
                ).encode(
                        x=alt.X(x_axis, axis=alt.Axis(tickCount=tick_count)),
                        y='nr_exame',
                        color=alt.Color('tipo_exame', title=''),
                        tooltip='nr_exame',
                        ).configure_axis(grid=False, title='').configure_view(
                                strokeWidth=0)

        st.altair_chart(line, use_container_width=True)
    else:
        st.warning('Por favor escolha um tipo de exame')


def show_imuno_plot(df):
    st.title('Imuno')
    excluir_hba = st.checkbox('Excluir HBA', key='imuno_hba')
    if excluir_hba:
        df = df[~df.tipo_exame.str.contains('hba', case=False)]

    anual = st.checkbox('Anual', key='imuno_anual')
    if anual:
        freq = 'Y'
        x_axis = 'year(expedido):T'
        tick_count = 'year'
    else:
        freq = 'M'
        x_axis = 'yearmonth(expedido):T'
        tick_count = {"interval": "month", "step": 3}

    df = df.groupby(
        pd.Grouper(key='expedido', freq=freq)).agg({'imuno': 'sum'})

    line = alt.Chart(df.reset_index()).mark_line(
            ).encode(
                    x=alt.X(x_axis, axis=alt.Axis(tickCount=tick_count)),
                    y='imuno',
                    tooltip='imuno',
                    ).configure_axis(grid=False, title='').configure_view(
                            strokeWidth=0)
    st.altair_chart(line, use_container_width=True)


def show_patologista_plot(df):
    df = df.loc[
            ~df.tipo_exame.str.contains('Aditamento')
            & ~df.tipo_exame.str.contains('Tipagem')
            & ~(df.patologista.isin([
                'Dra. Helena Oliveira',
                'Dra. Rosa Madureira',
                'Dr. Paulo Bernardo',
                'Prof. António Medina de Almeida',
                'Dra. Maria Delfina Brito',
                ]))
            ]
    st.title('Patologista')
    df = df.groupby([
        pd.Grouper(key='expedido', freq='M'),
        'patologista', 'exame']).agg({
            'nr_exame': 'count',
            'imuno': 'sum'})

    imuno = df.groupby(['expedido', 'patologista']).agg({'imuno': 'sum'})
    imuno['exame'] = 'Imuno'
    imuno.columns = ['nr_exame', 'exame']

    df = pd.concat([
        df.reset_index(), imuno.reset_index()
        ]).drop(columns='imuno')

    for i in ('Histologia', 'Citologia', 'Imuno'):
        st.subheader(i)
        bar = alt.Chart(df).mark_bar(
                ).encode(
                        x='mean(nr_exame)',
                        y=alt.Y('patologista', sort='-x'),
                        tooltip='mean(nr_exame)',
                        ).configure_axis(grid=False, title='').configure_view(
                                strokeWidth=0).transform_filter(
                                        (alt.datum.exame == i))

        st.altair_chart(bar, use_container_width=True)

    patologista = st.selectbox(
            '', df.patologista.sort_values().unique(),
            key='patologista_select')
    if patologista:
        df = df[df.patologista == patologista]
        anual = st.checkbox('Anual', key='patologista_anual')
        if anual:
            freq = 'Y'
            x_axis = 'year(expedido):T'
            tick_count = 'year'
        else:
            freq = 'M'
            x_axis = 'yearmonth(expedido):T'
            tick_count = {"interval": "month", "step": 6}
        df = df.groupby([
            pd.Grouper(key='expedido', freq=freq), 'exame']).agg({
                'nr_exame': 'sum'})
        line = alt.Chart(df.reset_index()).mark_line(
                ).encode(
                        x=alt.X(x_axis, axis=alt.Axis(tickCount=tick_count)),
                        y='nr_exame',
                        color=alt.Color('exame', title=''),
                        tooltip='nr_exame',
                        ).configure_axis(grid=False, title='').configure_view(
                                strokeWidth=0)

        st.altair_chart(line, use_container_width=True)


def show_tempo_de_resposta(df):
    df = df.loc[
            ~df.tipo_exame.str.contains('Aditamento')
            & ~df.tipo_exame.str.contains('Tipagem')
            & ~df.tipo_exame.str.contains('Aut')
            & ~(df.patologista.isin([
                'Dra. Helena Oliveira',
                'Dra. Rosa Madureira',
                'Dr. Paulo Bernardo',
                'Prof. António Medina de Almeida',
                'Dra. Maria Delfina Brito',
                ]))
            ]

    st.title('Tempo de Resposta')

    df = df.groupby([
        pd.Grouper(key='expedido', freq='M'),
        'patologista', 'exame']).agg({
            'nr_exame': 'count', 'tempo_de_resposta': 'mean'}).reset_index()

    for i in ('Histologia', 'Citologia'):
        st.subheader(i)
        bar = alt.Chart(df).mark_bar(
                ).encode(
                        x='mean(tempo_de_resposta)',
                        y=alt.Y('patologista', sort='x'),
                        tooltip='mean(tempo_de_resposta)',
                        ).configure_axis(grid=False, title='').configure_view(
                                strokeWidth=0).transform_filter(
                                        (alt.datum.exame == i))

        st.altair_chart(bar, use_container_width=True)

    patologista = st.multiselect(
            '', df.patologista.sort_values().unique(),
            key='tempo_de_resposta_multi')

    if patologista:
        df = df[df.patologista.isin(patologista)]
        anual = st.checkbox('Anual', key='tempo_de_resposta_anual')
        if anual:
            x_axis = 'year(expedido):T'
            tick_count = 'year'
        else:
            x_axis = 'yearmonth(expedido):T'
            tick_count = {"interval": "month", "step": 3}

        for i in ('Histologia', 'Citologia'):
            st.subheader(i)
            line = alt.Chart(df.reset_index()).mark_line(
                    ).encode(
                            x=alt.X(
                                x_axis, axis=alt.Axis(tickCount=tick_count)),
                            y='mean(tempo_de_resposta)',
                            color=alt.Color('patologista', title=''),
                            tooltip='mean(tempo_de_resposta)',
                            ).configure_axis(
                                    grid=False, title=''
                                    ).configure_view(
                                    strokeWidth=0).transform_filter(
                                            (alt.datum.exame == i))

            st.altair_chart(line, use_container_width=True)


def main_page():
    df = get_stored_data()
    df['exame'] = df.tipo_exame.mask(
            (df.tipo_exame.str.contains('citologia', case=False))
            | (df.tipo_exame.str.contains('mielo', case=False)),
            'Citologia')
    df['exame'] = df.exame.mask(
            ~df.exame.str.contains('citologia', case=False), 'Histologia')
    df['tempo_de_resposta'] = (df.expedido - df.entrada).apply(
            lambda x: x.days)
    show_total_plot(df)
    show_tipo_de_exame_plot(df)
    show_imuno_plot(df)
    show_patologista_plot(df)
    show_tempo_de_resposta(df)


def upload_files():
    df = get_stored_data()
    uploaded_files = st.file_uploader(
            '',
            type='xls',
            accept_multiple_files=True,
            )

    if uploaded_files:
        for file in uploaded_files:
            file_df = pd.read_html(file, header=0)[0][:-1]
            unidade = file.name.split('.')[0]
            if (unidade not in df.unidade.unique())\
                    or (len(file_df.columns) != 12):
                st.error(f'Ficheiro errado: {file.name}')
                st.stop()
            file_df.drop(columns=['Paciente', 'Cód. Facturação'], inplace=True)
            file_df['unidade'] = unidade
            file_df.columns = df.columns
            file_df = file_df.replace('....', None).fillna(0)
            file_df[[
                'ano', 'nr_exame', 'nhc', 'episodio', 'soarian', 'imuno'
                ]] = file_df[[
                    'ano', 'nr_exame', 'nhc', 'episodio', 'soarian', 'imuno'
                ]].astype(int)
            file_df[['entrada', 'expedido']] = file_df[[
                'entrada', 'expedido']].apply(
                        pd.to_datetime, format='%d-%m-%Y')
            df = pd.concat([df, file_df, df])
        df.drop_duplicates(keep=False, inplace=True)
        df.to_sql('sispat', engine, if_exists='append', index=False)
        st.success('Ficheiros Carregados')


if 'user' not in st.session_state:
    login()
    st.stop()

option = st.radio('', ['Ver Dados', 'Carregar Ficheiros'], horizontal=True)

if option == 'Ver Dados':
    main_page()
else:
    upload_files()


