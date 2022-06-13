import pydeck as pdk
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import unidecode

st.set_page_config(layout='wide')


def remove_accent(string):
    return unidecode.unidecode(string)


def remove_accent_from_series(series):
    return series.apply(remove_accent)


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


@st.experimental_memo(ttl=6000)
def pd_read_sql(sql):
    return pd.read_sql(sql, engine)


def show_last_updated():
    st.write('INÍCIO DOS DADOS: ', pd_read_sql(
            'SELECT MIN(date) FROM remax_total_listings').loc[0, max])
    st.write('ÚLTIMA ACTUALIZAÇÃO: ', pd_read_sql(
            'SELECT MAX(date) FROM remax_total_listings').loc[0, max])


def apply_color(x):
    alpha = 170
    if pd.isna(x):
        value = [0, 0, 0, alpha]
    elif x > 0.75:
        value = [167, 0, 0, alpha]
    elif x > 0.5:
        value = [255, 0, 0, alpha]
    elif x > 0.25:
        value = [255, 82, 82, alpha]
    elif x > 0:
        value = [255, 186, 186, alpha]
    elif x < -0.75:
        value = [0, 128, 0, alpha]
    elif x < -0.5:
        value = [34, 139, 34, alpha]
    elif x < -0.25:
        value = [50, 205, 50, alpha]
    else:
        value = [144, 238, 144, alpha]
    return value


@st.experimental_memo(ttl=6000)
def get_mean_price_m2(radio1):
    df = pd_read_sql(
            f"""
            SELECT
                    listings.id, listings.listing_price,
                    listing_types.name AS listing_type,
                    listings."area",
                    region1.name AS region1,
                    region2.name AS region2,
                    region3.name AS region3
            FROM
                    remax_listings listings
            INNER JOIN remax_listing_types listing_types
                    ON listing_types.id = listings.listing_type_id
            INNER JOIN remax_business_types business_types
                    ON business_types.id = listings.business_type_id
            INNER JOIN remax_region1 region1
                    ON region1.id = listings.region1_id
            INNER JOIN remax_region2 region2
                    ON region2.id = listings.region2_id
            INNER JOIN remax_region3 region3
                    ON region3.id = listings.region3_id
            INNER JOIN remax_listing_dates listing_dates
                    ON listing_dates.id = listings.id
            WHERE
                    listing_dates.date_removed IS NULL
                    AND
                    business_types.name = '{radio1}'
            """)
    df['price_m2'] = df.listing_price / df.area
    df.price_m2 = df.price_m2.where(df.area != 0, None)
    return df.groupby(
            ['listing_type', 'region1', 'region2', 'region3']
            ).agg({'price_m2': 'mean'}).round(2)


