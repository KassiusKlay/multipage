"""
Decision Coach — match diagnosis, shot sequences, and training priorities.
"""

import pandas as pd
import streamlit as st

from .data_processing import HOST, resolve_match_won, STATUS_LABELS, is_completed_status

SERVE_TYPES = {"first_serve", "second_serve"}
RETURN_TYPES = {"first_return", "second_return"}
PLUS_ONE = {"serve_plus_one", "return_plus_one"}
DIRECTION_CHANGE_PAIRS = {
    ("cross court", "down the line"),
    ("down the line", "cross court"),
    ("inside out", "down the line"),
    ("inside in", "cross court"),
}


def _clean_point_shots(point_shots: pd.DataFrame) -> pd.DataFrame:
    """Drop feeds and keep chronological unique strokes for sequence work."""
    df = point_shots.sort_values(["shot", "video_time"]).copy()
    df = df[df["stroke"] != "Feed"]
    # Drop Type==none noise unless it's the only event at that shot#
    # Keep serves/returns/in_play/+1; allow none only if stroke is real groundstroke
    # between serve attempts (rare) — exclude none Serve-like noise
    mask = df["type"].isin(
        SERVE_TYPES | RETURN_TYPES | PLUS_ONE | {"in_play"}
    ) | (
        (df["type"] == "none")
        & df["stroke"].isin(["Forehand", "Backhand", "Volley", "Overhead"])
    )
    df = df[mask]
    return df.drop_duplicates(subset=["video_time", "player", "type", "result"])


def _rally_length(point_shots: pd.DataFrame) -> int:
    strokes = point_shots[~point_shots["stroke"].isin(["Feed", "Serve"])]
    return len(strokes)


def _net_points_breakdown(match_points: pd.DataFrame) -> dict:
    won = match_points[match_points["point_winner"] == HOST]
    lost = match_points[match_points["point_winner"] != HOST]

    my_winners = len(
        won[won["detail"].isin(["Forehand Winner", "Backhand Winner", "Ace"])]
    )
    # service winners counted separately for narrative clarity
    my_service_winners = len(won[won["detail"] == "Service Winner"])
    opp_errors = len(
        won[
            won["detail"].isin(
                [
                    "Forehand Unforced Error",
                    "Backhand Unforced Error",
                    "Double Fault",
                ]
            )
        ]
    )
    my_errors = len(
        lost[
            lost["detail"].isin(
                ["Forehand Unforced Error", "Backhand Unforced Error"]
            )
        ]
    )
    my_dfs = len(lost[lost["detail"] == "Double Fault"])
    blank_lost = int(lost["detail_blank"].sum()) if "detail_blank" in lost else 0
    blank_won = int(won["detail_blank"].sum()) if "detail_blank" in won else 0

    positive = my_winners + my_service_winners + opp_errors
    negative = my_errors + my_dfs
    return {
        "my_winners": my_winners,
        "my_service_winners": my_service_winners,
        "opp_errors": opp_errors,
        "my_errors": my_errors,
        "my_dfs": my_dfs,
        "blank_lost": blank_lost,
        "blank_won": blank_won,
        "positive": positive,
        "negative": negative,
        "net_points": positive - negative,
        "fh_errors": len(lost[lost["detail"] == "Forehand Unforced Error"]),
        "bh_errors": len(lost[lost["detail"] == "Backhand Unforced Error"]),
        "fh_winners": len(won[won["detail"] == "Forehand Winner"]),
        "bh_winners": len(won[won["detail"] == "Backhand Winner"]),
    }


