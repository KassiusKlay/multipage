"""
Tactical Analysis module for SwingVision analytics
Contains functions for analyzing tactical patterns and game strategies
"""

import streamlit as st
import pandas as pd

HOST = "Joao Cassis"


@st.cache_data
def get_first_point_winner_outcome(points):
    first_points = (
        points.groupby(["match_id", "set", "game"], as_index=False)
        .first()
        .rename(columns={"point_winner": "first_point_winner"})
    )
    first_points["first_point_winner"] = first_points["first_point_winner"].apply(
        lambda x: HOST if x == HOST else "Opponent"
    )
    game_winners = (
        points.groupby(["match_id", "set", "game"], as_index=False)
        .last()
        .rename(columns={"point_winner": "game_winner"})
    )
    df = first_points.merge(game_winners, on=["match_id", "set", "game"])
    first_point_winner_outcome = (
        df.groupby("first_point_winner")
        .agg(
            games_played=("game_winner", "size"),
            games_won=("game_winner", lambda s: (s == HOST).sum()),
        )
        .assign(win_pct=lambda d: d["games_won"] / d["games_played"])
    )
    return first_point_winner_outcome


@st.cache_data
def analyze_serve_first_advantage(points):
    """Analyze if serving first in the set gives advantage to win the set"""
    first_points_per_set = (
        points.groupby(["match_id", "set"], as_index=False)
        .first()
        .rename(columns={"match_server": "set_first_server"})[
            ["match_id", "set", "set_first_server"]
        ]
    )
    last_points_per_set = (
        points.groupby(["match_id", "set"], as_index=False)
        .last()
        .rename(columns={"point_winner": "set_winner"})[
            ["match_id", "set", "set_winner"]
        ]
    )
    set_results = first_points_per_set.merge(
        last_points_per_set, on=["match_id", "set"]
    )
    set_results["i_served_first"] = set_results["set_first_server"] == HOST
    set_results["i_won_set"] = set_results["set_winner"] == HOST
    serve_first_stats = (
        set_results.groupby("i_served_first")
        .agg(
            sets_played=("i_won_set", "size"),
            sets_won=("i_won_set", "sum"),
        )
        .assign(win_pct=lambda d: d["sets_won"] / d["sets_played"])
    )
    serve_first_stats.index = serve_first_stats.index.map(
        lambda x: "Joao Cassis" if x else "Opponent"
    )
    serve_first_stats = serve_first_stats.loc[["Joao Cassis", "Opponent"]]
    serve_first_stats.index.name = "served_first"
    return serve_first_stats


@st.cache_data
def analyze_rally_length_impact(shots, points):
    """Analyze how performance changes in short vs long rallies"""
    HOST = "Joao Cassis"

    rally_analysis = []

    # Group shots by point to count rally length
    for (match_id, set_num, game, point), point_shots in shots.groupby(
        ["match_id", "set", "game", "point"]
    ):
        # Filter out feeds and serves for rally counting
        rally_shots = point_shots[~point_shots["stroke"].isin(["Feed", "Serve"])]
        rally_length = len(rally_shots)

        if rally_length == 0:
            continue

        # Get point winner
        point_data = points[
            (points["match_id"] == match_id)
            & (points["set"] == set_num)
            & (points["game"] == game)
            & (points["point"] == point)
        ]

        if point_data.empty:
            continue

        point_winner = point_data.iloc[-1]["point_winner"]
        won_point = point_winner == HOST

        # Count my shots in this rally
        my_shots_in_rally = len(rally_shots[rally_shots["player"] == HOST])

        rally_analysis.append(
            {
                "match_id": match_id,
                "rally_length": rally_length,
                "my_shots_count": my_shots_in_rally,
                "won_point": won_point,
                "point_detail": (
                    point_data.iloc[-1]["detail"] if not point_data.empty else ""
                ),
            }
        )

    df = pd.DataFrame(rally_analysis)

    if df.empty:
        return pd.DataFrame()

    # Categorize rally lengths
    df["rally_category"] = pd.cut(
        df["rally_length"],
        bins=[0, 4, 8, 12, float("inf")],
        labels=["Short (1-4)", "Medium (5-8)", "Long (9-12)", "Very Long (13+)"],
    )

    # Calculate performance by rally length
    rally_performance = (
        df.groupby("rally_category")
        .agg({"won_point": ["count", "sum", "mean"], "rally_length": "mean"})
        .round(3)
    )

    rally_performance.columns = [
        "Total_Points",
        "Points_Won",
        "Win_Rate",
        "Avg_Rally_Length",
    ]

    return rally_performance


