#!/usr/bin/env python3
"""Cohort Narrator - the retention triangle has three directions; the blended curve has none.

1. Synthesize 15 monthly signup cohorts of a consumer fintech app at user level and
   build the classic retention triangle (cohort x months-since-signup, % active).
   Three stories are injected: a product change lifting every cohort after it (vertical),
   a paid-traffic cohort that decays fast (a bad row), a calendar-month outage (a diagonal).
   Cohort sizes vary so the blended curve looks flat even though recent cohorts are better.
2. Engine: fit a baseline curve from the oldest cohorts, take each cell's residual
   vs baseline, then read the triangle one direction at a time - rows (a cohort
   below baseline on its own), vertical (a changepoint in age-matched residuals
   across signup months), diagonals (one calendar month across all cohorts).
   Compare size-weighted vs equal-weighted curves to size the mix effect, and
   project month-12 retention for the newest cohorts off the fitted curve.
3. Each finding becomes an *evidence pack*: type, cohort or month, age range,
   baseline vs observed at an anchor age, gap in pp, cohort size.
4. Narrate: with GEMINI_API_KEY or ANTHROPIC_API_KEY set, an LLM writes the two-line
   note per finding and the summary. Every number it writes is checked against the
   evidence pack; if it invents one, the deterministic template is used instead.
   Without a key you get the template. The triangle decides; the LLM only explains.

Run:  python cohort_narrator.py [--baseline-cohorts 6]
Out:  cohorts.md, triangle.png
"""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import llm  # noqa: E402

RNG = np.random.default_rng(11)
MAX_AGE = 12
COHORTS = [str(p) for p in pd.period_range("2025-07", "2026-09", freq="M")]
CUTOFF = pd.Period("2026-10", freq="M")                 # last complete calendar month
SIZES = [11200, 10800, 10400, 9900, 24000, 9100, 8300, 7600,   # paid burst in 2025-11
         4200, 3900, 4100, 3700, 3600, 3400, 3500]              # paid cut, organic only
PRODUCT_CHANGE, PAID_COHORT, OUTAGE_MONTH = "2026-03", "2025-11", "2026-06"
BLUE, RED = "#4A6FA5", "#d9534f"


def true_curve(age: np.ndarray) -> np.ndarray:
    """Power-law retention with a floor: 48% at month 1, 31% at month 3, 22% at month 12."""
    a = np.maximum(age, 1)
    return np.where(age == 0, 1.0, 0.18 + 0.30 * a ** -0.762)


def make_activity() -> tuple[pd.DataFrame, np.ndarray]:
    """User-level activity: users (user_id, cohort, channel) and a users x age 0/1 matrix (NaN = not yet observed)."""
    frames, mats = [], []
    ages = np.arange(MAX_AGE + 1)
    for cohort, n in zip(COHORTS, SIZES):
        p = true_curve(ages)[None, :] * RNG.lognormal(0, 0.45, n)[:, None]   # heterogeneous users
        if cohort >= PRODUCT_CHANGE:                                          # (a) vertical: better onboarding
            p = p * np.where(ages <= 3, 1.25, 1.08)
        if cohort == PAID_COHORT:                                             # (b) bad row: low-intent paid burst
            p = p * (0.75 * 0.93 ** np.maximum(ages - 1, 0))
        cal = pd.Period(cohort, freq="M") + ages
        p = p * np.where(cal == pd.Period(OUTAGE_MONTH, freq="M"), 0.80, 1.0)  # (c) diagonal: outage month
        act = (RNG.random((n, MAX_AGE + 1)) < np.clip(p, 0, 1)).astype(float)
        act[:, 0] = 1.0                                                       # active in the signup month
        act[:, cal > CUTOFF] = np.nan
        frames.append(pd.DataFrame({"cohort": [cohort] * n, "channel": "paid" if cohort == PAID_COHORT else "organic"}))
        mats.append(act)
    users = pd.concat(frames, ignore_index=True)
    users.insert(0, "user_id", [f"U{200000 + i}" for i in range(len(users))])
    return users, np.vstack(mats)


def triangle(users: pd.DataFrame, act: np.ndarray) -> pd.DataFrame:
    """Cohort x age, % active (NaN where the calendar month is not yet complete)."""
    t = pd.DataFrame(act, columns=range(MAX_AGE + 1)).groupby(users["cohort"].values).mean() * 100
    return t.loc[COHORTS].round(2)