def diagnose_match(match_id, matches, points, shots) -> dict:
    match = matches[matches["match_id"].astype(str) == str(match_id)].iloc[0]
    match_points = points[points["match_id"].astype(str) == str(match_id)]
    match_shots = shots[shots["match_id"].astype(str) == str(match_id)]

    total = len(match_points)
    won_n = len(match_points[match_points["point_winner"] == HOST])
    pct = won_n / total if total else 0
    won = resolve_match_won(match, pct)

    np = _net_points_breakdown(match_points)

    # Rally length leaks
    rally_rows = []
    for (s, g, p), grp in match_shots.groupby(["set", "game", "point"]):
        clean = _clean_point_shots(grp)
        length = _rally_length(clean)
        pt = match_points[
            (match_points["set"] == s)
            & (match_points["game"] == g)
            & (match_points["point"] == p)
        ]
        if pt.empty:
            continue
        rally_rows.append(
            {
                "rally_length": length,
                "won": pt.iloc[0]["point_winner"] == HOST,
                "detail": pt.iloc[0]["detail"],
            }
        )
    rally_df = pd.DataFrame(rally_rows)
    rally_summary = {}
    if not rally_df.empty:
        bins = [(0, 2, "0–2"), (3, 6, "3–6"), (7, 12, "7–12"), (13, 999, "13+")]
        for lo, hi, label in bins:
            sub = rally_df[
                (rally_df["rally_length"] >= lo) & (rally_df["rally_length"] <= hi)
            ]
            if len(sub) == 0:
                continue
            rally_summary[label] = {
                "points": len(sub),
                "won_pct": sub["won"].mean(),
                "lost": int((~sub["won"]).sum()),
            }

    # Serve / return
    serving = match_points[match_points["match_server"] == HOST]
    returning = match_points[match_points["match_server"] != HOST]
    first_serve_pts = serving[serving["serve_state"] == "first"]
    second_serve_pts = serving[serving["serve_state"] == "second"]

    serve_stats = {
        "serve_won_pct": (serving["point_winner"] == HOST).mean()
        if len(serving)
        else None,
        "return_won_pct": (returning["point_winner"] == HOST).mean()
        if len(returning)
        else None,
        "first_serve_won_pct": (first_serve_pts["point_winner"] == HOST).mean()
        if len(first_serve_pts)
        else None,
        "second_serve_won_pct": (second_serve_pts["point_winner"] == HOST).mean()
        if len(second_serve_pts)
        else None,
        "second_serve_points": len(second_serve_pts),
    }

    # Late match (last set)
    last_set = match_points["set"].max() if not match_points.empty else None
    late = {}
    if last_set is not None and match_points["set"].nunique() > 1:
        early = match_points[match_points["set"] < last_set]
        late_pts = match_points[match_points["set"] == last_set]
        late = {
            "early_won_pct": (early["point_winner"] == HOST).mean()
            if len(early)
            else None,
            "late_won_pct": (late_pts["point_winner"] == HOST).mean()
            if len(late_pts)
            else None,
            "last_set": int(last_set),
        }

    paragraphs = _build_diagnosis_text(
        match, won, pct, np, rally_summary, serve_stats, late
    )

    return {
        "match": match,
        "won": won,
        "points_won_pct": pct,
        "net": np,
        "rally_summary": rally_summary,
        "serve_stats": serve_stats,
        "late": late,
        "paragraphs": paragraphs,
    }


