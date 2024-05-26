import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import re
import plotly.graph_objects as go

st.set_page_config(layout="wide")

court_length = 23.77  # meters
court_width = 8.23  # meters
doubles_court_width = 10.97  # meters


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


def draw_tennis_court(df):
    fig = go.Figure()

    # Add the court lines
    fig.add_shape(
        type="rect",
        x0=-court_width / 2,
        y0=0,
        x1=court_width / 2,
        y1=court_length,
        line=dict(color="green", width=3),
    )
    fig.add_shape(
        type="rect",
        x0=-doubles_court_width / 2,
        y0=0,
        x1=doubles_court_width / 2,
        y1=court_length,
        line=dict(color="red", width=3),
    )
    fig.add_shape(
        type="rect",
        x0=-court_width / 2,
        y0=court_length / 2,
        x1=court_width / 2,
        y1=court_length / 2 + 6.4,
        line=dict(color="blue", width=3),
    )
    fig.add_shape(
        type="rect",
        x0=-court_width / 2,
        y0=court_length / 2 - 6.4,
        x1=court_width / 2,
        y1=court_length / 2,
        line=dict(color="blue", width=3),
    )
    fig.add_shape(
        type="line",
        x0=0,
        y0=court_length / 2 - 6.4,
        x1=0,
        y1=court_length / 2 + 6.4,
        line=dict(color="blue", width=3),
    )
    fig.add_shape(
        type="line",
        x0=-doubles_court_width / 2,
        y0=court_length / 2,
        x1=doubles_court_width / 2,
        y1=court_length / 2,
        line=dict(color="black", width=3),
    )

    # Plot the bounces and hits
    fig.add_trace(
        go.Scatter(
            x=df[df["result"] == "In"]["bounce_x"],
            y=df[df["result"] == "In"]["bounce_y"],
            mode="markers",
            name="Bounce In",
            marker=dict(color="blue", size=6),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df[df["result"] == "Out"]["bounce_x"],
            y=df[df["result"] == "Out"]["bounce_y"],
            mode="markers",
            name="Bounce Out",
            marker=dict(color="red", size=6),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df[df["result"] == "Net"]["bounce_x"],
            y=df[df["result"] == "Net"]["bounce_y"],
            mode="markers",
            name="Bounce Net",
            marker=dict(color="purple", size=6, symbol="x"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df[df["result"] == "In"]["hit_x"],
            y=df[df["result"] == "In"]["hit_y"],
            mode="markers",
            name="Hit In",
            marker=dict(color="green", size=6),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df[df["result"] == "Out"]["hit_x"],
            y=df[df["result"] == "Out"]["hit_y"],
            mode="markers",
            name="Hit Out",
            marker=dict(color="white", size=6, line=dict(color="green", width=2)),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df[df["result"] == "Net"]["hit_x"],
            y=df[df["result"] == "Net"]["hit_y"],
            mode="markers",
            name="Hit Net",
            marker=dict(color="purple", size=6),
        )
    )

    # Set the layout
    fig.update_layout(
        xaxis=dict(
            range=[-doubles_court_width / 2 - 1, doubles_court_width / 2 + 1],
            showgrid=False,
            zeroline=False,
            visible=False,
            scaleanchor="y",
            scaleratio=1.3,
        ),
        yaxis=dict(
            range=[-3, court_length + 3], showgrid=False, zeroline=False, visible=False
        ),
        plot_bgcolor="white",
        margin=dict(l=0, r=0, t=0, b=0),
    )

    st.plotly_chart(fig)


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

    resampled_data = (
        df.resample("W")
        .agg(
            {
                "result": lambda x: (x == "In").sum() / len(x) * 100
                if len(x) > 0
                else None,
                "speed_kmh": "mean",
            }
        )
        .rename(columns={"result": "In Percentage", "speed_kmh": "Average Speed"})
    )

    overall_in_percentage = (df["result"] == "In").sum() / len(df) * 100
    overall_avg_speed = df["speed_kmh"].mean()

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

    fig.update_layout(
        title="Shot Metrics Over Time (Weekly)",
        xaxis_title="Date",
        yaxis_title="Percentage / Speed",
        legend=dict(x=0, y=1),
        legend_traceorder="normal",
    )

    st.plotly_chart(fig)


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
        {"label": "Select Stroke", "column": "stroke"},
        {"label": "Select Spin", "column": "spin"},
        {"label": "Select Hit Zone", "column": "hit_zone"},
        {"label": "Select Direction", "column": "direction"},
        {"label": "Select Session", "column": "description"},
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

    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        draw_tennis_court(df)

    with col2:
        plot_time_series(df)

    with col3:
        display_metrics(df)


def upload_files():
    df = get_stored_data()
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
            file_df["date"] = pd.to_datetime(date, dayfirst=True)
            file_df["description"] = description
            new_df = pd.concat([new_df, file_df])
        new_df.columns = df.columns
        new_df["start_time"] = pd.to_datetime(new_df["start_time"]).dt.time
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