@st.experimental_memo(ttl=6000)
def get_map_df(radio1, radio2, radio3, radio4, radio5):
    sql = f"""
        SELECT
                listings.id, listings.listing_price, listings.latitude,
                listings.longitude,
                listings."area", listings.bedrooms, listings.bathrooms,
                listing_types.name AS listing_type,
                region1.name AS region1,
                region2.name AS region2,
                region3.name AS region3
        FROM
                remax_listings listings
        INNER JOIN remax_listing_types listing_types
                ON listing_types.id = listings.listing_type_id
        INNER JOIN remax_business_types business_types
                ON business_types.id = listings.business_type_id
        INNER JOIN remax_region1 region1
                ON region1.id = listings.region1_id
        INNER JOIN remax_region2 region2
                ON region2.id = listings.region2_id
        INNER JOIN remax_region3 region3
                ON region3.id = listings.region3_id
        INNER JOIN remax_listing_dates listing_dates
                ON listing_dates.id = listings.id
        WHERE
                business_types.name = '{radio1}'
                AND
                listing_types.name = '{radio2}'
                AND
                listing_dates.date_removed IS NULL"""
    if radio3:
        sql = sql + f""" AND region1.name = '{radio3}'"""
    if radio4:
        sql = sql + f"""AND region2.name = '{radio4}'"""
    if radio5:
        sql = sql + f"""AND region3.name = '{radio5}'"""
    df = pd_read_sql(sql)

    df['price_m2'] = round(df.listing_price / df.area, 2)
    df.price_m2 = df.price_m2.where(df.area != 0, None)
    mean_price_m2 = get_mean_price_m2(radio1)

    df = df.assign(
        delta0=list(df.listing_type),
        delta1=list(zip(df.listing_type, df.region1)),
        delta2=list(zip(df.listing_type, df.region1, df.region2)),
        delta3=list(zip(df.listing_type, df.region1, df.region2, df.region3)),
        )
    df['avg0'] = df.delta0.map(mean_price_m2.groupby(
        'listing_type').mean().round(2)['price_m2'])
    df['avg1'] = df.delta1.map(mean_price_m2.groupby(
            ['listing_type', 'region1']
            ).mean().round(2)['price_m2'])
    df['avg2'] = df.delta2.map(mean_price_m2.groupby(
            ['listing_type', 'region1', 'region2']
            ).mean().round(2)['price_m2'])
    df['avg3'] = df.delta3.map(mean_price_m2['price_m2'])
    for i in range(4):
        df[f'delta{i}'] = df[[
            f'avg{i}', 'price_m2']].pct_change(axis=1)['price_m2']
        df[f'color{i}'] = df[f'delta{i}'].apply(apply_color)
    return df


@st.experimental_memo(ttl=6000)
def get_plot_df(radio1, radio2, radio3, radio4, radio5):
    sql = f"""
        SELECT
                listings.listing_price,
                listings."area",
                listing_dates.date_added AS date_added,
                region1.name AS region1,
                region2.name AS region2,
                region3.name AS region3
        FROM
                remax_listings listings
        INNER JOIN remax_listing_types listing_types
                ON listing_types.id = listings.listing_type_id
        INNER JOIN remax_business_types business_types
                ON business_types.id = listings.business_type_id
        INNER JOIN remax_region1 region1
                ON region1.id = listings.region1_id
        INNER JOIN remax_region2 region2
                ON region2.id = listings.region2_id
        INNER JOIN remax_region3 region3
                ON region3.id = listings.region3_id
        INNER JOIN remax_listing_dates listing_dates
                ON listing_dates.id = listings.id
        WHERE
                business_types.name = '{radio1}'
                AND
                listing_types.name = '{radio2}'"""
    if radio3:
        sql = sql + f""" AND region1.name = '{radio3}'"""
    if radio4:
        sql = sql + f"""AND region2.name = '{radio4}'"""
    if radio5:
        sql = sql + f"""AND region3.name = '{radio5}'"""
    df = pd_read_sql(sql)
    df['price_m2'] = df.listing_price / df.area
    df.price_m2 = df.price_m2.where(df.area != 0, None)
    df = df.groupby('date_added').agg({'price_m2': 'mean'})
    return df