def fit_curve(ages: np.ndarray, pct: np.ndarray) -> tuple[float, float, float]:
    """Least-squares fit of pct = c + b * age^-k on ages >= 1 by grid search over (c, k); b is closed form."""
    best = (np.inf, 0.0, 0.0, 0.0)
    for c in np.arange(0, 40.01, 0.25):
        for k in np.arange(0.1, 2.001, 0.01):
            x = ages ** -k
            b = ((pct - c) * x).sum() / (x * x).sum()
            sse = ((pct - c - b * x) ** 2).sum()
            if sse < best[0]:
                best = (sse, c, b, k)
    return best[1], best[2], best[3]


def baseline_curve(tri: pd.DataFrame, n_base: int) -> np.ndarray:
    """Fit on the per-age median of the oldest n_base cohorts (median = robust to one bad row)."""
    med = tri.iloc[:n_base, 1:].median()
    ages = np.array([a for a in med.index if not np.isnan(med[a])], dtype=float)
    c, b, k = fit_curve(ages, med[ages.astype(int)].values)
    return np.r_[100.0, c + b * np.arange(1, MAX_AGE + 1) ** -k]


def changepoint(x: np.ndarray, min_seg: int = 3) -> tuple[int, float]:
    """Single mean-shift changepoint: the split minimising two-segment SSE. Returns (index, shift)."""
    best, k_best = np.inf, min_seg
    for k in range(min_seg, len(x) - min_seg + 1):
        sse = ((x[:k] - x[:k].mean()) ** 2).sum() + ((x[k:] - x[k:].mean()) ** 2).sum()
        if sse < best:
            best, k_best = sse, k
    return k_best, float(x[k_best:].mean() - x[:k_best].mean())


def cell(tri: pd.DataFrame, base: np.ndarray, cohort: str, age: int, size: int) -> dict:
    return {"baseline_pct": round(float(base[age]), 1), "observed_pct": round(float(tri.loc[cohort, age]), 1),
            "gap_pp": round(float(tri.loc[cohort, age] - base[age]), 1), "cohort_size": size}


def find_rows(res: pd.DataFrame, tri: pd.DataFrame, base: np.ndarray, floor_pp: float = -3.0) -> list[dict]:
    """A row anomaly: one cohort consistently below baseline at >= 3 observed ages."""
    out = []
    for i, cohort in enumerate(COHORTS):
        r = res.loc[cohort, 1:].dropna()
        if len(r) >= 3 and r.mean() <= floor_pp and (r < 0).mean() >= 0.8:
            anchor = 3 if 3 in r.index else int(r.index.max())
            out.append({"type": "row", "cohort": cohort, "age_from": 1, "age_to": int(r.index.max()),
                        "anchor_age": anchor, **cell(tri, base, cohort, anchor, SIZES[i]),
                        "mean_gap_pp": round(float(r.mean()), 1), "worst_gap_pp": round(float(r.min()), 1)})
    return out


def find_vertical(res: pd.DataFrame, tri: pd.DataFrame, base: np.ndarray, skip: set[str],
                  ages: tuple[int, int] = (1, 3), min_shift_pp: float = 3.0) -> dict | None:
    """A vertical shift: every cohort signing up after some month sits above/below baseline at the same ages."""
    cols = list(range(ages[0], ages[1] + 1))
    s = res.loc[[c for c in COHORTS if c not in skip], cols].dropna().mean(axis=1)
    k, shift = changepoint(s.values)
    if abs(shift) < min_shift_pp:
        return None
    first = s.index[k]
    after = [c for c in COHORTS if c >= first and c not in skip]
    at3 = tri.loc[[c for c in after if not np.isnan(tri.loc[c, 3])], 3]
    return {"type": "vertical", "from_cohort": first, "cohorts_after": len(after), "age_from": ages[0],
            "age_to": ages[1], "anchor_age": 3, "baseline_pct": round(float(base[3]), 1),
            "observed_pct": round(float(at3.mean()), 1), "gap_pp": round(float(at3.mean() - base[3]), 1),
            "shift_pp": round(shift, 1), "cohort_size": int(sum(SIZES[COHORTS.index(c)] for c in after))}


