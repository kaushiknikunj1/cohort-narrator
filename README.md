# Cohort Narrator

The blended retention curve is the most reassuring and least informative chart in the company. I have watched it sit flat for two quarters while the product team shipped the best onboarding change in the app's history — and I have watched it sit flat while a paid-acquisition burst quietly bought twenty thousand users who were gone by month three. Same chart, same shape, opposite news.

The triangle underneath it has three directions, and each one is a different kind of news. A **row** is one cohort behaving differently — an acquisition story. A **vertical** band is every cohort after a signup month behaving differently — a product story. A **diagonal** is every cohort in one calendar month — an incident or a festival. The blended curve averages all three into one line, weighted by whoever you happened to acquire the most of.

This project reads the triangle direction by direction, says which cohorts bent and when, and then says in plain numbers what the aggregate curve was hiding. A language model writes the notes — and is not allowed to invent a number.

```
── vertical  2026-03  [template (no API key)]
Every cohort from 2026-03 on (7 cohorts, 26,400 users) retains better at months 1-3: 41.3% at month 3 vs 33.9% baseline (+7.4 pp).
A sustained shift by signup month is a product or onboarding change, not a traffic one - check what shipped around 2026-03.

── what the aggregate hides  [template (no API key)]
Blended month-3 retention is 33.0% against a 33.9% baseline - the headline reads flat. Equal-weighted it is 36.1%, and the 5 cohorts since the product change average 41.3%.
The aggregate hides this because the bad paid cohort carries 21.7% of month-3 weight and the post-change cohorts only 17.6%; at month 6 the mix gap is +2.1 pp. On the fitted curve the latest 5 cohorts project to 26.0-30.8% at month 12 vs 24.6% baseline.
```

That is the deterministic template. With an API key the same evidence pack goes to an LLM, which writes it in plainer English — and is then checked.

## How it works

1. **Data.** Fifteen monthly signup cohorts of a consumer fintech app, 117,700 synthetic users, each with a month-by-month active flag — enough to build the classic triangle (cohort × months since signup, % active). Three stories are injected: a product change in 2026-03 that lifts months 1–3 for every cohort after it; a 24,000-user paid burst in 2025-11 that decays much faster than organic; and an outage in 2026-06 that dents one calendar month across all cohorts. Cohort sizes shrink after the paid burst, so the size-weighted aggregate stays flat while the recent cohorts improve. No employer data — the shape is the one I see at work.
2. **Engine → evidence.** A baseline curve (power law with a floor) is fitted on the per-age median of the oldest cohorts; every cell gets a residual in percentage points. Then the triangle is read one direction at a time: rows (a cohort below baseline at four-fifths of its ages), vertical (a single mean-shift changepoint on age-matched residuals across signup months, with the bad row masked), diagonals (one calendar month across cohorts, read after peeling the vertical shift off). Each finding becomes an evidence pack: type, cohort or month, age range, baseline vs observed at an anchor age, gap in pp, cohort size. A last pack compares the size-weighted and equal-weighted curves at months 3 and 6 and projects month-12 retention for the newest cohorts off the fitted curve.
3. **Write.** Each pack goes to an LLM with a two-line brief: what moved, where, how big; then what it probably is — row, vertical and diagonal each map to a different kind of cause. The summary pack gets its own brief: what the blended curve hides, and why.
4. **Verify.** Every number in the reply is parsed and checked against the pack. If any was invented or re-rounded, the note is discarded and the deterministic template is used, and the output says so. In cohort work this matters more than usual: the whole argument is "33.0 looks like 33.9 but 41.3 is the real story", and a model that rounds 41.3 to "about 40" or writes a month-3 figure against month 6 has quietly destroyed the point while sounding fine.

## Run it

```bash
pip install -r requirements.txt
python cohort_narrator.py
```

Works with no API key — you get the template notes. For LLM-written notes set one of:

```bash
export GEMINI_API_KEY=...        # preferred; uses gemini-2.5-flash via REST
export ANTHROPIC_API_KEY=...     # uses the official anthropic SDK, claude-opus-5-5
```

Outputs: `cohorts.md` (one note per finding plus the aggregate summary, each with a collapsible evidence pack) and `triangle.png` (the triangle as a heatmap of gap vs baseline with the findings outlined, and the blended vs equal-weighted curves). Tests: `python test_cohort_narrator.py`.

## What I'd change for production

- The month-12 projection is chain-ladder: scale the fitted curve by the cohort's latest observed ratio. It assumes a month-3 lift persists to month 12, and onboarding lifts usually fade. I would fit the post-change cohorts their own curve once four of them reach month 6, and show both projections until then.
- The baseline is "the oldest six cohorts". That is the only place with a full curve, but it is also the oldest product. A rolling baseline — the six most recent cohorts with month-6 observed — catches slow drift that a fixed one normalises away.
- Read the triangle on revenue-retained as well as users-retained. The paid cohort here is bad on both; the interesting cohorts are the ones that lose users and keep revenue, and a user-count triangle cannot see them.

Companion reading: [Cohort Analysis: What Aggregated Retention Hides](https://nikunjkaushik.com/blog/cohort_analysis.html). Part of the [Building with AI](https://nikunjkaushik.com/projects.html) set on my site.
