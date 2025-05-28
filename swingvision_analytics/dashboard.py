"""
Dashboard module for SwingVision analytics
Contains functions for creating performance dashboards and key metrics
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def create_key_metrics_cards(match_metrics_df):
    """Create key performance metric cards"""
    if match_metrics_df.empty:
        return

    # Calculate overall averages
    avg_metrics = match_metrics_df.select_dtypes(include=["float64", "int64"]).mean()

    # Create columns for metrics cards
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Overall Win Rate",
            value=f"{avg_metrics.get('points_won_pct', 0):.1%}",
            delta=None,
        )

    with col2:
        st.metric(
            label="First Serve %",
            value=f"{avg_metrics.get('first_serve_pct', 0):.1%}",
            delta=None,
        )

    with col3:
        st.metric(
            label="Winner/Error Ratio",
            value=f"{avg_metrics.get('winner_error_ratio', 0):.2f}",
            delta=None,
        )

    with col4:
        st.metric(
            label="Break Point Conversion",
            value=f"{avg_metrics.get('break_points_won_pct', 0):.1%}",
            delta=None,
        )


def create_performance_dashboard(match_metrics_df):
    """Create a comprehensive performance dashboard"""
    if match_metrics_df.empty:
        return go.Figure()

    # Calculate averages
    avg_metrics = match_metrics_df.select_dtypes(include=["float64", "int64"]).mean()

    # Create subplots
    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=(
            "Serve Performance (%)",
            "Return Performance (%)",
            "Winners vs Errors (Count)",
            "Break Point Performance (%)",
        ),
        specs=[
            [{"secondary_y": False}, {"secondary_y": False}],
            [{"secondary_y": False}, {"secondary_y": False}],
        ],
    )

    # Serve Performance - Fixed x-axis labels
    fig.add_trace(
        go.Bar(
            name="First Serve %",
            x=["1st Serve", "2nd Serve"],
            y=[
                avg_metrics.get("first_serve_pct", 0) * 100,
                avg_metrics.get("second_serve_pct", 0) * 100,
            ],
            showlegend=False,
            hovertemplate="<b>%{x}</b><br>Percentage: %{y:.1f}%<extra></extra>",
        ),
        row=1,
        col=1,
    )

    # Return Performance - Fixed x-axis labels
    fig.add_trace(
        go.Bar(
            name="Return Won %",
            x=["1st Return", "2nd Return"],
            y=[
                avg_metrics.get("first_return_won_pct", 0) * 100,
                avg_metrics.get("second_return_won_pct", 0) * 100,
            ],
            showlegend=False,
            hovertemplate="<b>%{x}</b><br>Win Rate: %{y:.1f}%<extra></extra>",
        ),
        row=1,
        col=2,
    )

    # Winners vs Errors
    fig.add_trace(
        go.Bar(
            name="Winners",
            x=["Forehand", "Backhand"],
            y=[
                avg_metrics.get("forehand_winners", 0),
                avg_metrics.get("backhand_winners", 0),
            ],
            showlegend=False,
            hovertemplate="<b>%{x} Winners</b><br>Count: %{y:.0f}<extra></extra>",
        ),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            name="Errors",
            x=["Forehand", "Backhand"],
            y=[
                avg_metrics.get("forehand_errors", 0),
                avg_metrics.get("backhand_errors", 0),
            ],
            showlegend=False,
            opacity=0.7,
            hovertemplate="<b>%{x} Errors</b><br>Count: %{y:.0f}<extra></extra>",
        ),
        row=2,
        col=1,
    )

    # Break Points
    fig.add_trace(
        go.Bar(
            name="Break Points",
            x=["BP Won", "BP Saved"],
            y=[
                avg_metrics.get("break_points_won_pct", 0) * 100,
                avg_metrics.get("break_points_saved_pct", 0) * 100,
            ],
            showlegend=False,
            hovertemplate="<b>%{x}</b><br>Percentage: %{y:.1f}%<extra></extra>",
        ),
        row=2,
        col=2,
    )

    # Update layout - let Streamlit theme handle colors
    fig.update_layout(
        height=600,
        title_text="Performance Dashboard",
        showlegend=False,
    )

    return fig


def create_match_comparison_chart(match_metrics_df):
    """Create a chart comparing performance across different opponents"""
    if match_metrics_df.empty:
        return go.Figure()

    # Group by opponent and calculate averages
    opponent_stats = (
        match_metrics_df.groupby("opponent")
        .agg(
            {
                "points_won_pct": "mean",
                "first_serve_pct": "mean",
                "winners": "mean",
                "unforced_errors": "mean",
                "break_points_won_pct": "mean",
            }
        )
        .reset_index()
    )

    fig = go.Figure()

    # Add traces for different metrics - let Streamlit theme handle colors
    fig.add_trace(
        go.Scatter(
            x=opponent_stats["opponent"],
            y=opponent_stats["points_won_pct"] * 100,
            mode="markers+lines",
            name="Points Won %",
            marker=dict(size=12),
            line=dict(width=3),
            hovertemplate="<b>%{x}</b><br>Points Won: %{y:.1f}%<extra></extra>",
        )
    )

    fig.update_layout(
        title="Performance vs Different Opponents",
        xaxis_title="Opponent",
        yaxis_title="Points Won %",
        height=400,
    )

    return fig


def render_dashboard_tab(matches, points, shots, match_metrics_df):
    """Render the main dashboard tab"""
    st.header("Performance Dashboard")

    # Key metrics cards
    create_key_metrics_cards(match_metrics_df)

    # Performance dashboard
    dashboard_fig = create_performance_dashboard(match_metrics_df)
    st.plotly_chart(dashboard_fig, use_container_width=True, theme="streamlit")

    # Match comparison
    comparison_fig = create_match_comparison_chart(match_metrics_df)
    st.plotly_chart(comparison_fig, use_container_width=True, theme="streamlit")

    # Recent matches summary
    st.subheader("Recent Matches")
    if not match_metrics_df.empty:
        recent_matches = match_metrics_df.sort_values(
            "match_date", ascending=False
        ).head(5)
        display_columns = [
            "match_date",
            "opponent",
            "points_won_pct",
            "winners",
            "unforced_errors",
            "aces",
        ]
        st.dataframe(
            recent_matches[display_columns].style.format(
                {
                    "points_won_pct": "{:.1%}",
                    "winners": "{:.0f}",
                    "unforced_errors": "{:.0f}",
                    "aces": "{:.0f}",
                }
            ),
            use_container_width=True,
        )