def find_diagonals(adj: pd.DataFrame, res: pd.DataFrame, tri: pd.DataFrame, base: np.ndarray,
                   skip: set[str], floor_pp: float = -2.0) -> list[dict]:
    """A diagonal: the same calendar month across cohorts (cohort + age = constant).
    Detected on residuals with the vertical shift peeled off (adj); the anchor cell is the worst raw gap."""
    cells = [(c, a, pd.Period(c, freq="M") + a) for c in COHORTS if c not in skip
             for a in range(1, MAX_AGE + 1) if not np.isnan(res.loc[c, a])]
    out = []
    for month in sorted({m for _, _, m in cells}):
        here = [(c, a) for c, a, m in cells if m == month]
        g = np.array([adj.loc[c, a] for c, a in here])
        if len(g) >= 4 and g.mean() <= floor_pp and (g < 0).mean() >= 0.75:
            c, a = min(here, key=lambda ca: res.loc[ca[0], ca[1]])
            out.append({"type": "diagonal", "calendar_month": str(month), "cohorts_hit": len(here),
                        "age_from": min(a for _, a in here), "age_to": max(a for _, a in here),
                        "mean_gap_pp": round(float(g.mean()), 1), "anchor_cohort": c, "anchor_age": a,
                        **cell(tri, base, c, a, SIZES[COHORTS.index(c)])})
    return out


def aggregate(tri: pd.DataFrame, base: np.ndarray, vertical: dict | None, rows: list[dict]) -> dict:
    """Size-weighted (blended) vs equal-weighted curves, the mix gap, and month-12 projections."""
    sizes = pd.Series(SIZES, index=COHORTS)
    blended = (tri.mul(sizes, axis=0)).sum() / tri.notna().mul(sizes, axis=0).sum()
    equal = tri.mean()
    after = [c for c in COHORTS if vertical and c >= vertical["from_cohort"]]
    bad = [r["cohort"] for r in rows]
    out = {"curves": {"blended": blended.round(1).tolist(), "equal_weighted": equal.round(1).tolist(),
                      "baseline": np.round(base, 1).tolist()}}
    for m in (3, 6):
        obs = tri[m].dropna()
        w = sizes[obs.index] / sizes[obs.index].sum() * 100
        post = [c for c in after if c in obs.index]
        out[f"month_{m}"] = {
            "blended_pct": round(float(blended[m]), 1), "equal_weighted_pct": round(float(equal[m]), 1),
            "baseline_pct": round(float(base[m]), 1), "mix_gap_pp": round(float(equal[m] - blended[m]), 1),
            "cohorts_observed": int(len(obs)), "post_change_cohorts": len(post),
            "post_change_mean_pct": round(float(obs[post].mean()), 1) if post else None,
            "post_change_weight_pct": round(float(w[post].sum()), 1),
            "bad_row_weight_pct": round(float(w[[c for c in bad if c in obs.index]].sum()), 1)}
    proj = []
    for c in COHORTS[-5:]:
        last = int(tri.loc[c].dropna().index.max())
        proj.append({"cohort": c, "last_age": last, "observed_pct": round(float(tri.loc[c, last]), 1),
                     "projected_month_12_pct": round(float(base[12] * tri.loc[c, last] / base[last]), 1)})
    out["projection"] = {"baseline_month_12_pct": round(float(base[12]), 1), "latest_cohorts": proj}
    return out


# ----------------------------------------------------------------------------- narrative
def template_finding(ev: dict) -> str:
    t = ev["type"]
    if t == "row":
        return (f"Cohort {ev['cohort']} ({ev['cohort_size']:,} users) sits below baseline at every age "
                f"{ev['age_from']}-{ev['age_to']}: {ev['observed_pct']}% at month {ev['anchor_age']} vs "
                f"{ev['baseline_pct']}% ({ev['gap_pp']:+g} pp), worst gap {ev['worst_gap_pp']:+g} pp.\n"
                "Probably an acquisition-quality problem, not a product one - check the channel mix "
                f"for {ev['cohort']} signups.")
    if t == "vertical":
        return (f"Every cohort from {ev['from_cohort']} on ({ev['cohorts_after']} cohorts, "
                f"{ev['cohort_size']:,} users) retains better at months {ev['age_from']}-{ev['age_to']}: "
                f"{ev['observed_pct']}% at month {ev['anchor_age']} vs {ev['baseline_pct']}% baseline "
                f"({ev['gap_pp']:+g} pp).\nA sustained shift by signup month is a product or onboarding "
                f"change, not a traffic one - check what shipped around {ev['from_cohort']}.")
    return (f"Calendar month {ev['calendar_month']} is down across {ev['cohorts_hit']} cohorts at once "
            f"(ages {ev['age_from']}-{ev['age_to']}), mean gap {ev['mean_gap_pp']:+g} pp; worst cell is "
            f"cohort {ev['anchor_cohort']} at month {ev['anchor_age']}: {ev['observed_pct']}% vs "
            f"{ev['baseline_pct']}% ({ev['gap_pp']:+g} pp).\nOne month hitting every cohort is a calendar "
            f"event - an outage, a pricing change or a festival - not a cohort problem; check the incident "
            f"log for {ev['calendar_month']}.")


