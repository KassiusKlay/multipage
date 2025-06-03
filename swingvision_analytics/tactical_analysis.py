"""
Tactical Analysis module for SwingVision analytics
Contains functions for analyzing tactical patterns and game strategies
"""

import streamlit as st
import pandas as pd

HOST = "Joao Cassis"


def identify_tie_breaks(points):
    """Identify which games are tie-breaks vs regular games"""
    tie_break_info = {}

    for _, point in points.iterrows():
        match_id = point["match_id"]
        set_num = point["set"]
        game_num = point["game"]

        key = f"{match_id}_Set{set_num}_Game{game_num}"

        if key not in tie_break_info:
            tie_break_info[key] = {
                "match_id": match_id,
                "set": set_num,
                "game": game_num,
                "points": [],
                "has_impossible_scores": False,
            }

        tie_break_info[key]["points"].append(point)

        # Check for impossible tennis scores (indicates tie-break scoring confusion)
        impossible_scores = ["AD-AD", "15-AD", "30-AD", "AD-30", "AD-0", "0-AD"]
        score = f"{point['host_game_score']}-{point['guest_game_score']}"
        if score in impossible_scores:
            tie_break_info[key]["has_impossible_scores"] = True

    # Classify each game
    classifications = {}

    for key, info in tie_break_info.items():
        match_id = info["match_id"]
        set_num = info["set"]
        game_num = info["game"]

        # Get all games in this set to understand structure
        set_games = [
            k
            for k in tie_break_info.keys()
            if tie_break_info[k]["match_id"] == match_id
            and tie_break_info[k]["set"] == set_num
        ]

        set_game_numbers = [tie_break_info[k]["game"] for k in set_games]
        min_game = min(set_game_numbers)
        max_game = max(set_game_numbers)

        # Classification logic
        if info["has_impossible_scores"]:
            # Has impossible scores = tie-break
            if set_num == 3:
                game_type = "match_tie_break"
            else:
                game_type = "set_tie_break"
        elif set_num == 3 and len(set_game_numbers) == 1:
            # Single game in Set 3 = likely match tie-break
            game_type = "match_tie_break"
        elif game_num == 13 and game_num == max_game:
            # Game 13 that ends the set = set tie-break
            game_type = "set_tie_break"
        else:
            # Regular game
            game_type = "regular"

        classifications[key] = game_type

    return classifications