@st.cache_data
def analyze_streak_patterns(points):
    """Analyze performance after winning/losing multiple points in a row"""
    HOST = "Joao Cassis"

    streak_data = []

    # Sort points chronologically within each match
    points_sorted = points.sort_values(["match_id", "set", "game", "point"])

    for match_id, match_points in points_sorted.groupby("match_id"):
        current_streak = 0
        streak_type = None  # 'win' or 'loss'

        match_points = match_points.reset_index(drop=True)

        for i, row in match_points.iterrows():
            won_point = row["point_winner"] == HOST

            # Update streak
            if streak_type is None:
                # First point of match
                current_streak = 1
                streak_type = "win" if won_point else "loss"
            elif (streak_type == "win" and won_point) or (
                streak_type == "loss" and not won_point
            ):
                # Continue streak
                current_streak += 1
            else:
                # Streak broken, start new one
                current_streak = 1
                streak_type = "win" if won_point else "loss"

            # Record data for next point analysis
            if i < len(match_points) - 1:  # Not the last point
                next_won = match_points.iloc[i + 1]["point_winner"] == HOST

                streak_data.append(
                    {
                        "match_id": match_id,
                        "current_streak_length": min(
                            current_streak, 10
                        ),  # Cap at 10 for analysis
                        "current_streak_type": streak_type,
                        "won_next_point": next_won,
                        "break_point": row["break_point"],
                        "set_point": row["set_point"],
                    }
                )

    df = pd.DataFrame(streak_data)

    if df.empty:
        return pd.DataFrame()

    # Analyze performance after different streak lengths
    streak_analysis = (
        df.groupby(["current_streak_type", "current_streak_length"])
        .agg({"won_next_point": ["count", "sum", "mean"]})
        .round(3)
    )

    streak_analysis.columns = ["Total_Points", "Next_Points_Won", "Next_Point_Win_Rate"]

    return streak_analysis


@st.cache_data
def analyze_game_score_performance(points):
    """Analyze performance at different game scores (0-0, 30-30, deuce, etc.)"""
    HOST = "Joao Cassis"

    # Map score combinations to readable format
    def format_game_score(host_score, guest_score):
        score_map = {"0": "0", "15": "15", "30": "30", "40": "40", "AD": "AD"}
        return f"{score_map.get(host_score, host_score)}-{score_map.get(guest_score, guest_score)}"

    game_score_data = []

    for _, row in points.iterrows():
        host_score = row["host_game_score"]
        guest_score = row["guest_game_score"]

        # Skip if scores are missing
        if pd.isna(host_score) or pd.isna(guest_score):
            continue

        game_score = format_game_score(str(host_score), str(guest_score))
        won_point = row["point_winner"] == HOST
        is_serving = row["match_server"] == HOST

        # Identify critical situations
        is_deuce = (host_score == "40" and guest_score == "40") or (
            "AD" in str(host_score) or "AD" in str(guest_score)
        )
        is_break_point = row["break_point"]
        is_set_point = row["set_point"]

        game_score_data.append(
            {
                "game_score": game_score,
                "won_point": won_point,
                "is_serving": is_serving,
                "is_deuce": is_deuce,
                "is_break_point": is_break_point,
                "is_set_point": is_set_point,
                "match_id": row["match_id"],
            }
        )

    df = pd.DataFrame(game_score_data)

    if df.empty:
        return pd.DataFrame()

    # Analyze performance by game score
    score_performance = (
        df.groupby("game_score").agg({"won_point": ["count", "sum", "mean"]}).round(3)
    )

    score_performance.columns = ["Total_Points", "Points_Won", "Win_Rate"]

    # Sort by total points to show most common scores first
    score_performance = score_performance.sort_values("Total_Points", ascending=False)

    # Separate analysis for critical situations
    critical_situations = (
        df.groupby(["is_deuce", "is_break_point", "is_set_point"])
        .agg({"won_point": ["count", "sum", "mean"]})
        .round(3)
    )

    critical_situations.columns = ["Total_Points", "Points_Won", "Win_Rate"]

    return score_performance, critical_situations