def template_summary(ev: dict) -> str:
    m3, m6, pj = ev["month_3"], ev["month_6"], ev["projection"]
    p12 = [p["projected_month_12_pct"] for p in pj["latest_cohorts"]]
    lo, hi = min(p12), max(p12)
    return (f"Blended month-3 retention is {m3['blended_pct']}% against a {m3['baseline_pct']}% baseline - "
            f"the headline reads flat. Equal-weighted it is {m3['equal_weighted_pct']}%, and the "
            f"{m3['post_change_cohorts']} cohorts since the product change average {m3['post_change_mean_pct']}%.\n"
            f"The aggregate hides this because the bad paid cohort carries {m3['bad_row_weight_pct']}% of "
            f"month-3 weight and the post-change cohorts only {m3['post_change_weight_pct']}%; at month 6 the "
            f"mix gap is {m6['mix_gap_pp']:+g} pp. On the fitted curve the latest 5 cohorts project to "
            f"{lo}-{hi}% at month 12 vs {pj['baseline_month_12_pct']}% baseline.")


SYSTEM_FINDING = """You write two-line notes on a retention cohort triangle for a consumer fintech growth team.
Line 1: what moved, where (cohort or calendar month and the age range), and how big - baseline vs observed, gap in pp.
Line 2: what it probably is. A row = one cohort acquired differently; a vertical shift = a product change for
everyone after a signup month; a diagonal = a calendar event hitting every cohort in one month.
Use ONLY numbers present in the evidence. Never compute, re-round or add numbers. No jargon about models."""

SYSTEM_SUMMARY = """You write a two-line summary of what a blended retention curve hides, for a consumer fintech growth team.
Line 1: blended vs equal-weighted vs baseline at month 3, and what the post-change cohorts actually do.
Line 2: why the aggregate hides it (cohort-size weights) and the month-12 projection for the latest cohorts.
Use ONLY numbers present in the evidence. Never compute, re-round or add numbers."""


def narrate(ev: dict, system: str, template) -> tuple[str, str]:
    text = llm.complete(system, json.dumps(ev, indent=2), max_tokens=300)
    if text is None:
        return template(ev), "template (no API key)"
    bad = llm.unpinned(text, ev)
    if bad:
        return template(ev), f"template (LLM invented numbers: {sorted(bad)})"
    return text, f"llm ({llm.provider()})"


# ----------------------------------------------------------------------------- chart
def plot(tri: pd.DataFrame, res: pd.DataFrame, agg: dict, findings: list[dict]):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    from matplotlib.patches import Rectangle

    cmap = LinearSegmentedColormap.from_list("div", [RED, "#f2f2f2", BLUE])
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(14, 6.2), gridspec_kw={"width_ratios": [1.5, 1]})
    im = ax.imshow(res.values, cmap=cmap, vmin=-15, vmax=15, aspect="auto")
    for (i, a), v in np.ndenumerate(tri.values):
        if not np.isnan(v):
            ax.text(a, i, f"{v:.0f}", ha="center", va="center", fontsize=6.5, color="#333")
    for f in findings:
        if f["type"] == "row":
            ax.add_patch(Rectangle((0.5, COHORTS.index(f["cohort"]) - 0.5), MAX_AGE, 1, fill=False, ec=RED, lw=1.8))
        elif f["type"] == "vertical":
            i = COHORTS.index(f["from_cohort"])
            ax.add_patch(Rectangle((f["age_from"] - 0.5, i - 0.5), f["age_to"] - f["age_from"] + 1,
                                   len(COHORTS) - i, fill=False, ec=BLUE, lw=1.8, ls="--"))
        else:
            m = pd.Period(f["calendar_month"], freq="M")
            for i, c in enumerate(COHORTS):
                a = (m - pd.Period(c, freq="M")).n
                if 1 <= a <= MAX_AGE:
                    ax.add_patch(Rectangle((a - 0.5, i - 0.5), 1, 1, fill=False, ec="#333", lw=1.2))
    ax.set_xticks(range(MAX_AGE + 1)); ax.set_yticks(range(len(COHORTS))); ax.set_yticklabels(COHORTS, fontsize=8)
    ax.set_xlabel("months since signup"); ax.set_ylabel("signup cohort")
    ax.set_title("Retention triangle: % active, coloured by gap vs baseline (pp)", fontsize=10)
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02).set_label("pp vs baseline", fontsize=8)

    ages = range(MAX_AGE + 1)
    n_obs = tri.notna().sum()                       # aggregate curves only where >= 6 cohorts contribute
    agg_ages = [a for a in ages if n_obs[a] >= 6]
    ax2.plot(ages, agg["curves"]["baseline"], color="#999", lw=1.5, ls=":", label="baseline (fitted, oldest cohorts)")
    ax2.plot(agg_ages, [agg["curves"]["blended"][a] for a in agg_ages], color=BLUE, lw=2, label="blended (size-weighted)")
    ax2.plot(agg_ages, [agg["curves"]["equal_weighted"][a] for a in agg_ages], color="#333", lw=2, ls="--",
             label="equal-weighted")
    for m in (3, 6):
        ax2.plot([m, m], [agg["curves"]["blended"][m], agg["curves"]["equal_weighted"][m]], color=RED, lw=3, alpha=0.8)
        ax2.annotate(f"{agg[f'month_{m}']['mix_gap_pp']:+g} pp", (m, agg["curves"]["equal_weighted"][m]),
                     xytext=(6, 4), textcoords="offset points", fontsize=8, color="#333")
    ax2.set_ylim(0, 60); ax2.set_xlim(0.5, MAX_AGE + 0.5); ax2.set_xlabel("months since signup"); ax2.set_ylabel("% active")
    ax2.set_title(f"Aggregate curve to month {agg_ages[-1]}: the mix gap at months 3 and 6", fontsize=10)
    ax2.grid(alpha=0.2); ax2.legend(fontsize=8, frameon=False)
    plt.tight_layout()
    plt.savefig("triangle.png", dpi=130)