@st.cache_data
def get_first_point_winner_outcome(points):
    """Analyze first point impact on game outcome (regular games only)"""
    game_classifications = identify_tie_breaks(points)

    # Filter for regular games only
    regular_points = []
    for _, point in points.iterrows():
        key = f"{point['match_id']}_Set{point['set']}_Game{point['game']}"
        if game_classifications.get(key) == "regular":
            regular_points.append(point)

    if not regular_points:
        return pd.DataFrame()

    regular_df = pd.DataFrame(regular_points)

    first_points = (
        regular_df.groupby(["match_id", "set", "game"], as_index=False)
        .first()
        .rename(columns={"point_winner": "first_point_winner"})
    )
    first_points["first_point_winner"] = first_points["first_point_winner"].apply(
        lambda x: HOST if x == HOST else "Opponent"
    )
    game_winners = (
        regular_df.groupby(["match_id", "set", "game"], as_index=False)
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
def analyze_game_score_performance(points):
    """Analyze performance at different game scores (REGULAR GAMES ONLY)"""
    game_classifications = identify_tie_breaks(points)

    # Filter for regular games only
    regular_points = []
    for _, point in points.iterrows():
        key = f"{point['match_id']}_Set{point['set']}_Game{point['game']}"
        if game_classifications.get(key) == "regular":
            regular_points.append(point)

    if not regular_points:
        return pd.DataFrame(), pd.DataFrame()

    # Map score combinations to readable format
    def format_game_score(host_score, guest_score):
        score_map = {"0": "0", "15": "15", "30": "30", "40": "40", "AD": "AD"}
        return f"{score_map.get(str(host_score), str(host_score))}-{score_map.get(str(guest_score), str(guest_score))}"

    game_score_data = []

    for point in regular_points:
        host_score = point["host_game_score"]
        guest_score = point["guest_game_score"]

        # Skip if scores are missing
        if pd.isna(host_score) or pd.isna(guest_score):
            continue

        game_score = format_game_score(host_score, guest_score)
        won_point = point["point_winner"] == HOST
        is_serving = point["match_server"] == HOST

        # Identify critical situations (only valid in regular games)
        is_deuce = str(host_score) == "40" and str(guest_score) == "40"
        is_break_point = point["break_point"]
        is_set_point = point["set_point"]

        game_score_data.append(
            {
                "game_score": game_score,
                "won_point": won_point,
                "is_serving": is_serving,
                "is_deuce": is_deuce,
                "is_break_point": is_break_point,
                "is_set_point": is_set_point,
                "match_id": point["match_id"],
            }
        )

    df = pd.DataFrame(game_score_data)

    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

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
def analyze_set_tie_break_performance(points):
    """Analyze performance in set tie-breaks"""
    game_classifications = identify_tie_breaks(points)

    # Filter for set tie-breaks only
    set_tb_points = []
    for _, point in points.iterrows():
        key = f"{point['match_id']}_Set{point['set']}_Game{point['game']}"
        if game_classifications.get(key) == "set_tie_break":
            set_tb_points.append(point)

    if not set_tb_points:
        return pd.DataFrame()

    set_tb_df = pd.DataFrame(set_tb_points)

    # Group by tie-break (match_id, set, game)
    tie_break_results = []

    for (match_id, set_num, game_num), tb_points in set_tb_df.groupby(
        ["match_id", "set", "game"]
    ):
        tb_points_sorted = tb_points.sort_values("point")

        total_points = len(tb_points_sorted)
        joao_points = len(tb_points_sorted[tb_points_sorted["point_winner"] == HOST])
        opponent_points = total_points - joao_points

        # Get winner (last point winner)
        winner = tb_points_sorted.iloc[-1]["point_winner"]
        won_tb = winner == HOST

        # Get opponent name (approximate from server/winner data)
        opponent = "Opponent"
        for _, point in tb_points_sorted.iterrows():
            if point["point_winner"] != HOST:
                opponent = point["point_winner"]
                break
            elif point["match_server"] != HOST:
                opponent = point["match_server"]
                break

        # Calculate first-to-X performance
        first_to_3 = None
        first_to_5 = None

        joao_count = 0
        opp_count = 0

        for _, point in tb_points_sorted.iterrows():
            if point["point_winner"] == HOST:
                joao_count += 1
            else:
                opp_count += 1

            if first_to_3 is None and (joao_count >= 3 or opp_count >= 3):
                first_to_3 = joao_count >= 3

            if first_to_5 is None and (joao_count >= 5 or opp_count >= 5):
                first_to_5 = joao_count >= 5

        tie_break_results.append(
            {
                "match_id": match_id,
                "set": set_num,
                "game": game_num,
                "opponent": opponent,
                "total_points": total_points,
                "joao_points": joao_points,
                "opponent_points": opponent_points,
                "won_tie_break": won_tb,
                "first_to_3": first_to_3,
                "first_to_5": first_to_5,
                "final_score": f"{joao_points}-{opponent_points}",
            }
        )

    results_df = pd.DataFrame(tie_break_results)

    if results_df.empty:
        return pd.DataFrame()

    # Calculate summary statistics
    summary_stats = {
        "total_tie_breaks": len(results_df),
        "tie_breaks_won": len(results_df[results_df["won_tie_break"]]),
        "win_percentage": len(results_df[results_df["won_tie_break"]])
        / len(results_df)
        * 100,
        "avg_points_scored": results_df["joao_points"].mean(),
        "avg_points_allowed": results_df["opponent_points"].mean(),
        "first_to_3_rate": results_df["first_to_3"].sum() / len(results_df) * 100,
        "first_to_5_rate": results_df["first_to_5"].sum() / len(results_df) * 100,
    }

    results_df["summary_stats"] = [summary_stats] * len(results_df)

    return results_df


@st.cache_data
def analyze_match_tie_break_performance(points):
    """Analyze performance in match tie-breaks"""
    game_classifications = identify_tie_breaks(points)

    # Filter for match tie-breaks only
    match_tb_points = []
    for _, point in points.iterrows():
        key = f"{point['match_id']}_Set{point['set']}_Game{point['game']}"
        if game_classifications.get(key) == "match_tie_break":
            match_tb_points.append(point)

    if not match_tb_points:
        return pd.DataFrame()

    match_tb_df = pd.DataFrame(match_tb_points)

    # Group by tie-break (match_id, set, game)
    tie_break_results = []

    for (match_id, set_num, game_num), tb_points in match_tb_df.groupby(
        ["match_id", "set", "game"]
    ):
        tb_points_sorted = tb_points.sort_values("point")

        total_points = len(tb_points_sorted)
        joao_points = len(tb_points_sorted[tb_points_sorted["point_winner"] == HOST])
        opponent_points = total_points - joao_points

        # Get winner (last point winner)
        winner = tb_points_sorted.iloc[-1]["point_winner"]
        won_tb = winner == HOST

        # Get opponent name
        opponent = "Opponent"
        for _, point in tb_points_sorted.iterrows():
            if point["point_winner"] != HOST:
                opponent = point["point_winner"]
                break
            elif point["match_server"] != HOST:
                opponent = point["match_server"]
                break

        # Calculate performance at different score milestones
        first_to_5 = None
        first_to_8 = None
        reached_match_point = False

        joao_count = 0
        opp_count = 0

        for _, point in tb_points_sorted.iterrows():
            if point["point_winner"] == HOST:
                joao_count += 1
            else:
                opp_count += 1

            if first_to_5 is None and (joao_count >= 5 or opp_count >= 5):
                first_to_5 = joao_count >= 5

            if first_to_8 is None and (joao_count >= 8 or opp_count >= 8):
                first_to_8 = joao_count >= 8

            # Check if reached match point (9 points with 2-point lead, or 10 points)
            if (joao_count >= 9 and joao_count - opp_count >= 2) or joao_count >= 10:
                reached_match_point = True
                break
            elif (opp_count >= 9 and opp_count - joao_count >= 2) or opp_count >= 10:
                break

        tie_break_results.append(
            {
                "match_id": match_id,
                "set": set_num,
                "game": game_num,
                "opponent": opponent,
                "total_points": total_points,
                "joao_points": joao_points,
                "opponent_points": opponent_points,
                "won_tie_break": won_tb,
                "first_to_5": first_to_5,
                "first_to_8": first_to_8,
                "reached_match_point": reached_match_point,
                "final_score": f"{joao_points}-{opponent_points}",
            }
        )

    results_df = pd.DataFrame(tie_break_results)

    if results_df.empty:
        return pd.DataFrame()

    # Calculate summary statistics
    summary_stats = {
        "total_tie_breaks": len(results_df),
        "tie_breaks_won": len(results_df[results_df["won_tie_break"]]),
        "win_percentage": len(results_df[results_df["won_tie_break"]])
        / len(results_df)
        * 100,
        "avg_points_scored": results_df["joao_points"].mean(),
        "avg_points_allowed": results_df["opponent_points"].mean(),
        "first_to_5_rate": (
            results_df["first_to_5"].sum() / len(results_df) * 100
            if len(results_df) > 0
            else 0
        ),
        "first_to_8_rate": (
            results_df["first_to_8"].sum() / len(results_df) * 100
            if len(results_df) > 0
            else 0
        ),
        "match_point_conversion": len(
            results_df[
                (results_df["reached_match_point"]) & (results_df["won_tie_break"])
            ]
        )
        / max(1, len(results_df[results_df["reached_match_point"]]))
        * 100,
    }

    results_df["summary_stats"] = [summary_stats] * len(results_df)

    return results_df


@st.cache_data
def analyze_clutch_performance(points):
    """Analyze late-game clutch performance in critical moments (REGULAR GAMES ONLY)"""
    game_classifications = identify_tie_breaks(points)

    # Filter for regular games only
    regular_points = []
    for _, point in points.iterrows():
        key = f"{point['match_id']}_Set{point['set']}_Game{point['game']}"
        if game_classifications.get(key) == "regular":
            regular_points.append(point)

    if not regular_points:
        return pd.DataFrame(), pd.DataFrame()

    clutch_situations = []

    for point in regular_points:
        won_point = point["point_winner"] == HOST
        is_serving = point["match_server"] == HOST

        # Define clutch situations (only valid in regular games)
        situations = {
            "break_point": point["break_point"],
            "set_point": point["set_point"],
            "deuce_or_ad": "AD" in str(point["host_game_score"])
            or "AD" in str(point["guest_game_score"])
            or (
                str(point["host_game_score"]) == "40"
                and str(point["guest_game_score"]) == "40"
            ),
            "tight_game": str(point["host_game_score"]) in ["30", "40"]
            and str(point["guest_game_score"]) in ["30", "40"],
        }

        for situation_name, is_situation in situations.items():
            if is_situation:
                clutch_situations.append(
                    {
                        "situation": situation_name,
                        "won_point": won_point,
                        "is_serving": is_serving,
                        "match_id": point["match_id"],
                        "set": point["set"],
                        "game": point["game"],
                    }
                )

    df = pd.DataFrame(clutch_situations)

    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

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

    # First Point Analysis (Regular Games Only)
    st.subheader("🎯 First Point Impact Analysis (Regular Games)")
    col1, col2 = st.columns(2)

    with col1:
        st.write("**First Point Winner Impact on Game**")
        first_point_stats = get_first_point_winner_outcome(points)
        if not first_point_stats.empty:
            st.dataframe(
                first_point_stats.style.format({"win_pct": "{:.1%}"}),
                use_container_width=True,
            )

    with col2:
        st.write("**Serve First Advantage in Sets**")
        serve_first_stats = analyze_serve_first_advantage(points)
        if not serve_first_stats.empty:
            st.dataframe(
                serve_first_stats.style.format({"win_pct": "{:.1%}"}),
                use_container_width=True,
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
    else:
        st.info("Not enough rally data for analysis.")

    # REGULAR GAMES ANALYSIS
    st.subheader("🎯 Regular Games - Game Score Performance")
    score_perf, critical_perf = analyze_game_score_performance(points)

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Performance by Game Score (Regular Games Only):**")
        if not score_perf.empty:
            st.dataframe(
                score_perf.style.format({"Win_Rate": "{:.1%}"}),
                use_container_width=True,
            )

    with col2:
        st.write("**Critical Situations (Regular Games Only):**")
        if not critical_perf.empty:
            st.dataframe(
                critical_perf.style.format({"Win_Rate": "{:.1%}"}),
                use_container_width=True,
            )

    # SET TIE-BREAKS ANALYSIS
    st.subheader("🏆 Set Tie-Breaks Performance")

    set_tb_data = analyze_set_tie_break_performance(points)

    if not set_tb_data.empty:
        # Display summary statistics
        summary_stats = set_tb_data.iloc[0]["summary_stats"]

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(
                "Tie-Breaks Won",
                f"{summary_stats['tie_breaks_won']}/{summary_stats['total_tie_breaks']}",
            )
        with col2:
            st.metric("Win Rate", f"{summary_stats['win_percentage']:.1f}%")
        with col3:
            st.metric("Avg Points Scored", f"{summary_stats['avg_points_scored']:.1f}")
        with col4:
            st.metric("First to 3 Rate", f"{summary_stats['first_to_3_rate']:.1f}%")

        # Display detailed results
        st.write("**Set Tie-Break Results:**")
        display_cols = [
            "opponent",
            "set",
            "final_score",
            "won_tie_break",
            "first_to_3",
            "first_to_5",
        ]
        display_df = set_tb_data[display_cols].copy()
        display_df["Result"] = display_df["won_tie_break"].map(
            {True: "✅ WON", False: "❌ LOST"}
        )
        display_df["First to 3"] = display_df["first_to_3"].map(
            {True: "✅", False: "❌"}
        )
        display_df["First to 5"] = display_df["first_to_5"].map(
            {True: "✅", False: "❌"}
        )

        st.dataframe(
            display_df[
                ["opponent", "set", "final_score", "Result", "First to 3", "First to 5"]
            ],
            use_container_width=True,
        )

    else:
        st.info("No set tie-breaks found in the data.")

    # MATCH TIE-BREAKS ANALYSIS
    st.subheader("🥇 Match Tie-Breaks Performance")

    match_tb_data = analyze_match_tie_break_performance(points)

    if not match_tb_data.empty:
        # Display summary statistics
        summary_stats = match_tb_data.iloc[0]["summary_stats"]

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(
                "Tie-Breaks Won",
                f"{summary_stats['tie_breaks_won']}/{summary_stats['total_tie_breaks']}",
            )
        with col2:
            st.metric("Win Rate", f"{summary_stats['win_percentage']:.1f}%")
        with col3:
            st.metric("Avg Points Scored", f"{summary_stats['avg_points_scored']:.1f}")
        with col4:
            st.metric(
                "Match Point Conversion",
                f"{summary_stats['match_point_conversion']:.1f}%",
            )

        # Additional metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("First to 5 Rate", f"{summary_stats['first_to_5_rate']:.1f}%")
        with col2:
            st.metric("First to 8 Rate", f"{summary_stats['first_to_8_rate']:.1f}%")
        with col3:
            st.metric(
                "Avg Points Allowed", f"{summary_stats['avg_points_allowed']:.1f}"
            )

        # Display detailed results
        st.write("**Match Tie-Break Results:**")
        display_cols = [
            "opponent",
            "final_score",
            "won_tie_break",
            "first_to_5",
            "first_to_8",
            "reached_match_point",
        ]
        display_df = match_tb_data[display_cols].copy()
        display_df["Result"] = display_df["won_tie_break"].map(
            {True: "✅ WON", False: "❌ LOST"}
        )
        display_df["First to 5"] = display_df["first_to_5"].map(
            {True: "✅", False: "❌"}
        )
        display_df["First to 8"] = display_df["first_to_8"].map(
            {True: "✅", False: "❌"}
        )
        display_df["Reached MP"] = display_df["reached_match_point"].map(
            {True: "✅", False: "❌"}
        )

        st.dataframe(
            display_df[
                [
                    "opponent",
                    "final_score",
                    "Result",
                    "First to 5",
                    "First to 8",
                    "Reached MP",
                ]
            ],
            use_container_width=True,
        )

    else:
        st.info("No match tie-breaks found in the data.")

    # CLUTCH PERFORMANCE (Regular Games)
    st.subheader("⚡ Clutch Performance Analysis (Regular Games)")
    overall_clutch, detailed_clutch = analyze_clutch_performance(points)

    if not overall_clutch.empty:
        st.write("**Performance in Pressure Situations:**")
        st.dataframe(
            overall_clutch.style.format({"Win_Rate": "{:.1%}"}),
            use_container_width=True,
        )
    else:
        st.info("Not enough clutch situation data for analysis.")
