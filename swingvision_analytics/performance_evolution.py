"""
Performance Evolution module for SwingVision analytics
Contains functions for tracking performance metrics over time
"""

import streamlit as st
import plotly.graph_objects as go


def create_evolution_chart(match_metrics_df, metric):
    """Create evolution chart for a single metric"""

    if match_metrics_df.empty or not metric or metric not in match_metrics_df.columns:
        return go.Figure()

    # Sort by date
    df_sorted = match_metrics_df.sort_values("match_date")

    fig = go.Figure()

    # Determine win/loss colors using points_won_pct > 0.5
    if "points_won_pct" in df_sorted.columns:
        colors = [
            "green" if pct > 0.5 else "red" for pct in df_sorted["points_won_pct"]
        ]
    else:
        # Fallback to blue if no win/loss data available
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

    # Available metrics
    available_metrics = [
        col
        for col in match_metrics_df.columns
        if col not in ["match_id", "match_date", "opponent", "location"]
    ]

    # Create two columns for side-by-side charts
    col1, col2 = st.columns(2)

    with col1:
        # First metric selector
        selected_metric_1 = st.selectbox(
            "Select first metric:",
            available_metrics,
            index=(
                available_metrics.index("first_serve_speed")
                if "first_serve_speed" in available_metrics
                else 0
            ),
            format_func=lambda x: x.replace("_", " ").title(),
            key="metric_selectbox_1",
        )

        if selected_metric_1:
            evolution_fig_1 = create_evolution_chart(
                match_metrics_df, selected_metric_1
            )
            st.plotly_chart(evolution_fig_1, use_container_width=True, key="chart_1")

    with col2:
        # Second metric selector
        selected_metric_2 = st.selectbox(
            "Select second metric:",
            available_metrics,
            index=(
                available_metrics.index("first_serve_points_won_pct")
                if "first_serve_points_won_pct" in available_metrics
                else 1
            ),
            format_func=lambda x: x.replace("_", " ").title(),
            key="metric_selectbox_2",
        )

        if selected_metric_2:
            evolution_fig_2 = create_evolution_chart(
                match_metrics_df, selected_metric_2
            )
            st.plotly_chart(evolution_fig_2, use_container_width=True, key="chart_2")

    # Detailed metrics table
    st.subheader("Match Metrics Table")
    if not match_metrics_df.empty:
        # Format numeric columns for better display
        formatted_df = match_metrics_df.copy()
        percentage_cols = [col for col in formatted_df.columns if "pct" in col]
        for col in percentage_cols:
            formatted_df[col] = formatted_df[col].map("{:.1%}".format)

        st.dataframe(formatted_df, use_container_width=True)
