import pydeck as pdk
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import unidecode
import numpy as np
import altair as alt

st.set_page_config(layout="wide")


def remove_accent(string):
    return unidecode.unidecode(string)


def remove_accent_from_series(series):
    return series.apply(remove_accent)


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


def pd_read_sql(sql, params=None):
    return pd.read_sql(sql, con=engine, params=params)


def show_last_updated():
    st.write(
        "INÍCIO DOS DADOS: ",
        pd_read_sql("SELECT MIN(date) FROM remax_total_listings").loc[0, max],
    )
    st.write(
        "ÚLTIMA ACTUALIZAÇÃO: ",
        pd_read_sql("SELECT MAX(date) FROM remax_total_listings").loc[0, max],
    )


def get_map_df(business_type, listing_type, region1, region2, region3):
    sql = f"""
        SELECT
                listings.id, listings.listing_price, listings.is_special,
                listings.latitude, listings.longitude,
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
        WHERE
                business_types.name = '{business_type}'
                AND
                listing_types.name = '{listing_type}'
        """
    if region1:
        sql = sql + f""" AND region1.name = '{region1}'"""
    if region2:
        sql = sql + f"""AND region2.name = '{region2}'"""
    if region3:
        sql = sql + f"""AND region3.name = '{region3}'"""
    df = pd_read_sql(sql)
    df = df[(df.listing_price > 0) & (df.area > 0)]
    start_price, end_price = st.select_slider(
        "Escolha o preço",
        df.listing_price.sort_values(),
        value=(df.listing_price.min(), df.listing_price.max()),
    )
    start_area, end_area = st.select_slider(
        "Escolha a área", df.area.sort_values(), value=(df.area.min(), df.area.max())
    )
    df = df[
        (df.listing_price >= start_price)
        & (df.listing_price <= end_price)
        & (df.area >= start_area)
        & (df.area <= end_area)
    ]
    special = st.checkbox("Apenas Remax Collection")
    if special:
        df = df[df.is_special]
    df["price_m2"] = (df.listing_price / df.area).round(0)
    avg_price_m2 = df["price_m2"].mean()
    df["normalized_price_m2"] = df["price_m2"].apply(
        lambda x: (x - avg_price_m2) / avg_price_m2
    )

    def get_color(price_m2):
        if price_m2 < -0.5:
            return [26, 150, 65]  # Dark green
        elif price_m2 < 0:
            return [166, 217, 106]  # Light green
        elif price_m2 < 0.5:
            return [239, 138, 98]  # Light red
        else:
            return [178, 24, 43]  # Dark red

    df["color"] = df["normalized_price_m2"].apply(get_color)
    return df


