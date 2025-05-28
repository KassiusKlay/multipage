"""
Upload Files module for SwingVision analytics
Contains functions for file upload and data processing
"""

import streamlit as st
import pandas as pd
import uuid
from db import engine


def get_stored_match_ids():
    return pd.read_sql("SELECT match_id FROM swingvision_matches", engine)[
        "match_id"
    ].tolist()


def normalize_points(df):
    return df.rename(
        columns={
            "Point": "point",
            "Game": "game",
            "Set": "set",
            "Serve State": "serve_state",
            "Match Server": "match_server",
            "Host Game Score": "host_game_score",
            "Guest Game Score": "guest_game_score",
            "Point Winner": "point_winner",
            "Detail": "detail",
            "Break Point": "break_point",
            "Set Point": "set_point",
            "Favorited": "favorited",
            "Start Time": "start_time",
            "Video Time": "video_time",
            "Duration": "duration",
        }
    )


def normalize_shots(df):
    return df.rename(
        columns={
            "Player": "player",
            "Shot": "shot",
            "Type": "type",
            "Stroke": "stroke",
            "Spin": "spin",
            "Speed (KM/H)": "speed",
            "Point": "point",
            "Game": "game",
            "Set": "set",
            "Bounce Depth": "bounce_depth",
            "Bounce Zone": "bounce_zone",
            "Bounce Side": "bounce_side",
            "Bounce (x)": "bounce_x",
            "Bounce (y)": "bounce_y",
            "Hit Depth": "hit_depth",
            "Hit Zone": "hit_zone",
            "Hit Side": "hit_side",
            "Hit (x)": "hit_x",
            "Hit (y)": "hit_y",
            "Hit (z)": "hit_z",
            "Direction": "direction",
            "Result": "result",
            "Favorited": "favorited",
            "Start Time": "start_time",
            "Video Time": "video_time",
        }
    )


def extract_match_metadata(settings_df, filename=None):
    try:
        # Get raw values exactly as they appear in Excel
        start_time_raw = settings_df.loc[0, "Start Time"]
        location_raw = settings_df.loc[0, "Location"]
        host_raw = settings_df.loc[0, "Host Team"]
        guest_raw = settings_df.loc[0, "Guest Team"]

        # Parse start_time
        start_time = pd.to_datetime(start_time_raw)

        # Convert everything to strings and normalize
        location = str(location_raw).strip() if pd.notna(location_raw) else ""
        host = str(host_raw).strip() if pd.notna(host_raw) else ""
        guest = str(guest_raw).strip() if pd.notna(guest_raw) else ""

        # Extract match date from filename
        match_date = None
        if filename:
            import re

            date_pattern = r"(\d{4}-\d{2}-\d{2})"
            match = re.search(date_pattern, filename)
            if match:
                match_date = pd.to_datetime(match.group(1)).date()

        # Create UUID using a hash-based approach for maximum determinism
        import hashlib

        # Use epoch timestamp to avoid datetime formatting issues
        timestamp_str = str(int(start_time.timestamp()))

        # Create a very explicit, structured string
        data_string = f"ST:{timestamp_str}|LOC:{location}|HOST:{host}|GUEST:{guest}"

        # Use MD5 hash to create a consistent 16-byte value
        hash_object = hashlib.md5(data_string.encode("utf-8"))
        hash_bytes = hash_object.digest()

        # Create UUID from the hash bytes
        match_id = uuid.UUID(bytes=hash_bytes)

        return match_id, start_time, location, host, guest, match_date

    except Exception as e:
        print(f"Error extracting metadata: {e}")
        import traceback

        traceback.print_exc()
        return None


def upload_files():
    existing_ids = get_stored_match_ids()
    uploaded_files = st.file_uploader(
        "Upload SwingVision Excel files", type="xlsx", accept_multiple_files=True
    )

    if uploaded_files:
        progress_bar = st.progress(0)
        for i, file in enumerate(uploaded_files):
            progress_bar.progress((i + 1) / len(uploaded_files))

            xls = pd.ExcelFile(file)
            settings = xls.parse("Settings")
            result = extract_match_metadata(settings, file.name)
            if result is None:
                st.error(f"Failed to extract metadata from {file.name}")
                continue

            match_id, start_time, location, host, guest, match_date = result

            # Debug info to help identify duplicate detection issues
            if st.checkbox("Show debug info", key=f"debug_{i}"):
                st.write(f"**File:** {file.name}")
                st.write(f"**Match ID:** {match_id}")
                st.write(f"**Start Time:** {start_time}")
                st.write(f"**Location:** {location}")
                st.write(f"**Host:** {host}")
                st.write(f"**Guest:** {guest}")
                st.write(
                    f"**UUID String:** {start_time.strftime('%Y-%m-%d %H:%M:%S')}|{location}|{host}|{guest}"
                )
                st.write(f"**Already exists:** {match_id in existing_ids}")

            if match_id in existing_ids:
                st.info(f"Match already uploaded: {file.name}")
                continue

            points_df = normalize_points(xls.parse("Points"))
            shots_df = normalize_shots(xls.parse("Shots"))

            points_df["match_id"] = match_id
            shots_df["match_id"] = match_id

            match_row = pd.DataFrame(
                [
                    {
                        "match_id": match_id,
                        "start_time": start_time,
                        "location": location,
                        "host_team": host,
                        "guest_team": guest,
                        "match_date": match_date,
                    }
                ]
            )

            match_row.to_sql(
                "swingvision_matches",
                engine,
                if_exists="append",
                index=False,
            )

            points_df.to_sql(
                "swingvision_points",
                engine,
                if_exists="append",
                index=False,
            )

            shots_df.to_sql(
                "swingvision_shots",
                engine,
                if_exists="append",
                index=False,
            )
            st.success(f"Uploaded match: {file.name}")
        st.cache_data.clear()


def render_upload_files_tab():
    """Render the upload files tab"""
    st.title("📤 Upload SwingVision Files")
    upload_files()