# ----------------------------------------------------------------------------- main
def analyse(n_base: int = 6) -> tuple[pd.DataFrame, pd.DataFrame, list[dict], dict]:
    users, act = make_activity()
    tri = triangle(users, act)
    base = baseline_curve(tri, n_base)
    res = tri - base
    rows = find_rows(res, tri, base)
    skip = {r["cohort"] for r in rows}
    vert = find_vertical(res, tri, base, skip)
    adj = res.copy()                                   # peel the vertical shift before reading diagonals
    if vert:
        after = [c for c in COHORTS if c >= vert["from_cohort"] and c not in skip]
        adj.loc[after] = adj.loc[after] - adj.loc[after].mean()
    diags = find_diagonals(adj, res, tri, base, skip)
    findings = rows + ([vert] if vert else []) + diags
    return tri, res, findings, aggregate(tri, base, vert, rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline-cohorts", type=int, default=6, help="oldest cohorts used to fit the baseline")
    args = ap.parse_args()
    tri, res, findings, agg = analyse(args.baseline_cohorts)
    print(f"{len(COHORTS)} cohorts · {sum(SIZES):,} users · {int(tri.notna().sum().sum())} triangle cells · "
          f"{len(findings)} findings · LLM provider: {llm.provider()}\n")

    out = ["# Cohort notes", "", "Retention triangle read in three directions (rows, vertical, diagonals) "
           f"against a baseline fitted on the oldest {args.baseline_cohorts} cohorts. Notes written by: "
           f"{llm.provider()}; every number verified against the evidence pack.", ""]
    for ev in findings:
        where = ev.get("cohort") or ev.get("from_cohort") or ev.get("calendar_month")
        note, src = narrate(ev, SYSTEM_FINDING, template_finding)
        print(f"── {ev['type']}  {where}  [{src}]")
        print(note, "\n")
        out += [f"## {ev['type'].title()}: {where}", "", note, "", f"*source: {src}*", "",
                "<details><summary>evidence</summary>", "", "```json", json.dumps(ev, indent=2), "```",
                "</details>", ""]
    summary, src = narrate(agg, SYSTEM_SUMMARY, template_summary)
    print(f"── what the aggregate hides  [{src}]")
    print(summary, "\n")
    out += ["## What the aggregate hides", "", summary, "", f"*source: {src}*", "",
            "<details><summary>evidence</summary>", "", "```json", json.dumps(agg, indent=2), "```",
            "</details>", ""]
    Path("cohorts.md").write_text("\n".join(out), encoding="utf-8")
    plot(tri, res, agg, findings)
    print("wrote cohorts.md and triangle.png")


if __name__ == "__main__":
    main()
