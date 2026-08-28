"""
Performance Evolution module for SwingVision analytics
Contains functions for tracking performance metrics over time
"""

import streamlit as st
import plotly.graph_objects as go

# Timeline-friendly metrics only (exclude ids, labels, blank-detail bookkeeping)
EVOLUTION_METRIC_CANDIDATES = [
    "points_won_pct",
    "first_serve_pct",
    "first_serve_won_pct",
    "second_serve_pct",
    "second_serve_won_pct",
    "first_serve_speed",
    "second_serve_speed",
    "forehand_avg_speed",
    "backhand_avg_speed",
    "first_return_won_pct",
    "second_return_won_pct",
    "first_return_speed",
    "second_return_speed",
    "winners",
    "forehand_winners",
    "backhand_winners",
    "unforced_errors",
    "forehand_errors",
    "backhand_errors",
    "double_faults",
    "aces",
    "service_winners",
    "winner_error_ratio",
    "forehand_winner_error_ratio",
    "backhand_winner_error_ratio",
    "break_points_won_pct",
    "break_points_saved_pct",
    "service_games_won_pct",
    "return_games_won_pct",
    "opponent_unforced_errors",
]


def evolution_metrics(match_metrics_df):
    return [m for m in EVOLUTION_METRIC_CANDIDATES if m in match_metrics_df.columns]


def create_evolution_chart(match_metrics_df, metric):
    """Create evolution chart for a single metric"""

    if match_metrics_df.empty or not metric or metric not in match_metrics_df.columns:
        return go.Figure()

    df_sorted = match_metrics_df.sort_values("match_date")

    fig = go.Figure()

    if "match_won" in df_sorted.columns:
        colors = []
        for won in df_sorted["match_won"]:
            if won is True:
                colors.append("green")
            elif won is False:
                colors.append("red")
            else:
                colors.append("gray")
    elif "points_won_pct" in df_sorted.columns:
        colors = [
            "green" if pct > 0.5 else "red" for pct in df_sorted["points_won_pct"]
        ]
    else:
        colors = ["blue"] * len(df_sorted)

    fig.add_trace(
        go.Scatter(
            x=df_sorted["match_date"],
            y=df_sorted[metric],
            mode="lines+markers",
            name=metric.replace("_", " ").title(),
            marker=dict(color=colors, size=8, line=dict(width=1, color="white")),
            hovertemplate=f'<b>{metric.replace("_", " ").title()}</b><br>'
            + "Opponent: %{customdata}<br>"
            + "Value: %{y:.2f}<br>"
            + "<extra></extra>",
            customdata=(
                df_sorted["opponent"]
                if "opponent" in df_sorted.columns
                else ["Unknown"] * len(df_sorted)
            ),
        )
    )

    fig.update_layout(
        title=metric.replace("_", " ").title(),
        xaxis_title="Match Date",
        yaxis_title="Value",
        hovermode="x unified",
        height=400,
        showlegend=False,
    )

    return fig


def render_performance_evolution_tab(matches, points, shots, match_metrics_df):
    """Render the performance evolution tab"""
    st.header("📈 Performance Evolution")

    available_metrics = evolution_metrics(match_metrics_df)
    if not available_metrics:
        st.warning("No plottable metrics available.")
        return

    def _default_index(name, fallback=0):
        return available_metrics.index(name) if name in available_metrics else fallback

    col1, col2 = st.columns(2)

    with col1:
        selected_metric_1 = st.selectbox(
            "Select first metric:",
            available_metrics,
            index=_default_index("forehand_avg_speed", 0),
            format_func=lambda x: x.replace("_", " ").title(),
            key="metric_selectbox_1",
        )
        if selected_metric_1:
            st.plotly_chart(
                create_evolution_chart(match_metrics_df, selected_metric_1),
                width="stretch",
                key="chart_1",
            )

    with col2:
        selected_metric_2 = st.selectbox(
            "Select second metric:",
            available_metrics,
            index=_default_index("backhand_avg_speed", min(1, len(available_metrics) - 1)),
            format_func=lambda x: x.replace("_", " ").title(),
            key="metric_selectbox_2",
        )
        if selected_metric_2:
            st.plotly_chart(
                create_evolution_chart(match_metrics_df, selected_metric_2),
                width="stretch",
                key="chart_2",
            )

    st.subheader("Match Metrics Table")
    if not match_metrics_df.empty:
        show_cols = [
            c
            for c in ["match_date", "opponent", "scoreline", "match_won"]
            + available_metrics
            if c in match_metrics_df.columns
        ]
        formatted_df = match_metrics_df[show_cols].copy()
        percentage_cols = [col for col in formatted_df.columns if "pct" in col]
        for col in percentage_cols:
            formatted_df[col] = formatted_df[col].map("{:.1%}".format)
        st.dataframe(formatted_df, width="stretch")
