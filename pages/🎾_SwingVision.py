import streamlit as st
import pandas as pd
import re
import plotly.graph_objects as go
from db import engine

court_length = 23.77  # meters
court_width = 8.23  # meters
doubles_court_width = 10.97  # meters


@st.cache_data
def get_stored_data():
    return pd.read_sql("SELECT * FROM swing_vision", engine, parse_dates=["date"])


def extract_date_and_description(filename):
    date_pattern = r"\d{4}-\d{2}-\d{2}"
    description_pattern = r"SwingVision-(.*?)-\d{4}-\d{2}-\d{2}"

    date_match = re.search(date_pattern, filename)
    description_match = re.search(description_pattern, filename)

    date = date_match.group(0) if date_match else None
    description = description_match.group(1) if description_match else None
    return date, description


def display_metrics(df):
    total_shots = len(df)
    in_shots = len(df[df["result"] == "In"])
    out_shots = len(df[df["result"] == "Out"])
    net_shots = len(df[df["result"] == "Net"])

    in_percentage = (in_shots / total_shots) * 100
    out_percentage = (out_shots / total_shots) * 100
    net_percentage = (net_shots / total_shots) * 100

    average_speed = df["speed_kmh"].mean()

    st.metric(label="Total Shots", value=total_shots)
    st.metric(label="IN Shots", value=f"{in_shots} ({in_percentage:.2f}%)")
    st.metric(label="OUT Shots", value=f"{out_shots} ({out_percentage:.2f}%)")
    st.metric(label="NET Shots", value=f"{net_shots} ({net_percentage:.2f}%)")
    st.metric(label="Average Speed (km/h)", value=f"{average_speed:.2f} km/h")


def plot_time_series(df):
    df.set_index("date", inplace=True)

    # Define a function to determine well-placed shots
    def well_placed_shots(row):
        near_baseline = (
            abs(row["bounce_y"] - court_length) < 0.3 or abs(row["bounce_y"]) < 0.3
        )
        near_sideline = (
            abs(row["bounce_x"] - court_width / 2) < 0.3
            or abs(row["bounce_x"] + court_width / 2) < 0.3
        )
        return near_baseline or near_sideline

    df["well_placed"] = df.apply(well_placed_shots, axis=1)

    resampled_data = (
        df.resample("W")
        .agg(
            {
                "result": lambda x: (
                    (x == "In").sum() / len(x) * 100 if len(x) > 0 else None
                ),
                "speed_kmh": "mean",
                "spin": lambda x: (
                    (x == "Topspin").sum() / len(x) * 100 if len(x) > 0 else None
                ),
                "well_placed": lambda x: x.sum() / len(x) * 100 if len(x) > 0 else None,
            }
        )
        .rename(
            columns={
                "result": "In Percentage",
                "speed_kmh": "Average Speed",
                "spin": "Topspin Percentage",
                "well_placed": "Well Placed Percentage",
            }
        )
    )

    overall_in_percentage = (df["result"] == "In").sum() / len(df) * 100
    overall_avg_speed = df["speed_kmh"].mean()
    overall_topspin_percentage = (df["spin"] == "Topspin").sum() / len(df) * 100
    overall_well_placed_percentage = df["well_placed"].sum() / len(df) * 100

    fig = go.Figure()

    # Add IN percentage line
    fig.add_trace(
        go.Scatter(
            x=resampled_data.index,
            y=resampled_data["In Percentage"],
            mode="lines+markers",
            name="In Percentage",
            line=dict(color="blue"),
            connectgaps=True,
        )
    )

    # Add average speed line
    fig.add_trace(
        go.Scatter(
            x=resampled_data.index,
            y=resampled_data["Average Speed"],
            mode="lines+markers",
            name="Average Speed",
            line=dict(color="green"),
            connectgaps=True,
        )
    )

    # Add topspin percentage line
    fig.add_trace(
        go.Scatter(
            x=resampled_data.index,
            y=resampled_data["Topspin Percentage"],
            mode="lines+markers",
            name="Topspin Percentage",
            line=dict(color="red"),
            connectgaps=True,
        )
    )

    # Add well placed percentage line
    fig.add_trace(
        go.Scatter(
            x=resampled_data.index,
            y=resampled_data["Well Placed Percentage"],
            mode="lines+markers",
            name="Well Placed Percentage",
            line=dict(color="orange"),
            connectgaps=True,
        )
    )

    # Add overall average lines
    fig.add_shape(
        type="line",
        x0=resampled_data.index.min(),
        y0=overall_in_percentage,
        x1=resampled_data.index.max(),
        y1=overall_in_percentage,
        line=dict(color="blue", width=2, dash="dot"),
        name="Overall In Percentage",
    )

    fig.add_shape(
        type="line",
        x0=resampled_data.index.min(),
        y0=overall_avg_speed,
        x1=resampled_data.index.max(),
        y1=overall_avg_speed,
        line=dict(color="green", width=2, dash="dot"),
        name="Overall Average Speed",
    )

    fig.add_shape(
        type="line",
        x0=resampled_data.index.min(),
        y0=overall_topspin_percentage,
        x1=resampled_data.index.max(),
        y1=overall_topspin_percentage,
        line=dict(color="red", width=2, dash="dot"),
        name="Overall Topspin Percentage",
    )

    fig.add_shape(
        type="line",
        x0=resampled_data.index.min(),
        y0=overall_well_placed_percentage,
        x1=resampled_data.index.max(),
        y1=overall_well_placed_percentage,
        line=dict(color="orange", width=2, dash="dot"),
        name="Overall Well Placed Percentage",
    )

    fig.update_layout(
        title="Shot Metrics Over Time (Weekly)",
        xaxis_title="Date",
        yaxis_title="Percentage / Speed",
        legend=dict(x=0, y=1),
        legend_traceorder="normal",
    )

    st.plotly_chart(fig, use_container_width=True)