def _fmt_pct(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "n/a"
    return f"{x:.0%}"


def _build_diagnosis_text(match, won, pct, np, rally_summary, serve_stats, late):
    opponent = match.get("guest_team", "opponent")
    scoreline = match.get("scoreline") or ""
    status = match.get("match_status", "completed")
    if not is_completed_status(status):
        label = STATUS_LABELS.get(str(status), str(status))
        result = f"played an incomplete match ({label})"
    elif won:
        result = "won"
    elif won is False:
        result = "lost"
    else:
        result = "played"
    lines = []

    head = f"You {result} vs {opponent}"
    if scoreline:
        head += f" ({scoreline})"
    head += f", taking {pct:.0%} of points."
    lines.append(head)
    if not is_completed_status(status):
        lines.append(
            "This match has no official result — stats below still count for "
            "pattern analysis and training priorities, but not win/loss rate."
        )

    net = np["net_points"]
    if net >= 0:
        lines.append(
            f"Net Points were +{net}: you created {np['positive']} points "
            f"({np['my_winners']} winners, {np['my_service_winners']} service winners, "
            f"{np['opp_errors']} opponent errors) and gave away {np['negative']} "
            f"({np['my_errors']} UEs, {np['my_dfs']} double faults)."
        )
    else:
        lines.append(
            f"Net Points were {net}: you gave away {np['negative']} points through "
            f"errors/DFs versus {np['positive']} created "
            f"({np['fh_errors']} FH UEs, {np['bh_errors']} BH UEs, {np['my_dfs']} DFs)."
        )

    if np["blank_lost"] or np["blank_won"]:
        lines.append(
            f"Note: {np['blank_lost'] + np['blank_won']} points have blank Detail "
            f"({np['blank_lost']} lost, {np['blank_won']} won) and are excluded from "
            f"winner/error Net Points components."
        )

    # Worst rally bucket among those with enough points
    if rally_summary:
        worst = min(
            (
                (label, data)
                for label, data in rally_summary.items()
                if data["points"] >= 5
            ),
            key=lambda x: x[1]["won_pct"],
            default=None,
        )
        if worst:
            label, data = worst
            lines.append(
                f"By rally length, your weakest band was {label} shots "
                f"({data['lost']} points lost, {_fmt_pct(data['won_pct'])} won)."
            )

    if serve_stats.get("second_serve_won_pct") is not None:
        lines.append(
            f"Serve points won {_fmt_pct(serve_stats['serve_won_pct'])} overall; "
            f"first-serve points {_fmt_pct(serve_stats['first_serve_won_pct'])}, "
            f"second-serve points {_fmt_pct(serve_stats['second_serve_won_pct'])} "
            f"({serve_stats['second_serve_points']} second-serve points). "
            f"Return points won {_fmt_pct(serve_stats['return_won_pct'])}."
        )

    if late.get("late_won_pct") is not None and late.get("early_won_pct") is not None:
        delta = late["late_won_pct"] - late["early_won_pct"]
        if abs(delta) >= 0.08:
            direction = "dropped" if delta < 0 else "rose"
            lines.append(
                f"Points won {direction} from {_fmt_pct(late['early_won_pct'])} "
                f"before set {late['last_set']} to {_fmt_pct(late['late_won_pct'])} "
                f"in the final set."
            )

    return lines


@st.cache_data
def analyze_sequences(points, shots, match_id=None) -> dict:
    """Serve→+1, return→outcome, and direction-change error patterns."""
    pts = points
    sh = shots
    if match_id is not None:
        pts = points[points["match_id"].astype(str) == str(match_id)]
        sh = shots[shots["match_id"].astype(str) == str(match_id)]

    serve_plus_one = []
    return_patterns = []
    direction_changes = []

    for (mid, s, g, p), grp in sh.groupby(["match_id", "set", "game", "point"]):
        clean = _clean_point_shots(grp)
        if clean.empty:
            continue
        pt = pts[
            (pts["match_id"] == mid)
            & (pts["set"] == s)
            & (pts["game"] == g)
            & (pts["point"] == p)
        ]
        if pt.empty:
            continue
        won = pt.iloc[0]["point_winner"] == HOST
        i_served = pt.iloc[0]["match_server"] == HOST

        my_rows = clean[clean["player"] == HOST]
        # Serve + 1 when I serve
        serve = my_rows[my_rows["type"].isin(SERVE_TYPES) & (my_rows["result"] == "In")]
        plus = my_rows[my_rows["type"] == "serve_plus_one"]
        if i_served and not serve.empty:
            serve_row = serve.iloc[-1]
            plus_dir = plus.iloc[0]["direction"] if not plus.empty else None
            plus_stroke = plus.iloc[0]["stroke"] if not plus.empty else None
            plus_result = plus.iloc[0]["result"] if not plus.empty else None
            serve_plus_one.append(
                {
                    "serve_type": serve_row["type"],
                    "serve_dir": serve_row["direction"],
                    "plus_stroke": plus_stroke,
                    "plus_dir": plus_dir,
                    "plus_result": plus_result,
                    "won": won,
                }
            )

        # Return → outcome
        ret = my_rows[my_rows["type"].isin(RETURN_TYPES)]
        if not i_served and not ret.empty:
            r = ret.iloc[0]
            return_patterns.append(
                {
                    "return_type": r["type"],
                    "direction": r["direction"],
                    "stroke": r["stroke"],
                    "bounce_depth": r.get("bounce_depth"),
                    "result": r["result"],
                    "won": won,
                }
            )

        # Direction changes on my consecutive groundstrokes
        ground = my_rows[
            my_rows["stroke"].isin(["Forehand", "Backhand"])
            & my_rows["direction"].notna()
            & (my_rows["direction"] != "---")
        ].sort_values("shot")
        prev = None
        for _, row in ground.iterrows():
            if prev is not None:
                pair = (prev["direction"], row["direction"])
                changed = pair in DIRECTION_CHANGE_PAIRS or (
                    prev["direction"] != row["direction"]
                )
                if changed:
                    direction_changes.append(
                        {
                            "stroke": row["stroke"],
                            "from_dir": prev["direction"],
                            "to_dir": row["direction"],
                            "result": row["result"],
                            "error": row["result"] in ("Out", "Net"),
                        }
                    )
            prev = row

    def _rate_table(rows, group_cols, success_col="won"):
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        g = (
            df.groupby(group_cols, dropna=False)
            .agg(n=(success_col, "size"), won=(success_col, "sum"))
            .reset_index()
        )
        g["won_pct"] = g["won"] / g["n"]
        return g.sort_values(["n", "won_pct"], ascending=[False, False])

    spo = _rate_table(
        serve_plus_one,
        ["serve_type", "serve_dir", "plus_stroke", "plus_dir"],
    )
    ret = _rate_table(
        return_patterns, ["return_type", "stroke", "direction", "bounce_depth"]
    )

    dir_df = pd.DataFrame(direction_changes)
    if not dir_df.empty:
        dir_summary = (
            dir_df.groupby(["stroke", "from_dir", "to_dir"])
            .agg(n=("error", "size"), errors=("error", "sum"))
            .reset_index()
        )
        dir_summary["error_pct"] = dir_summary["errors"] / dir_summary["n"]
        dir_summary = dir_summary.sort_values(
            ["n", "error_pct"], ascending=[False, False]
        )
    else:
        dir_summary = pd.DataFrame()

    return {
        "serve_plus_one": spo,
        "returns": ret,
        "direction_changes": dir_summary,
        "raw_counts": {
            "serve_plus_one": len(serve_plus_one),
            "returns": len(return_patterns),
            "direction_changes": len(direction_changes),
        },
    }


def _priority_candidates(points, shots) -> list:
    """Score leak categories across the provided points/shots window."""
    candidates = []
    if points.empty:
        return candidates

    lost = points[points["point_winner"] != HOST]
    n_sets = max(points.groupby("match_id")["set"].nunique().sum(), 1)

    fh = len(lost[lost["detail"] == "Forehand Unforced Error"])
    bh = len(lost[lost["detail"] == "Backhand Unforced Error"])
    dfs = len(lost[lost["detail"] == "Double Fault"])

    if fh:
        candidates.append(
            {
                "key": "fh_ue",
                "title": "Forehand tolerance (unforced errors)",
                "impact": fh,
                "per_set": fh / n_sets,
                "detail": f"{fh} FH UEs (~{fh / n_sets:.1f} per set).",
            }
        )
    if bh:
        candidates.append(
            {
                "key": "bh_ue",
                "title": "Backhand tolerance (unforced errors)",
                "impact": bh,
                "per_set": bh / n_sets,
                "detail": f"{bh} BH UEs (~{bh / n_sets:.1f} per set).",
            }
        )
    if dfs:
        candidates.append(
            {
                "key": "df",
                "title": "Second-serve / double-fault control",
                "impact": dfs,
                "per_set": dfs / n_sets,
                "detail": f"{dfs} double faults (~{dfs / n_sets:.1f} per set).",
            }
        )

    # Second serve points won
    seconds = points[
        (points["match_server"] == HOST) & (points["serve_state"] == "second")
    ]
    if len(seconds) >= 8:
        won_pct = (seconds["point_winner"] == HOST).mean()
        if won_pct < 0.45:
            leak = int((seconds["point_winner"] != HOST).sum())
            candidates.append(
                {
                    "key": "second_serve_pts",
                    "title": "Second-serve point toughness",
                    "impact": leak,
                    "per_set": leak / n_sets,
                    "detail": f"Won only {won_pct:.0%} of {len(seconds)} second-serve points.",
                }
            )

    # Return depth: short returns when returning
    my_returns = shots[
        (shots["player"] == HOST)
        & (shots["type"].isin(RETURN_TYPES))
        & (shots["result"] == "In")
    ]
    if len(my_returns) >= 10:
        short = my_returns[my_returns["bounce_depth"] == "short"]
        # Join to point outcomes
        merged = short.merge(
            points[["match_id", "set", "game", "point", "point_winner"]],
            on=["match_id", "set", "game", "point"],
            how="left",
        )
        if len(merged) >= 5:
            lose_pct = (merged["point_winner"] != HOST).mean()
            if lose_pct >= 0.55:
                candidates.append(
                    {
                        "key": "short_return",
                        "title": "Return depth (too many short returns)",
                        "impact": int((merged["point_winner"] != HOST).sum()),
                        "per_set": int((merged["point_winner"] != HOST).sum()) / n_sets,
                        "detail": (
                            f"{len(merged)} short in-play returns; lost "
                            f"{lose_pct:.0%} of those points."
                        ),
                    }
                )

    # Neutral rally FH errors (rally 3-6, FH UE)
    mid_errors = 0
    for (mid, s, g, p), grp in shots.groupby(["match_id", "set", "game", "point"]):
        clean = _clean_point_shots(grp)
        length = _rally_length(clean)
        if not (3 <= length <= 6):
            continue
        pt = points[
            (points["match_id"] == mid)
            & (points["set"] == s)
            & (points["game"] == g)
            & (points["point"] == p)
        ]
        if pt.empty:
            continue
        if (
            pt.iloc[0]["point_winner"] != HOST
            and pt.iloc[0]["detail"] == "Forehand Unforced Error"
        ):
            mid_errors += 1
    if mid_errors >= 3:
        candidates.append(
            {
                "key": "neutral_fh",
                "title": "Neutral forehand (errors in 3–6 shot rallies)",
                "impact": mid_errors,
                "per_set": mid_errors / n_sets,
                "detail": f"{mid_errors} FH UEs in medium-length rallies.",
            }
        )

    candidates.sort(key=lambda c: c["impact"], reverse=True)
    return candidates


def compute_priorities(matches, points, shots, recent_n=5) -> dict:
    """Top 1–2 priorities from recent matches vs previous window."""
    if matches.empty:
        return {"priorities": [], "progress": []}

    ordered = matches.sort_values("match_date")
    recent = ordered.tail(recent_n)
    previous = ordered.iloc[: -recent_n].tail(recent_n) if len(ordered) > recent_n else None

    recent_ids = set(recent["match_id"].astype(str))
    recent_pts = points[points["match_id"].astype(str).isin(recent_ids)]
    recent_shots = shots[shots["match_id"].astype(str).isin(recent_ids)]
    recent_cands = _priority_candidates(recent_pts, recent_shots)
    priorities = recent_cands[:2]

    progress = []
    if previous is not None and not previous.empty:
        prev_ids = set(previous["match_id"].astype(str))
        prev_cands = {
            c["key"]: c
            for c in _priority_candidates(
                points[points["match_id"].astype(str).isin(prev_ids)],
                shots[shots["match_id"].astype(str).isin(prev_ids)],
            )
        }
        for p in priorities:
            before = prev_cands.get(p["key"])
            if not before:
                progress.append(
                    {
                        "title": p["title"],
                        "status": "new focus",
                        "note": "Not a top leak in the prior window.",
                    }
                )
                continue
            # Compare per-set rate
            delta = p["per_set"] - before["per_set"]
            if delta < -0.15:
                status = "improving"
            elif delta > 0.15:
                status = "worsening"
            else:
                status = "stable"
            progress.append(
                {
                    "title": p["title"],
                    "status": status,
                    "note": (
                        f"Per-set impact {before['per_set']:.1f} → {p['per_set']:.1f} "
                        f"(previous {len(previous)} vs recent {len(recent)} matches)."
                    ),
                }
            )

    return {
        "priorities": priorities,
        "progress": progress,
        "recent_matches": len(recent),
        "previous_matches": 0 if previous is None else len(previous),
    }


def _weekly_plan(priority: dict) -> list:
    key = priority["key"]
    plans = {
        "fh_ue": [
            "Technical: shadow FH with early unit turn, finish over the shoulder.",
            "Consistency: crosscourt FH cooperatively, 20-ball targets, no winners.",
            "Tactical: in neutral, default FH crosscourt; change direction only on a short ball.",
            "Match target: ≤ 3 FH UEs per set.",
        ],
        "bh_ue": [
            "Technical: BH contact out in front; reduce late wrist flips.",
            "Consistency: BH crosscourt depth boxes, 2×8 minutes.",
            "Tactical: when pressured, slice BH high and deep instead of flat DTL.",
            "Match target: ≤ 2 BH UEs per set.",
        ],
        "df": [
            "Technical: kick/second-serve toss consistency — same placement every rep.",
            "Consistency: 30 second serves to T / 30 wide, track % in.",
            "Tactical: on ad court break points, prefer high percentage T serve.",
            "Match target: ≤ 1 double fault per set.",
        ],
        "second_serve_pts": [
            "Technical: second-serve shape first, pace second.",
            "Consistency: serve + 1 pattern: second serve → FH to open court.",
            "Tactical: after second serve, first ball crosscourt; avoid immediate DTL.",
            "Match target: win ≥ 50% of second-serve points.",
        ],
        "short_return": [
            "Technical: return split-step + compact swing; prioritize depth over pace.",
            "Consistency: return feeds deep to middle, land past service line.",
            "Tactical: on second-serve returns, aim deep middle/BH; delay direction change.",
            "Match target: < 30% of returns bouncing short.",
        ],
        "neutral_fh": [
            "Technical: FH from neutral stance, recover to center after each ball.",
            "Consistency: 3–6 ball FH rallies, reset feet every shot.",
            "Tactical: build with CC; attack only when bounce is short.",
            "Match target: cut FH UEs in 3–6 shot rallies by half.",
        ],
    }
    return plans.get(
        key,
        [
            "Technical: one focused quality (contact / balance).",
            "Consistency: cooperative rallying on the priority stroke.",
            "Tactical: one pattern to rehearse under mild pressure.",
            "Match target: measurable reduction next match.",
        ],
    )


def render_decision_coach_tab(matches, points, shots, sets=None):
    st.header("🧭 Decision Coach")
    st.caption(
        "Why points were won or lost, which patterns matter, and what to train next."
    )

    if matches.empty:
        st.warning("No matches available.")
        return

    ordered = matches.sort_values("match_date", ascending=False)
    labels = ordered.apply(
        lambda r: f"{r['match_date']} vs {r['guest_team']}"
        + (f" ({r['scoreline']})" if r.get("scoreline") else ""),
        axis=1,
    ).tolist()

    idx = st.selectbox(
        "Match for diagnosis",
        range(len(labels)),
        format_func=lambda i: labels[i],
    )
    match_id = ordered.iloc[idx]["match_id"]

    diagnosis = diagnose_match(match_id, matches, points, shots)

    st.subheader("Match diagnosis")
    for p in diagnosis["paragraphs"]:
        st.markdown(f"- {p}")

    np = diagnosis["net"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Net Points", np["net_points"])
    c2.metric("Created", np["positive"])
    c3.metric("Given away", np["negative"])
    c4.metric(
        "Blank Detail",
        np["blank_lost"] + np["blank_won"],
        help="Points with empty Detail excluded from winner/error components",
    )

    if diagnosis["rally_summary"]:
        st.subheader("Rally length")
        rally_df = pd.DataFrame(
            [
                {
                    "Rally": k,
                    "Points": v["points"],
                    "Won %": v["won_pct"],
                    "Lost": v["lost"],
                }
                for k, v in diagnosis["rally_summary"].items()
            ]
        )
        st.dataframe(
            rally_df.style.format({"Won %": "{:.0%}"}),
            width="stretch",
            hide_index=True,
        )

    st.subheader("Tactical patterns")
    scope = st.radio(
        "Sequence scope",
        ["This match", "All matches"],
        horizontal=True,
    )
    seq_match = match_id if scope == "This match" else None
    seq = analyze_sequences(points, shots, seq_match)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Serve → plus-one**")
        spo = seq["serve_plus_one"]
        if spo.empty:
            st.info("Not enough serve+1 data.")
        else:
            show = spo[spo["n"] >= 2].head(12)
            if show.empty:
                show = spo.head(8)
            st.dataframe(
                show.style.format({"won_pct": "{:.0%}"}),
                width="stretch",
                hide_index=True,
            )

    with col_b:
        st.markdown("**Return → point outcome**")
        ret = seq["returns"]
        if ret.empty:
            st.info("Not enough return data.")
        else:
            show = ret[ret["n"] >= 2].head(12)
            if show.empty:
                show = ret.head(8)
            st.dataframe(
                show.style.format({"won_pct": "{:.0%}"}),
                width="stretch",
                hide_index=True,
            )

    st.markdown("**Direction-change errors**")
    dchg = seq["direction_changes"]
    if dchg.empty:
        st.info("Not enough direction-change samples.")
    else:
        show = dchg[dchg["n"] >= 2].head(12)
        if show.empty:
            show = dchg.head(8)
        st.dataframe(
            show.style.format({"error_pct": "{:.0%}"}),
            width="stretch",
            hide_index=True,
        )

    st.subheader("Training priorities")
    recent_n = st.slider("Recent match window", 3, 10, 5)
    pri = compute_priorities(matches, points, shots, recent_n=recent_n)

    if not pri["priorities"]:
        st.success("No clear high-impact leaks in the recent window.")
        return

    for i, p in enumerate(pri["priorities"]):
        label = "Primary" if i == 0 else "Secondary"
        st.markdown(f"**{label} priority: {p['title']}**")
        st.write(p["detail"])
        st.markdown("Weekly plan:")
        for item in _weekly_plan(p):
            st.markdown(f"- {item}")

    if pri["progress"]:
        st.subheader("Is it improving?")
        for g in pri["progress"]:
            emoji = {
                "improving": "✅",
                "worsening": "⚠️",
                "stable": "➖",
                "new focus": "🆕",
            }.get(g["status"], "•")
            st.markdown(f"{emoji} **{g['title']}** — {g['status']}: {g['note']}")