@st.cache_data
def analyze_clutch_performance(points):
    """Analyze late-game clutch performance in critical moments"""
    HOST = "Joao Cassis"

    clutch_situations = []

    for _, row in points.iterrows():
        won_point = row["point_winner"] == HOST
        is_serving = row["match_server"] == HOST

        # Define clutch situations
        situations = {
            "break_point": row["break_point"],
            "set_point": row["set_point"],
            "deuce_or_ad": "AD" in str(row["host_game_score"])
            or "AD" in str(row["guest_game_score"])
            or (row["host_game_score"] == "40" and row["guest_game_score"] == "40"),
            "tight_game": str(row["host_game_score"]) in ["30", "40"]
            and str(row["guest_game_score"]) in ["30", "40"],
        }

        for situation_name, is_situation in situations.items():
            if is_situation:
                clutch_situations.append(
                    {
                        "situation": situation_name,
                        "won_point": won_point,
                        "is_serving": is_serving,
                        "match_id": row["match_id"],
                        "set": row["set"],
                        "game": row["game"],
                    }
                )

    df = pd.DataFrame(clutch_situations)

    if df.empty:
        return pd.DataFrame()

    # Analyze clutch performance by situation
    clutch_analysis = (
        df.groupby(["situation", "is_serving"])
        .agg({"won_point": ["count", "sum", "mean"]})
        .round(3)
    )

    clutch_analysis.columns = ["Total_Points", "Points_Won", "Win_Rate"]

    # Overall clutch performance
    overall_clutch = (
        df.groupby("situation").agg({"won_point": ["count", "sum", "mean"]}).round(3)
    )

    overall_clutch.columns = ["Total_Points", "Points_Won", "Win_Rate"]

    return overall_clutch, clutch_analysis


