"""
Shot Analysis module for SwingVision analytics
Contains functions for analyzing shot patterns, strengths, and weaknesses
"""

import streamlit as st
import pandas as pd

HOST = "Joao Cassis"


@st.cache_data
def get_bad_shots(shots):
    my_shots = shots[(shots["player"] == HOST)]
    total_by_stroke = my_shots.groupby("stroke").size().rename("total")
    last_shots = my_shots.loc[
        my_shots.groupby(["match_id", "set", "game", "point"])["shot"].idxmax()
    ]
    your_errors = last_shots[last_shots["result"].isin(["Out", "Net"])]
    error_by_stroke = your_errors.groupby("stroke").size().rename("error_count")
    forced_winner = []
    for _, grp in shots.groupby(["match_id", "set", "game", "point"]):
        last = grp.sort_values("shot").iloc[-1]
        if (last["player"] != HOST) and (last["result"] == "In"):
            penult = grp[grp["player"] == HOST].sort_values("shot").iloc[-1:]
            if not penult.empty:
                forced_winner.append(penult.iloc[0]["stroke"])
    opp_win_by_stroke = pd.Series(forced_winner).value_counts().rename("opp_win_count")
    bad_shots = pd.concat(
        [total_by_stroke, error_by_stroke, opp_win_by_stroke], axis=1
    ).fillna(0)
    bad_shots["error_pct"] = bad_shots["error_count"] / bad_shots["total"]
    bad_shots["opp_win_pct"] = bad_shots["opp_win_count"] / bad_shots["total"]
    bad_shots["total_pct"] = bad_shots["error_pct"] + bad_shots["opp_win_pct"]
    bad_shots = bad_shots.sort_values("total_pct", ascending=False)
    return bad_shots


@st.cache_data
def get_good_shots(shots):
    my_shots = shots[(shots["player"] == HOST)]
    total_by_stroke = my_shots.groupby("stroke").size().rename("total")
    last_shots = my_shots.loc[
        my_shots.groupby(["match_id", "set", "game", "point"])["shot"].idxmax()
    ]
    winners = last_shots[last_shots["result"] == "In"]
    winner_by_stroke = winners.groupby("stroke").size().rename("win_count")
    forced = []
    for key, group in shots.groupby(["match_id", "set", "game", "point"]):
        if group.iloc[-1]["player"] != HOST and group.iloc[-1]["result"] != "In":
            penult = group.iloc[:-1].loc[group.iloc[:-1]["player"] == HOST]
            if not penult.empty:
                forced.append(penult.iloc[-1]["stroke"])
    error_by_stroke = pd.Series(forced).value_counts().rename("opp_error_count")
    good_shots = pd.concat(
        [total_by_stroke, winner_by_stroke, error_by_stroke], axis=1
    ).fillna(0)
    good_shots["win_pct"] = good_shots["win_count"] / good_shots["total"]
    good_shots["error_pct"] = good_shots["opp_error_count"] / good_shots["total"]
    good_shots["total_pct"] = good_shots["win_pct"] + good_shots["error_pct"]
    good_shots = good_shots.sort_values("total_pct", ascending=False)
    return good_shots


