import streamlit as st
from streamlit_folium import st_folium
import folium
from PIL import Image
from io import BytesIO
from folium.plugins import MarkerCluster
import pandas as pd
from db import engine

proximity_round = 2


@st.cache_data(ttl=600)
def get_db_data():
    return pd.read_sql(
        """
    SELECT * from fotos
    WHERE json->>'latitude' is NOT NULL""",
        engine,
    )


def get_image_from_byte_array(byte_array):
    byte_object = BytesIO(byte_array)
    img = Image.open(byte_object)
    return img


def main():
    st.header(
        """
    Vegan Food 🌱 around the World 🗺️
    """
    )
    data = get_db_data()
    df = pd.DataFrame()
    for i in data.json:
        latitude = round(i["latitude"], proximity_round)
        longitude = round(i["longitude"], proximity_round)
        country = i["place"]["address"]["country"]
        df = pd.concat(
            [
                df,
                pd.DataFrame.from_records(
                    [{"country": country, "latitude": latitude, "longitude": longitude}]
                ),
            ]
        )
    df = df.drop_duplicates()

    m = folium.Map(
        location=[38.699638, -9.267694], zoom_start=3, tiles="cartodbpositron"
    )
    fg = folium.FeatureGroup(name="Marks")
    for _, country_df in df.groupby("country"):
        MarkerCluster(country_df[["latitude", "longitude"]].values).add_to(fg)
    m.add_child(fg)
    folium_data = st_folium(m, width=725, key="map")

    cols = st.columns(3)
    try:
        clicked_lat = folium_data["last_object_clicked"]["lat"]
        clicked_lng = folium_data["last_object_clicked"]["lng"]
        results = [
            row.id
            for _, row in data.iterrows()
            if round(row.json["latitude"], proximity_round) == clicked_lat
            and round(row.json["longitude"], proximity_round) == clicked_lng
        ]
        i = 0
        url_prefix = "https://res.cloudinary.com/kassiusklay/"
        for result in results:
            cols[i].image(f"{url_prefix + result}")
            i += 1
            if i == 3:
                i = 0
                cols = st.columns(3)
    except TypeError:
        st.warning("Por favor clique num ponto para ver a imagem")


if __name__ == "__main__":
    main()