def variation_per_business_type():
    df = pd_read_sql(
            """
            SELECT total_listings, date, business_types.name AS business_type,
                region1.name AS region1
            FROM remax_total_listings
            JOIN remax_business_types business_types
                ON business_types.id = remax_total_listings.business_type_id
            JOIN remaX_region1 region1
                ON region1.id = remax_total_listings.id
            """)

    df.total_listings = df.total_listings.where(df.total_listings > 0, 1)
    type_df = df.groupby(['date', 'business_type']).agg({
        'total_listings': 'sum'})
    type_df = type_df.reset_index().pivot(
            index='date', columns='business_type', values='total_listings')
    type_pct_df = type_df.pct_change(periods=len(type_df)-1)

    region_df = df.groupby(['date', 'business_type', 'region1']).agg({
        'total_listings': 'sum'})
    region_df = region_df.reset_index().pivot(
            index='date',
            columns=['business_type', 'region1'],
            values='total_listings')
    region_pct_df = region_df.pct_change(periods=len(region_df)-1)

    st.title('Evolução do Mercado')
    for _, business_type in enumerate(('Alugar', 'Comprar')):
        st.header(business_type)
        cols_region = st.columns(3)
        cols_region[0].metric(
                'Total',
                type_df.loc[type_df.index.max(), business_type],
                f'''{type_pct_df.loc[
                type_pct_df.index.max(), business_type]:.0%}''')
        sub_df = region_pct_df.loc[region_pct_df.index.max()][business_type]
        region_max = sub_df[sub_df == sub_df.max()].index[0]
        delta_max = f'{sub_df.max():.0%}'

        region_min = sub_df[sub_df == sub_df.min()].index[0]
        delta_min = f'{sub_df.min():.0%}'
        cols_region[1].metric('Maior oferta', region_max, delta_max)
        cols_region[2].metric('Menor oferta', region_min, delta_min)


def get_radio_selection():
    listing_types = pd_read_sql(
            'SELECT name FROM remax_listing_types').name.to_list()
    business_types = pd_read_sql(
            'SELECT name FROM remax_business_types').name.to_list()
    region1 = pd_read_sql(
            'SELECT name FROM remax_region1'
            ).name.sort_values(key=remove_accent_from_series).to_list()
    region1.insert(0, 'Todos')
    region2 = pd_read_sql(
            'SELECT name FROM remax_region2').name.to_list()
    cols = st.columns(4)
    radio1 = cols[0].radio('', options=business_types)
    radio2 = cols[0].radio('', options=listing_types)
    color_selection = cols[0].radio(
            'Comparar preco_m2 com média:',
            ['Nacional', 'Distrito', 'Concelho', 'Freguesia'])
    radio3 = cols[1].radio('', options=region1)
    if radio3 == 'Todos':
        radio3 = None
        radio4 = None
        radio5 = None
    else:
        region2 = pd_read_sql(
                f"""
                SELECT remax_region2.name FROM remax_region2
                JOIN remax_region1
                ON remax_region1.id = remax_region2.region1_id
                WHERE remax_region1.name = '{radio3}'
                """
                ).name.sort_values(
                        key=remove_accent_from_series).to_list()
        region2.insert(0, 'Todos')
        radio4 = cols[2].radio('', options=region2)
        if radio4 == 'Todos':
            radio4 = None
            radio5 = None
        else:
            region3 = pd_read_sql(
                f"""
                SELECT remax_region3.name FROM remax_region3
                JOIN remax_region2
                ON remax_region2.id = remax_region3.region2_id
                WHERE remax_region2.name = '{radio4}'
                """
                ).name.sort_values(
                        key=remove_accent_from_series).to_list()
            region3.insert(0, 'Todos')
            radio5 = cols[3].radio('', options=region3)
            if radio5 == 'Todos':
                radio5 = None
    return radio1, radio2, radio3, radio4, radio5, color_selection


def show_plot(df):
    st.title('Preco por m2 por data de inserção')
    st.line_chart(df)


def show_map(df, color_selection):
    st.title('Mapa dos resultados')
    if color_selection == 'Nacional':
        color = 'color0'
    elif color_selection == 'Distrito':
        color = 'color1'
    elif color_selection == 'Concelho':
        color = 'color2'
    else:
        color = 'color3'
    map_style = "mapbox://styles/mapbox/light-v9"
    view_state = pdk.ViewState(
            latitude=df.latitude.mean(),
            longitude=df.longitude.mean(),
            zoom=9,
            pitch=0)
    if df.latitude.isna().sum() == len(df):
        st.warning('Sem coordenadas disponíveis para apresentar')
        return
    df = df.copy().fillna('--').reset_index()
    scatter = pdk.Layer(
            "ScatterplotLayer",
            data=df,
            get_position="[longitude, latitude]",
            get_color=color,
            get_radius="listing_price",
            radius_scale=0.0001,
            radius_min_pixels=2,
            radius_max_pixels=10,
            pickable=True,
            autohighlight=True,
            )
    tooltip = {
            "html":
            "<b>Index:</b> {index}</br>"
            "<b>Preço:</b> {listing_price}</br>"
            "<b>Preço_m2:</b> {price_m2}</br>"
            "<b>Área:</b> {area}</br>"
            "<b>Quartos:</b> {bedrooms}</br>"
            "<b>Casas de Banho:</b> {bedrooms}",
    }
    chart = pdk.Deck(
            map_style=map_style,
            initial_view_state=view_state,
            layers=[scatter],
            tooltip=tooltip,
            )
    st.pydeck_chart(chart)