def render_tactical_analysis_tab(matches, points, shots):
    """Main function for the Tactical Analysis tab"""
    st.header("🧠 Tactical Analysis - Game Strategy Analysis")

    # First Point Analysis
    st.subheader("🎯 First Point Impact Analysis")
    col1, col2 = st.columns(2)

    with col1:
        st.write("**First Point Winner Impact on Game**")
        first_point_stats = get_first_point_winner_outcome(points)
        if not first_point_stats.empty:
            st.dataframe(
                first_point_stats.style.format({"win_pct": "{:.1%}"}),
                use_container_width=True,
            )

            # Add interpretation
            winner_win_pct = (
                first_point_stats.loc["Joao Cassis", "win_pct"]
                if "Joao Cassis" in first_point_stats.index
                else 0
            )
            opponent_win_pct = (
                first_point_stats.loc["Opponent", "win_pct"]
                if "Opponent" in first_point_stats.index
                else 0
            )

            if winner_win_pct > 0.6:
                st.success(
                    "**Insight**: When you win the first point, you have a strong chance of winning the game!"
                )
            elif opponent_win_pct > 0.6:
                st.error(
                    "**Warning**: When your opponent wins the first point, they tend to win the game."
                )

    with col2:
        st.write("**Serve First Advantage in Sets**")
        serve_first_stats = analyze_serve_first_advantage(points)
        if not serve_first_stats.empty:
            st.dataframe(
                serve_first_stats.style.format({"win_pct": "{:.1%}"}),
                use_container_width=True,
            )

            # Add interpretation
            your_advantage = (
                serve_first_stats.loc["Joao Cassis", "win_pct"]
                if "Joao Cassis" in serve_first_stats.index
                else 0
            )
            opp_advantage = (
                serve_first_stats.loc["Opponent", "win_pct"]
                if "Opponent" in serve_first_stats.index
                else 0
            )

            if your_advantage > opp_advantage + 0.1:
                st.success(
                    "**Tactical Tip**: Choose to serve first when you win the toss!"
                )
            elif opp_advantage > your_advantage + 0.1:
                st.info(
                    "**Tactical Tip**: Consider choosing to receive when you win the toss."
                )

    st.subheader("🎾 Rally Length Performance Analysis")
    rally_performance = analyze_rally_length_impact(shots, points)

    if not rally_performance.empty:
        st.dataframe(
            rally_performance.style.format(
                {"Win_Rate": "{:.1%}", "Avg_Rally_Length": "{:.1f}"}
            ),
            use_container_width=True,
        )

        # Key insights
        best_rally_type = rally_performance["Win_Rate"].idxmax()
        best_win_rate = rally_performance.loc[best_rally_type, "Win_Rate"]
        st.success(
            f"🎯 **Best Rally Length**: {best_rally_type} rallies ({best_win_rate:.1%} win rate)"
        )
    else:
        st.info("Not enough rally data for analysis.")

    st.subheader("🔥 Streak Pattern Analysis")
    streak_analysis = analyze_streak_patterns(points)

    if not streak_analysis.empty:
        st.write("**Performance after winning/losing streaks:**")
        st.dataframe(
            streak_analysis.style.format({"Next_Point_Win_Rate": "{:.1%}"}),
            use_container_width=True,
        )

        # Show key patterns
        if ("win", 3) in streak_analysis.index:
            win_3_rate = streak_analysis.loc[("win", 3), "Next_Point_Win_Rate"]
            st.info(
                f"After 3-point winning streak: {win_3_rate:.1%} chance of winning next point"
            )
    else:
        st.info("Not enough streak data for analysis.")

    st.subheader("🎯 Game Score Performance")
    score_perf, critical_perf = analyze_game_score_performance(points)

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Performance by Game Score:**")
        if not score_perf.empty:
            st.dataframe(
                score_perf.style.format({"Win_Rate": "{:.1%}"}),
                use_container_width=True,
            )

    with col2:
        st.write("**Critical Situations:**")
        if not critical_perf.empty:
            st.dataframe(
                critical_perf.style.format({"Win_Rate": "{:.1%}"}),
                use_container_width=True,
            )

    st.subheader("⚡ Clutch Performance Analysis")
    overall_clutch, detailed_clutch = analyze_clutch_performance(points)

    if not overall_clutch.empty:
        st.write("**Performance in Pressure Situations:**")
        st.dataframe(
            overall_clutch.style.format({"Win_Rate": "{:.1%}"}),
            use_container_width=True,
        )

        # Highlight best/worst clutch situations
        best_clutch = overall_clutch["Win_Rate"].idxmax()
        worst_clutch = overall_clutch["Win_Rate"].idxmin()

        col1, col2 = st.columns(2)
        with col1:
            st.success(
                f"💪 **Strongest in**: {best_clutch.replace('_', ' ').title()} ({overall_clutch.loc[best_clutch, 'Win_Rate']:.1%})"
            )
        with col2:
            st.error(
                f"⚠️ **Focus on**: {worst_clutch.replace('_', ' ').title()} ({overall_clutch.loc[worst_clutch, 'Win_Rate']:.1%})"
            )
    else:
        st.info("Not enough clutch situation data for analysis.")
