"""
Performance Evolution module for SwingVision analytics
Contains functions for tracking performance metrics over time
"""

import streamlit as st
import plotly.graph_objects as go


def create_evolution_chart(match_metrics_df, selected_metrics):
    """Create evolution chart for selected metrics"""

    if match_metrics_df.empty or not selected_metrics:
        return go.Figure()

    # Sort by date
    df_sorted = match_metrics_df.sort_values("match_date")

    fig = go.Figure()

    # Add a trace for each selected metric
    for metric in selected_metrics:
        if metric in df_sorted.columns:
            fig.add_trace(
                go.Scatter(
                    x=df_sorted["match_date"],
                    y=df_sorted[metric],
                    mode="lines+markers",
                    name=metric.replace("_", " ").title(),
                    hovertemplate=f'<b>{metric.replace("_", " ").title()}</b><br>'
                    + "Date: %{x}<br>"
                    + "Value: %{y:.2f}<br>"
                    + "<extra></extra>",
                )
            )

    fig.update_layout(
        title="Tennis Performance Evolution Over Time",
        xaxis_title="Match Date",
        yaxis_title="Value",
        hovermode="x unified",
        height=500,
    )

    return fig


def render_performance_evolution_tab(matches, points, shots, match_metrics_df):
    """Render the performance evolution tab"""
    st.header("📈 Performance Evolution")

    # Metric selection
    available_metrics = [
        col
        for col in match_metrics_df.columns
        if col not in ["match_id", "match_date", "opponent", "location"]
    ]

    selected_metrics = st.multiselect(
        "Select metrics to display:",
        available_metrics,
        default=["first_serve_pct", "winners", "unforced_errors", "points_won_pct"],
        format_func=lambda x: x.replace("_", " ").title(),
    )

    if selected_metrics:
        evolution_fig = create_evolution_chart(match_metrics_df, selected_metrics)
        st.plotly_chart(evolution_fig, use_container_width=True)

    # Detailed metrics table
    st.subheader("Match Metrics Table")
    if not match_metrics_df.empty:
        # Format numeric columns for better display
        formatted_df = match_metrics_df.copy()
        percentage_cols = [col for col in formatted_df.columns if "pct" in col]
        for col in percentage_cols:
            formatted_df[col] = formatted_df[col].map("{:.1%}".format)

        st.dataframe(formatted_df, use_container_width=True)