@st.cache_data
def analyze_error_factors(shots):
    my_errs = shots[
        (shots["player"] == HOST)
        & (shots["stroke"].isin(["Forehand", "Backhand"]))
        & (shots["result"].isin(["Out", "Net"]))
    ]

    rows = []
    for (_, s, g, p), group in shots.groupby(["match_id", "set", "game", "point"]):
        err = my_errs[
            (my_errs["match_id"] == _)
            & (my_errs["set"] == s)
            & (my_errs["game"] == g)
            & (my_errs["point"] == p)
        ]
        if err.empty:
            continue
        err_idx = err["shot"].iloc[0]
        prior = group[group["shot"] == err_idx - 1]
        if prior.empty or prior["player"].iloc[0] == HOST:
            continue
        prev = prior.iloc[0]
        e = err.iloc[0]
        rows.append(
            {
                "match_id": _,
                "set": s,
                "game": g,
                "point": p,
                "error_stroke": e["stroke"],
                "error_result": e["result"],
                "prev_stroke": prev["stroke"],
                "prev_spin": prev["spin"],
                "prev_speed": prev["speed"],
                "prev_bounce_depth": prev["bounce_depth"],
                "prev_bounce_x": prev["bounce_x"],
                "prev_bounce_y": prev["bounce_y"],
                "error_hit_zone": e["hit_zone"],
                "error_hit_x": e["hit_x"],
                "error_hit_y": e["hit_y"],
                "error_hit_direction": e["direction"],
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame()

    error_summary = df.groupby("error_stroke").agg(
        count=("prev_speed", "size"),
        avg_prev_speed=("prev_speed", "mean"),
        deep_pct=("prev_bounce_depth", lambda x: (x == "deep").mean()),
        down_the_line=("error_hit_direction", lambda x: (x == "down the line").mean()),
    )
    return error_summary


@st.cache_data
def analyze_success_factors(shots):
    my_successes = shots[
        (shots["player"] == HOST)
        & (shots["stroke"].isin(["Forehand", "Backhand"]))
        & (shots["result"] == "In")
    ]

    rows = []
    for (_, s, g, p), group in shots.groupby(["match_id", "set", "game", "point"]):
        success = my_successes[
            (my_successes["match_id"] == _)
            & (my_successes["set"] == s)
            & (my_successes["game"] == g)
            & (my_successes["point"] == p)
        ]
        if success.empty:
            continue

        for _, succ in success.iterrows():
            prior = group[group["shot"] == succ["shot"] - 1]
            if prior.empty or prior["player"].iloc[0] == HOST:
                continue
            prev = prior.iloc[0]
            rows.append(
                {
                    "match_id": _,
                    "set": s,
                    "game": g,
                    "point": p,
                    "success_stroke": succ["stroke"],
                    "prev_stroke": prev["stroke"],
                    "prev_spin": prev["spin"],
                    "prev_speed": prev["speed"],
                    "prev_bounce_depth": prev["bounce_depth"],
                    "prev_bounce_x": prev["bounce_x"],
                    "prev_bounce_y": prev["bounce_y"],
                    "success_hit_zone": succ["hit_zone"],
                    "success_hit_x": succ["hit_x"],
                    "success_hit_y": succ["hit_y"],
                    "success_hit_direction": succ["direction"],
                }
            )

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame()

    success_summary = df.groupby("success_stroke").agg(
        count=("prev_speed", "size"),
        avg_prev_speed=("prev_speed", "mean"),
        deep_pct=("prev_bounce_depth", lambda x: (x == "deep").mean()),
        down_the_line=(
            "success_hit_direction",
            lambda x: (x == "down the line").mean(),
        ),
    )
    return success_summary


@st.cache_data
def compare_error_vs_success_factors(shots):
    """Compare characteristics of opponent shots that lead to errors vs successes"""
    error_summary = analyze_error_factors(shots)
    success_summary = analyze_success_factors(shots)

    if error_summary.empty or success_summary.empty:
        return pd.DataFrame()

    comparison = pd.DataFrame()

    for stroke in ["Forehand", "Backhand"]:
        if stroke in error_summary.index and stroke in success_summary.index:
            comparison = pd.concat(
                [
                    comparison,
                    pd.DataFrame(
                        {
                            "stroke": [stroke],
                            "error_count": [error_summary.loc[stroke, "count"]],
                            "success_count": [success_summary.loc[stroke, "count"]],
                            "error_avg_prev_speed": [
                                error_summary.loc[stroke, "avg_prev_speed"]
                            ],
                            "success_avg_prev_speed": [
                                success_summary.loc[stroke, "avg_prev_speed"]
                            ],
                            "error_prev_deep_pct": [
                                error_summary.loc[stroke, "deep_pct"]
                            ],
                            "success_prev_deep_pct": [
                                success_summary.loc[stroke, "deep_pct"]
                            ],
                        }
                    ),
                ]
            )
    return comparison


@st.cache_data
def process_shots_for_court_zone(shots):
    """Process shots data to normalize court perspective for left-handed player"""
    HOST = "Joao Cassis"

    # Filter for your shots only (excluding feeds, serve and returns)
    shots = shots[
        (shots["player"] == HOST)
        & (~shots["stroke"].isin(["Feed", "Serve"]))
        & (~shots["type"].str.contains("_return"))
    ].copy()

    # Court dimensions
    court_length = 23.77  # meters

    # Normalize perspective - flip coordinates when hitting from far side
    condition = shots["hit_y"] > court_length / 2
    shots.loc[condition, "hit_x"] = -shots.loc[condition, "hit_x"]
    shots.loc[condition, "hit_y"] = court_length - shots.loc[condition, "hit_y"]
    shots.loc[condition, "bounce_x"] = -shots.loc[condition, "bounce_x"]
    shots.loc[condition, "bounce_y"] = court_length - shots.loc[condition, "bounce_y"]

    # Handle net shots
    net_condition = shots["result"] == "Net"
    shots.loc[net_condition, "bounce_y"] = court_length / 2

    return shots


@st.cache_data
def get_court_zone(hit_x, hit_y):
    """Get court zone for left-handed player"""
    # Depth zones
    if hit_y < 0:  # Service line
        depth = "Deep"
    elif hit_y < 6.4:  # Mid court
        depth = "Mid"
    else:  # Past service line on opponent side
        depth = "Short"

    # Width zones (adjusted for left-handed player)
    if hit_x < -2:
        width = "Ad"  # Left side is lefty's forehand
    elif hit_x > 2:
        width = "Deuce"  # Right side is lefty's backhand
    else:
        width = "Center"

    return f"{depth} {width}"


@st.cache_data
def analyze_court_zone_success(shots, points):
    """Analyze success rates by court zone for left-handed player"""
    HOST = "Joao Cassis"

    # Process shots for consistent perspective
    processed_df = process_shots_for_court_zone(shots)

    if processed_df.empty:
        return pd.DataFrame()

    # Add court zones
    processed_df["court_zone"] = processed_df.apply(
        lambda row: get_court_zone(row["hit_x"], row["hit_y"]), axis=1
    )

    # Merge with points data to get point outcomes
    zone_analysis = []

    for zone in processed_df["court_zone"].unique():
        zone_shots = processed_df[processed_df["court_zone"] == zone]

        if len(zone_shots) == 0:
            continue

        total_shots = len(zone_shots)

        # Calculate success metrics
        shots_in = len(zone_shots[zone_shots["result"] == "In"])

        # For shots that landed "In", check if they helped win the point
        successful_points = 0
        for _, shot in zone_shots[zone_shots["result"] == "In"].iterrows():
            # Find the corresponding point outcome
            point_data = points[
                (points["match_id"] == shot["match_id"])
                & (points["set"] == shot["set"])
                & (points["game"] == shot["game"])
                & (points["point"] == shot["point"])
            ]

            if not point_data.empty and point_data.iloc[-1]["point_winner"] == HOST:
                successful_points += 1

        # Calculate error rate
        errors = len(zone_shots[zone_shots["result"].isin(["Out", "Net"])])

        # Success rate = shots that landed in AND won the point / total shots
        success_rate = successful_points / total_shots if total_shots > 0 else 0
        error_rate = errors / total_shots if total_shots > 0 else 0
        in_play_rate = shots_in / total_shots if total_shots > 0 else 0

        zone_analysis.append(
            {
                "Court Zone": zone,
                "Total Shots": total_shots,
                "Success Rate": success_rate,
                "Error Rate": error_rate,
                "In Play Rate": in_play_rate,
                "Successful Points": successful_points,
                "Errors": errors,
            }
        )

    df = pd.DataFrame(zone_analysis)

    if not df.empty:
        # Sort by success rate descending
        df = df.sort_values("Success Rate", ascending=False)

        # Add assessment column
        df["Assessment"] = df["Success Rate"].apply(
            lambda x: (
                "🟢 Strength" if x > 0.6 else "🟡 Good" if x > 0.4 else "🔴 Weakness"
            )
        )

    return df


def render_shot_analysis_tab(matches, points, shots):
    """Main function for the Shot Analysis tab"""
    st.header("🎾 Shot Analysis - Strengths and Weaknesses")

    # Shot Analysis Section
    st.subheader("Shot Effectiveness")
    col1, col2 = st.columns(2)

    with col1:
        st.write("**Best Shots (Strengths)**")
        good_shots = get_good_shots(shots)
        if not good_shots.empty:
            st.dataframe(
                good_shots.style.format(
                    {
                        "total_pct": "{:.1%}",
                        "win_pct": "{:.1%}",
                        "error_pct": "{:.1%}",
                    }
                ),
                use_container_width=True,
            )

    with col2:
        st.write("**Problematic Shots (Areas to Improve)**")
        bad_shots = get_bad_shots(shots)
        if not bad_shots.empty:
            st.dataframe(
                bad_shots.style.format(
                    {
                        "total_pct": "{:.1%}",
                        "error_pct": "{:.1%}",
                        "opp_win_pct": "{:.1%}",
                        "opp_win_count": "{:.0f}",
                    }
                ),
                use_container_width=True,
            )

    # Error vs Success Analysis
    st.subheader("🔍 Error vs Success Pattern Analysis")
    comparison_df = compare_error_vs_success_factors(shots)
    if not comparison_df.empty:
        st.write("**What conditions lead to errors vs success on your shots:**")
        st.dataframe(comparison_df, use_container_width=True)
    else:
        st.info("Not enough data for error vs success comparison analysis.")

    # Court Zone Analysis
    st.subheader("🎯 Court Zone Success Analysis")

    zone_analysis = analyze_court_zone_success(shots, points)
    if not zone_analysis.empty:
        # Display the zone analysis table
        st.dataframe(
            zone_analysis.style.format(
                {
                    "Success Rate": "{:.1%}",
                    "Error Rate": "{:.1%}",
                    "In Play Rate": "{:.1%}",
                }
            ),
            use_container_width=True,
        )

        # Key insights
        if len(zone_analysis) > 0:
            best_zone = zone_analysis.iloc[0]
            worst_zone = zone_analysis.iloc[-1]

            col1, col2 = st.columns(2)
            with col1:
                st.success(
                    f"""
                    🟢 **Strongest Zone**: {best_zone['Court Zone']}
                    ({best_zone['Success Rate']:.1%} success rate)
                    """
                )
            with col2:
                st.error(
                    f"""
                    🔴 **Weakest Zone**: {worst_zone['Court Zone']}
                    ({worst_zone['Success Rate']:.1%} success rate)
                    """
                )
    else:
        st.info("Not enough data for court zone analysis.")