def show_listing(df):
    st.title('Características do Imóvel')
    selection = int(st.number_input(
        'Seleccione Index para ver Fotos',
        0))
    try:
        row = df.iloc[selection]
    except IndexError:
        st.warning('Por favor escolha um index disponível')
        st.stop()
    site_url_prefix = 'https://remax.pt/imoveis/a/'
    st.write(f'LINK: {site_url_prefix}{row.id}')
    st.write(
            'Preço: ', row.listing_price,
            'Area:', row.area,
            )
    cols = st.columns(5)
    cols[0].metric('Preço_m2', row.price_m2)
    for i, j in zip(
            range(1, 5),
            ('Nacional', 'Distrito', 'Concelho', 'Freguesia')):
        cols[i].metric(
                f'Media {j}', row[f'avg{i-1}'],
                f'{row[f"delta{i-1}"]:.0%}', delta_color='inverse')
    pictures = pd_read_sql(f"""
    SELECT listing_pictures FROM remax_listings
    WHERE id = '{row.id}'""").loc[0, 'listing_pictures'].split(',')
    pictures_url_prefix = 'https://i.maxwork.pt/l-view/'
    cols = st.columns(5)
    i = 0
    for picture in pictures:
        cols[i].image(pictures_url_prefix + picture)
        i += 1
        if i == 5:
            i = 0


def filter_price_area(df, color_selection):
    start_price, end_price = st.select_slider(
        'Escolha o preço', df.listing_price.sort_values(),
        value=(df.listing_price.min(), df.listing_price.max()))
    start_area, end_area = st.select_slider(
        'Escolha a área', df.area.sort_values(),
        value=(df.area.min(), df.area.max()))
    delta_selection = st.select_slider(
        'Escolha preco_m2:',
        ['Abaixo da média', 'Todos', 'Acima da média'],
        value='Todos')
    if color_selection == 'Nacional':
        delta = 'delta0'
    elif color_selection == 'Distrito':
        delta = 'delta1'
    elif color_selection == 'Concelho':
        delta = 'delta2'
    else:
        delta = 'delta3'
    df = df[(df.listing_price >= start_price)
            & (df.listing_price <= end_price)
            & (df.area >= start_area)
            & (df.area <= end_area)
            ]
    if delta_selection == 'Abaixo da média':
        df = df[df[f'{delta}'] < 0]
    elif delta_selection == 'Acima da média':
        df = df[df[f'{delta}'] > 0]
    return df.reset_index(drop=True)


def main():
    show_last_updated()
    variation_per_business_type()
    (
            radio1, radio2, radio3,
            radio4, radio5, color_selection) = get_radio_selection()
    map_df = get_map_df(radio1, radio2, radio3, radio4, radio5)
    if not map_df.empty:
        map_df = filter_price_area(map_df, color_selection)

    plot_df = get_plot_df(radio1, radio2, radio3, radio4, radio5)
    st.success(f'Encontrados {len(map_df)} resultados')
    if not plot_df.empty:
        show_plot(plot_df)
    if not map_df.empty:
        show_map(map_df, color_selection)
        show_listing(map_df)


if __name__ == '__main__':
    main()