def process_df(df):
    df = df[(df["player"] == "Joao Cassis") & (df["stroke"] != "Feed")]
    condition = df["hit_y"] > court_length / 2
    df.loc[condition, "hit_x"] = -df.loc[condition, "hit_x"]
    df.loc[condition, "hit_y"] = court_length - df.loc[condition, "hit_y"]
    df.loc[condition, "bounce_x"] = -df.loc[condition, "bounce_x"]
    df.loc[condition, "bounce_y"] = court_length - df.loc[condition, "bounce_y"]

    net_condition = df["result"] == "Net"
    df.loc[net_condition, "bounce_y"] = court_length / 2

    # Determine direction based on hit_x and bounce_x
    df.loc[
        ((df["hit_x"] < 0) & (df["bounce_x"] < 0))
        | ((df["hit_x"] > 0) & (df["bounce_x"] > 0)),
        "direction",
    ] = "down the line"
    df.loc[
        ((df["hit_x"] < 0) & (df["bounce_x"] > 0))
        | ((df["hit_x"] > 0) & (df["bounce_x"] < 0)),
        "direction",
    ] = "cross court"

    return df


def add_filters(df):
    filter_options = [
        {"label": "Select Session", "column": "description"},
        {"label": "Select Stroke", "column": "stroke"},
        {"label": "Select Spin", "column": "spin"},
        {"label": "Select Hit Zone", "column": "hit_zone"},
        {"label": "Select Direction", "column": "direction"},
    ]

    filters = {}
    columns = st.columns(len(filter_options))

    for i, option in enumerate(filter_options):
        unique_values = ["ALL"] + list(df[option["column"]].unique())
        selected_value = columns[i].selectbox(option["label"], unique_values)
        filters[option["column"]] = selected_value

        if selected_value != "ALL":
            df = df[df[option["column"]] == selected_value]

    return df


def main_page():
    st.title("Swing Vision")
    df = get_stored_data()
    df = process_df(df)
    df = add_filters(df)

    col1, col2 = st.columns([2, 1])

    with col1:
        plot_time_series(df)

    with col2:
        display_metrics(df)


def upload_files():
    df = get_stored_data()
    last_row = df.loc[df["date"].idxmax()]
    st.write("### Latest Event")
    st.write(f"**Date:** {last_row['date'].date()}")
    st.write(f"**Description:** {last_row['description']}")
    df = df.drop(columns=["id"])
    uploaded_files = st.file_uploader(
        "Choose an Excel file", type="xlsx", accept_multiple_files=True
    )
    if uploaded_files:
        new_df = pd.DataFrame()
        for file in uploaded_files:
            date, description = extract_date_and_description(file.name)
            try:
                file_df = pd.read_excel(file, sheet_name="Shots")
            except ValueError:
                st.error("The 'Shots' sheet is not present in the uploaded Excel file.")
            file_df["date"] = pd.to_datetime(date, format="%Y-%m-%d")
            file_df["description"] = description
            new_df = pd.concat([new_df, file_df])
        new_df.columns = df.columns
        new_df["start_time"] = pd.to_datetime(
            new_df["start_time"], format="%H:%M:%S"
        ).dt.time
        df = pd.concat([df, new_df, df])
        df = df.drop_duplicates(keep=False)
        if not df.empty:
            df.to_sql("swing_vision", engine, if_exists="append", index=False)
            get_stored_data.clear()
            st.success("Files Uploaded")
        else:
            st.info("No new data")


option = st.sidebar.radio(
    "Options", ["View Data", "Upload Files"], label_visibility="collapsed"
)

if option == "View Data":
    main_page()
else:
    upload_files()
