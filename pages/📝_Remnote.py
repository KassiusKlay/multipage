import streamlit as st
import pandas as pd
import re
from sqlalchemy import text
from db import engine

# --- Settings ---
TABLE_NAME = "remnote"


# --- Helper Functions ---
@st.cache_data
def get_stored_data():
    # Filter out ignored records
    return pd.read_sql(
        f"SELECT * FROM {TABLE_NAME} WHERE tag != 'ignore' OR tag IS NULL", engine
    )


def extract_urls_from_markdown(md_content):
    return re.findall(r"!\[.*?\]\((https?://.*?)\)", md_content)


def insert_url_record(url, area, organ, type, tag):
    with engine.begin() as conn:
        conn.execute(
            text(
                f"INSERT INTO {TABLE_NAME} (url, area, organ, type, tag) VALUES (:url, :area, :organ, :type, :tag)"
            ),
            {"url": url, "area": area, "organ": organ, "type": type, "tag": tag},
        )


# --- Sidebar Navigation ---
option = st.sidebar.radio(
    "Options", ["Main Page", "Upload Files"], label_visibility="collapsed"
)

# --- Main Page (Empty for now) ---
if option == "Main Page":
    st.title("Remnote Screenshots")
    df = get_stored_data()

    # Filters
    area_filter = st.selectbox("Filter by Area", ["All"] + sorted(df["area"].unique()))
    organ_filter = st.selectbox(
        "Filter by Organ", ["All"] + sorted(df["organ"].unique())
    )
    type_filter = st.selectbox("Filter by Type", ["All"] + sorted(df["type"].unique()))

    filtered_df = df.copy()
    if area_filter != "All":
        filtered_df = filtered_df[filtered_df["area"] == area_filter]
    if organ_filter != "All":
        filtered_df = filtered_df[filtered_df["organ"] == organ_filter]
    if type_filter != "All":
        filtered_df = filtered_df[filtered_df["type"] == type_filter]

    st.write(f"Showing {len(filtered_df)} images:")

    for _, row in filtered_df.iterrows():
        st.image(row["url"], )
        st.caption(
            f"Area: {row['area']} | Organ: {row['organ']} | Type: {row['type']} | Tag: {row['tag'] or '—'}"
        )

# --- Upload Files Page ---
elif option == "Upload Files":
    st.title("Upload Remnote Markdown Files")

    # Upload .md files
    uploaded_files = st.file_uploader(
        "Upload Markdown Files", type="md", accept_multiple_files=True
    )

    # Reset index and clear cache if files removed
    if not uploaded_files:
        st.cache_data.clear()
        st.session_state.index = 0
        st.session_state.last_upload_hash = None

    if uploaded_files:
        # Load existing URLs from database (including ignored ones to avoid duplicates)
        stored_df = pd.read_sql(f"SELECT * FROM {TABLE_NAME}", engine)
        existing_urls = set(stored_df["url"].tolist())

        new_urls = []
        for file in uploaded_files:
            content = file.read().decode("utf-8")
            urls = extract_urls_from_markdown(content)
            for url in urls:
                if url not in existing_urls:
                    new_urls.append(url)

        # Remove duplicates
        new_urls = list(set(new_urls))

        st.success(f"Found {len(new_urls)} new image URLs not in the database.")

        # Reset index when file content changes
        current_hash = hash("".join(new_urls))
        if (
            "last_upload_hash" not in st.session_state
            or st.session_state.last_upload_hash != current_hash
        ):
            st.session_state.index = 0
            st.session_state.last_upload_hash = current_hash

        if new_urls:
            if st.session_state.index >= len(new_urls):
                st.success("All new URLs processed.")
                st.stop()

            st.write("New URLs:")
            url = new_urls[st.session_state.index]
            st.image(url, )
            st.markdown(f"**URL:** {url}")

            area = st.selectbox("Area", ["GastroIntestinal", "Urology"])
            organ_options = {
                "GastroIntestinal": [
                    "Esophagus",
                    "Stomach",
                    "Small Bowel",
                    "Large Bowel",
                    "Appendix",
                    "Other",
                ],
                "Urology": ["Kidney", "Urothelial", "Prostate", "Testis", "Other"],
            }
            organ = st.selectbox("Organ", organ_options[area])

            type = st.selectbox("Type", ["Slide", "Table", "Photo", "Other"])
            tag = st.text_input("Tag (optional)")

            col1, col2 = st.columns([1, 1])

            with col1:
                if st.button("Confirm"):
                    insert_url_record(url, area, organ, type, tag if tag else None)
                    st.session_state.index += 1
                    st.rerun()
            with col2:
                if st.button("Ignore"):
                    # Store with "ignore" tag, using placeholder values for required fields
                    insert_url_record(url, "Ignored", "Ignored", "Ignored", "ignore")
                    st.session_state.index += 1
                    st.rerun()
