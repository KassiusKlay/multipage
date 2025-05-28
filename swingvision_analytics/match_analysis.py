"""
Match Metrics module for SwingVision analytics
Contains functions for analyzing match-level performance metrics
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

HOST = "Joao Cassis"


@st.cache_data
def calculate_match_analytics(matches, points, shots):
    """Calculate analytical metrics for performance insights"""

    analytics_data = []

    for _, match in matches.iterrows():
        match_id = match["match_id"]
        match_points = points[points["match_id"] == match_id]
        match_shots = shots[shots["match_id"] == match_id]
        my_shots = match_shots[match_shots["player"] == HOST]

        if len(match_points) == 0:
            continue

        # Basic match outcome
        total_points = len(match_points)
        points_won = len(match_points[match_points["point_winner"] == HOST])
        points_won_pct = points_won / total_points
        match_won = points_won_pct > 0.5

        # === NET POINTS CALCULATION ===
        # Positive shots (points I create)
        my_winner_points = match_points[match_points["point_winner"] == HOST]
        my_forehand_winners = len(
            my_winner_points[my_winner_points["detail"] == "Forehand Winner"]
        )
        my_backhand_winners = len(
            my_winner_points[my_winner_points["detail"] == "Backhand Winner"]
        )
        my_winners = my_forehand_winners + my_backhand_winners

        # Opponent errors that gave me points
        opponent_unforced_errors = len(
            my_winner_points[
                my_winner_points["detail"].isin(
                    [
                        "Forehand Unforced Error",
                        "Backhand Unforced Error",
                        "Double Fault",
                    ]
                )
            ]
        )

        positive_shots = my_winners + opponent_unforced_errors

        # Negative shots (points I give away)
        opponent_winner_points = match_points[match_points["point_winner"] != HOST]
        my_unforced_errors = len(
            opponent_winner_points[
                opponent_winner_points["detail"].isin(
                    ["Forehand Unforced Error", "Backhand Unforced Error"]
                )
            ]
        )
        my_double_faults = len(
            opponent_winner_points[opponent_winner_points["detail"] == "Double Fault"]
        )

        negative_shots = my_unforced_errors + my_double_faults

        # NET POINTS = Positive - Negative
        net_points = positive_shots - negative_shots

        # === OTHER ANALYTICAL METRICS ===
        # Winner/Error Ratio
        winner_error_ratio = (
            my_winners / my_unforced_errors
            if my_unforced_errors > 0
            else (999 if my_winners > 0 else 0)
        )

        # Service Winners (including aces)
        my_aces = len(my_winner_points[my_winner_points["detail"] == "Ace"])
        my_service_winners = len(
            my_winner_points[my_winner_points["detail"] == "Service Winner"]
        )
        total_service_winners = my_aces + my_service_winners

        # Break Point Conversion
        break_point_opportunities = len(
            match_points[
                (match_points["match_server"] != HOST) & (match_points["break_point"])
            ]
        )
        break_points_won = len(
            match_points[
                (match_points["match_server"] != HOST)
                & (match_points["break_point"])
                & (match_points["point_winner"] == HOST)
            ]
        )
        break_point_conversion = (
            break_points_won / break_point_opportunities
            if break_point_opportunities > 0
            else 0
        )

        # Return Points Won
        return_points = match_points[match_points["match_server"] != HOST]
        return_points_won = len(return_points[return_points["point_winner"] == HOST])
        return_points_won_pct = (
            return_points_won / len(return_points) if len(return_points) > 0 else 0
        )

        # First Serve Percentage
        serve_points = match_points[match_points["match_server"] == HOST]
        my_first_serves = my_shots[my_shots["type"] == "first_serve"]
        first_serves_in = len(my_first_serves[my_first_serves["result"] == "In"])
        first_serve_pct = (
            first_serves_in / len(serve_points) if len(serve_points) > 0 else 0
        )

        analytics_data.append(
            {
                "match_id": match_id,
                "match_date": match["match_date"],
                "opponent": match["guest_team"],
                "location": match["location"],
                "match_won": match_won,
                "points_won_pct": points_won_pct,
                # Net Points breakdown
                "net_points": net_points,
                "positive_shots": positive_shots,
                "negative_shots": negative_shots,
                "my_winners": my_winners,
                "opponent_errors": opponent_unforced_errors,
                "my_unforced_errors": my_unforced_errors,
                "my_double_faults": my_double_faults,
                # Other analytical metrics
                "winner_error_ratio": winner_error_ratio,
                "service_winners": total_service_winners,
                "break_point_conversion": break_point_conversion,
                "return_points_won_pct": return_points_won_pct,
                "first_serve_pct": first_serve_pct,
            }
        )

    return pd.DataFrame(analytics_data)


def create_net_points_breakdown_chart(analytics_df):
    """Create a detailed Net Points breakdown chart"""

    if analytics_df.empty:
        return go.Figure()

    # Sort by date
    df_sorted = analytics_df.sort_values("match_date")

    fig = make_subplots(
        rows=2,
        cols=1,
        subplot_titles=("Net Points by Match", "Net Points Components"),
        specs=[[{"secondary_y": False}], [{"secondary_y": False}]],
        vertical_spacing=0.15,
    )

    # Top chart: Net Points line with win/loss colors
    colors = ["green" if won else "red" for won in df_sorted["match_won"]]

    fig.add_trace(
        go.Scatter(
            x=df_sorted["match_date"],
            y=df_sorted["net_points"],
            mode="markers+lines",
            name="Net Points",
            marker=dict(color=colors, size=12),
            hovertemplate="Date: %{x}<br>Net Points: %{y}<br>Result: %{customdata}<extra></extra>",
            customdata=["WON" if won else "LOST" for won in df_sorted["match_won"]],
        ),
        row=1,
        col=1,
    )

    # Add horizontal line at 0
    fig.add_hline(y=0, line_dash="dash", line_color="gray", row=1, col=1)

    # Bottom chart: Stacked bar showing positive vs negative shots
    fig.add_trace(
        go.Bar(
            x=df_sorted["match_date"],
            y=df_sorted["positive_shots"],
            name="Positive Shots",
            hovertemplate="Positive: %{y}<extra></extra>",
        ),
        row=2,
        col=1,
    )

    fig.add_trace(
        go.Bar(
            x=df_sorted["match_date"],
            y=-df_sorted["negative_shots"],  # Negative for visual effect
            name="Negative Shots",
            hovertemplate="Negative: %{y}<extra></extra>",
        ),
        row=2,
        col=1,
    )

    # Add horizontal line at 0 for bottom chart
    fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)

    fig.update_layout(
        height=700,
        title_text="Net Points Analysis - Your Shot Impact Over Time",
        showlegend=True,
    )

    fig.update_xaxes(title_text="Match Date", row=2, col=1)
    fig.update_yaxes(title_text="Net Points", row=1, col=1)
    fig.update_yaxes(title_text="Shots Count", row=2, col=1)

    return fig


def create_performance_comparison_dashboard(analytics_df):
    """Create dashboard comparing won vs lost matches"""

    if analytics_df.empty:
        return go.Figure()

    # Calculate averages for won vs lost matches
    won_matches = analytics_df[analytics_df["match_won"]]
    lost_matches = analytics_df[~analytics_df["match_won"]]

    metrics = [
        "net_points",
        "winner_error_ratio",
        "service_winners",
        "break_point_conversion",
        "return_points_won_pct",
    ]

    won_avgs = [won_matches[metric].mean() for metric in metrics]
    lost_avgs = [lost_matches[metric].mean() for metric in metrics]

    # Format metric names
    metric_names = [
        "Net Points",
        "Winner/Error Ratio",
        "Service Winners",
        "Break Point Conv.",
        "Return Points Won",
    ]

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            name="Won Matches",
            x=metric_names,
            y=won_avgs,
            text=[f"{val:.1f}" for val in won_avgs],
            textposition="auto",
        )
    )

    fig.add_trace(
        go.Bar(
            name="Lost Matches",
            x=metric_names,
            y=lost_avgs,
            text=[f"{val:.1f}" for val in lost_avgs],
            textposition="auto",
        )
    )

    fig.update_layout(
        title="Key Performance Metrics: Won vs Lost Matches",
        xaxis_title="Metrics",
        yaxis_title="Average Value",
        barmode="group",
        height=500,
    )

    return fig


def render_match_analysis_tab(matches, points, shots):
    """Main function for the Match Analysis tab"""
    st.header("📊 Match Analysis - Performance Insights")

    # Calculate analytics metrics
    analytics_df = calculate_match_analytics(matches, points, shots)

    if analytics_df.empty:
        st.warning("No data available for analysis.")
        return

    # Key insights at the top
    st.subheader("🏆 Key Performance Insights")

    won_matches = analytics_df[analytics_df["match_won"]]
    lost_matches = analytics_df[~analytics_df["match_won"]]

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        avg_net_won = won_matches["net_points"].mean() if len(won_matches) > 0 else 0
        avg_net_lost = lost_matches["net_points"].mean() if len(lost_matches) > 0 else 0
        st.metric(
            "Net Points (Won vs Lost)",
            f"{avg_net_won:.1f}",
            f"{avg_net_won - avg_net_lost:.1f}",
        )

    with col2:
        avg_ratio_won = (
            won_matches["winner_error_ratio"].mean() if len(won_matches) > 0 else 0
        )
        avg_ratio_lost = (
            lost_matches["winner_error_ratio"].mean() if len(lost_matches) > 0 else 0
        )
        st.metric(
            "Winner/Error Ratio",
            f"{avg_ratio_won:.2f}",
            f"{avg_ratio_won - avg_ratio_lost:.2f}",
        )

    with col3:
        avg_service_won = (
            won_matches["service_winners"].mean() if len(won_matches) > 0 else 0
        )
        avg_service_lost = (
            lost_matches["service_winners"].mean() if len(lost_matches) > 0 else 0
        )
        st.metric(
            "Service Winners",
            f"{avg_service_won:.1f}",
            f"{avg_service_won - avg_service_lost:.1f}",
        )

    with col4:
        avg_bp_won = (
            won_matches["break_point_conversion"].mean() if len(won_matches) > 0 else 0
        )
        avg_bp_lost = (
            lost_matches["break_point_conversion"].mean()
            if len(lost_matches) > 0
            else 0
        )
        st.metric(
            "Break Point Conv.", f"{avg_bp_won:.1%}", f"{avg_bp_won - avg_bp_lost:.1%}"
        )

    # Net Points Analysis
    st.subheader("🎯 Net Points Analysis")
    st.info(
        """
    **Net Points = (Your Winners + Opponent Errors) - (Your Errors + Double Faults)**

    This measures your **shot impact** - how many points you CREATE vs GIVE AWAY.
    Positive net points mean you're creating more than you're giving away!
    """
    )

    net_points_fig = create_net_points_breakdown_chart(analytics_df)
    st.plotly_chart(net_points_fig, use_container_width=True, theme="streamlit")

    # Performance Comparison Dashboard
    st.subheader("📈 Won vs Lost Matches Analysis")
    dashboard_fig = create_performance_comparison_dashboard(analytics_df)
    st.plotly_chart(dashboard_fig, use_container_width=True, theme="streamlit")

    # Detailed Data
    st.subheader("📋 Detailed Analytics Data")

    # Show the full analytics dataframe
    display_df = analytics_df.copy()

    # Format columns for better display
    percentage_cols = [
        "points_won_pct",
        "break_point_conversion",
        "return_points_won_pct",
        "first_serve_pct",
    ]
    for col in percentage_cols:
        if col in display_df.columns:
            display_df[col] = display_df[col].map("{:.1%}".format)

    # Add match result column
    display_df["Result"] = display_df["match_won"].map(
        {True: "✅ WON", False: "❌ LOST"}
    )

    # Reorder columns for better presentation
    column_order = [
        "match_date",
        "opponent",
        "Result",
        "net_points",
        "positive_shots",
        "negative_shots",
        "my_winners",
        "opponent_errors",
        "my_unforced_errors",
        "my_double_faults",
        "winner_error_ratio",
        "service_winners",
        "break_point_conversion",
        "return_points_won_pct",
    ]

    display_cols = [col for col in column_order if col in display_df.columns]
    st.dataframe(display_df[display_cols], use_container_width=True)

    # Download button
    csv = display_df.to_csv(index=False)
    st.download_button(
        label="📥 Download Analytics Data as CSV",
        data=csv,
        file_name="tennis_analytics_data.csv",
        mime="text/csv",
    )
