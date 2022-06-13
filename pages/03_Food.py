import streamlit as st
from streamlit_folium import st_folium
import folium
from PIL import Image
from io import BytesIO
import psycopg2
from folium.plugins import MarkerCluster
import pandas as pd

st.set_page_config(layout='wide')
proximity_round = 2


@st.experimental_singleton
def init_connection():
    connection = psycopg2.connect(**st.secrets['postgres'])
    connection.autocommit = True
    return connection


connection = init_connection()


def run_query(connection, query, fetch=None):
    with connection.cursor() as cur:
        cur.execute(query)
        connection.commit()
        if fetch:
            return cur.fetchall()


@st.experimental_memo(ttl=6000)
def get_db_data():
    data = run_query(connection, """
            SELECT * from fotos
            WHERE json->>'latitude' is NOT NULL""", 1)
    return data


def get_image_from_byte_array(byte_array):
    byte_object = BytesIO(byte_array)
    img = Image.open(byte_object)
    return img


def main():
    st.header("""
    Vegan Food 🌱 around the World 🗺️
    """)
    data = get_db_data()
    m = folium.Map(
            location=[38.699638, -9.267694],
            zoom_start=3, tiles='cartodbpositron')
    fg = folium.FeatureGroup(name='Marks')
    df = pd.DataFrame()
    for i in data:
        metadata = i[1]
        latitude = round(metadata['latitude'], proximity_round)
        longitude = round(metadata['longitude'], proximity_round)
        country = metadata['place']['address']['country']
        df = pd.concat([df, pd.DataFrame.from_records([{
            'country': country,
            'latitude': latitude,
            'longitude': longitude}])])
    df = df.drop_duplicates()
    fg = folium.FeatureGroup(name='Marks')
    for _, country_df in df.groupby('country'):
        MarkerCluster(country_df[['latitude', 'longitude']].values).add_to(fg)
    m.add_child(fg)
    folium_data = st_folium(m, width=725, key='map')
    cols = st.columns(3)
    try:
        clicked_lat = folium_data['last_object_clicked']['lat']
        clicked_lng = folium_data['last_object_clicked']['lng']
        results = [
                i[0] for i in data if (
                    round(i[1]['latitude'], proximity_round) == clicked_lat and
                    round(i[1]['longitude'], proximity_round) == clicked_lng)]
        i = 0
        url_prefix = 'https://res.cloudinary.com/kassiusklay/'
        for result in results:
            cols[i].image(f'{url_prefix + result}')
            i += 1
            if i == 3:
                i = 0
                cols = st.columns(3)
    except TypeError:
        st.warning('Por favor clique num ponto para ver a imagem')


if __name__ == '__main__':
    main()