def show_map(df):
    map_style = "mapbox://styles/mapbox/light-v9"
    view_state = pdk.ViewState(
        latitude=df.latitude.mean(), longitude=df.longitude.mean(), zoom=9, pitch=0
    )
    if df.latitude.isna().sum() == len(df):
        st.warning("Sem coordenadas disponíveis para apresentar")
        return

    df = df.replace([np.inf, -np.inf], None).fillna("--").reset_index()
    scatter = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position="[longitude, latitude]",
        get_color="color",
        get_radius="listing_price",
        radius_scale=0.0001,
        radius_min_pixels=2,
        radius_max_pixels=10,
        pickable=True,
        autohighlight=True,
    )
    tooltip = {
        "html": "<b>Index:</b> {index}</br>"
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
    return


@st.cache_data(ttl=6000)
def show_plot(business_type, listing_type, region1, region2, region3):
    conditions = [
        f"business_types.name = '{business_type}'",
        f"listing_types.name = '{listing_type}'",
    ]
    if region1:
        conditions.append(f"region1.name = '{region1}'")
    if region2:
        conditions.append(f"region2.name = '{region2}'")
    if region3:
        conditions.append(f"region3.name = '{region3}'")

    where_clause = " AND ".join(conditions)

    sql = f"""
        SELECT
            listings.price_m2,
            listings.date
        FROM
            remax_price_m2 listings
        INNER JOIN remax_listing_types listing_types
            ON listing_types.id = listings.listing_type_id
        INNER JOIN remax_business_types business_types
            ON business_types.id = listings.listing_class_id
        INNER JOIN remax_region1 region1
            ON region1.id = listings.region1_id
        INNER JOIN remax_region2 region2
            ON region2.id = listings.region2_id
        INNER JOIN remax_region3 region3
            ON region3.id = listings.region3_id
        WHERE {where_clause}
    """
    df = pd_read_sql(sql)
    df["date"] = pd.to_datetime(df["date"], dayfirst=True)
    df = df[(df["price_m2"] >= 1)]
    chart = (
        alt.Chart(df)
        .mark_line(point=True)
        .encode(
            x=alt.X(
                "yearmonth(date):T",
                title="Month",
                axis=alt.Axis(format="%b %Y"),
                scale=alt.Scale(padding=10),
            ),
            y=alt.Y("mean(price_m2):Q", title="Average Price per m²"),
            tooltip=[
                alt.Tooltip("yearmonth(date):T", title="Month"),
                "mean(price_m2):Q",
            ],
        )
        .properties(
            title="Monthly Evolution of Average Price per m²",
        )
        .configure_view(strokeWidth=0)
    )
    st.altair_chart(chart, use_container_width=True)
    return


def show_variation_per_business_type():
    df = pd_read_sql(
        """
            SELECT total_listings, date, business_types.name AS business_type,
                region1.name AS region1
            FROM remax_total_listings
            JOIN remax_business_types business_types
                ON business_types.id = remax_total_listings.business_type_id
            JOIN remax_region1 region1
                ON region1.id = remax_total_listings.id
            """
    )

    df.total_listings = df.total_listings.where(df.total_listings > 0, 1)
    type_df = df.groupby(["date", "business_type"]).agg({"total_listings": "sum"})
    type_df = type_df.reset_index().pivot(
        index="date", columns="business_type", values="total_listings"
    )
    type_pct_df = type_df.pct_change(periods=len(type_df) - 1)

    region_df = df.groupby(["date", "business_type", "region1"]).agg(
        {"total_listings": "sum"}
    )
    region_df = region_df.reset_index().pivot(
        index="date", columns=["business_type", "region1"], values="total_listings"
    )
    region_pct_df = region_df.pct_change(periods=len(region_df) - 1)

    st.title("Evolução do Mercado")
    for _, business_type in enumerate(("Alugar", "Comprar")):
        st.header(business_type)
        cols_region = st.columns(3)
        cols_region[0].metric(
            "Total",
            type_df.loc[type_df.index.max(), business_type],
            f"""{type_pct_df.loc[
                type_pct_df.index.max(), business_type]:.0%}""",
        )
        sub_df = region_pct_df.loc[region_pct_df.index.max()][business_type]
        region_max = sub_df[sub_df == sub_df.max()].index[0]
        delta_max = f"{sub_df.max():.0%}"

        region_min = sub_df[sub_df == sub_df.min()].index[0]
        delta_min = f"{sub_df.min():.0%}"
        cols_region[1].metric("Maior oferta", region_max, delta_max)
        cols_region[2].metric("Menor oferta", region_min, delta_min)


def get_selection():
    listing_types = pd_read_sql("SELECT name FROM remax_listing_types").name.to_list()
    business_types = pd_read_sql("SELECT name FROM remax_business_types").name.to_list()
    region1 = (
        pd_read_sql("SELECT name FROM remax_region1")
        .name.sort_values(key=remove_accent_from_series)
        .to_list()
    )
    region1.insert(0, "Todos")
    cols = st.columns(4)
    business_type = cols[0].radio("", options=business_types)
    listing_type = cols[0].radio("", options=listing_types)
    region1 = cols[1].radio("", options=region1)
    if region1 == "Todos":
        region1 = region2 = region3 = None
    else:
        region2 = (
            pd_read_sql(
                f"""
                SELECT remax_region2.name FROM remax_region2
                JOIN remax_region1
                ON remax_region1.id = remax_region2.region1_id
                WHERE remax_region1.name = '{region1}'
                """
            )
            .name.sort_values(key=remove_accent_from_series)
            .to_list()
        )
        region2.insert(0, "Todos")
        region2 = cols[2].radio("", options=region2)
        if region2 == "Todos":
            region2 = region3 = None
        else:
            region3 = (
                pd_read_sql(
                    f"""
                SELECT remax_region3.name FROM remax_region3
                JOIN remax_region2
                ON remax_region2.id = remax_region3.region2_id
                WHERE remax_region2.name = '{region2}'
                """
                )
                .name.sort_values(key=remove_accent_from_series)
                .to_list()
            )
            region3.insert(0, "Todos")
            region3 = cols[3].radio("", options=region3)
            if region3 == "Todos":
                region3 = None
    return business_type, listing_type, region1, region2, region3


def show_listing(df):
    st.title("Características do Imóvel")
    selection = int(st.number_input("Seleccione Index para ver Fotos", 0))
    try:
        row = df.iloc[selection]
    except IndexError:
        st.warning("Por favor escolha um index disponível")
        st.stop()
    site_url_prefix = "https://remax.pt/imoveis/a/"
    st.write(f"LINK: {site_url_prefix}{row.id}")
    st.write(
        "Preço: ",
        row.listing_price,
        "Area:",
        row.area,
    )
    cols = st.columns(5)
    cols[0].metric("Preço_m2", row.price_m2)
    pictures = (
        pd_read_sql(
            f"""
    SELECT listing_pictures FROM remax_listings
    WHERE id = '{row.id}'"""
        )
        .loc[0, "listing_pictures"]
        .split(",")
    )
    pictures_url_prefix = "https://i.maxwork.pt/l-view/"
    cols = st.columns(5)
    i = 0
    for picture in pictures:
        cols[i].image(pictures_url_prefix + picture)
        i += 1
        if i == 5:
            i = 0


def filter_price_area(df, color_selection):
    start_price, end_price = st.select_slider(
        "Escolha o preço",
        df.listing_price.sort_values(),
        value=(df.listing_price.min(), df.listing_price.max()),
    )
    start_area, end_area = st.select_slider(
        "Escolha a área", df.area.sort_values(), value=(df.area.min(), df.area.max())
    )
    df = df[
        (df.listing_price >= start_price)
        & (df.listing_price <= end_price)
        & (df.area >= start_area)
        & (df.area <= end_area)
    ]
    special = st.checkbox("Apenas Remax Collection")
    if special:
        df = df[df.is_special]
    return df.reset_index(drop=True)


def main():
    show_last_updated()
    show_variation_per_business_type()
    (
        business_type,
        listing_type,
        region1,
        region2,
        region3,
    ) = get_selection()
    # map_df = get_map_df(business_type, listing_type, region1, region2, region3)
    # if not map_df.empty:
    # map_df = filter_price_area(map_df, color_selection)

    show_plot(business_type, listing_type, region1, region2, region3)
    df = get_map_df(business_type, listing_type, region1, region2, region3)
    show_map(df)
    show_listing(df)


if __name__ == "__main__":
    main()
