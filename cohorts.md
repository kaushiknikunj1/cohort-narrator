# Cohort notes

Retention triangle read in three directions (rows, vertical, diagonals) against a baseline fitted on the oldest 6 cohorts. Notes written by: none; every number verified against the evidence pack.

## Row: 2025-11

Cohort 2025-11 (24,000 users) sits below baseline at every age 1-11: 22.6% at month 3 vs 33.9% (-11.2 pp), worst gap -16.4 pp.
Probably an acquisition-quality problem, not a product one - check the channel mix for 2025-11 signups.

*source: template (no API key)*

<details><summary>evidence</summary>

```json
{
  "type": "row",
  "cohort": "2025-11",
  "age_from": 1,
  "age_to": 11,
  "anchor_age": 3,
  "baseline_pct": 33.9,
  "observed_pct": 22.6,
  "gap_pp": -11.2,
  "cohort_size": 24000,
  "mean_gap_pp": -13.5,
  "worst_gap_pp": -16.4
}
```
</details>

## Vertical: 2026-03

Every cohort from 2026-03 on (7 cohorts, 26,400 users) retains better at months 1-3: 41.3% at month 3 vs 33.9% baseline (+7.4 pp).
A sustained shift by signup month is a product or onboarding change, not a traffic one - check what shipped around 2026-03.

*source: template (no API key)*

<details><summary>evidence</summary>

```json
{
  "type": "vertical",
  "from_cohort": "2026-03",
  "cohorts_after": 7,
  "age_from": 1,
  "age_to": 3,
  "anchor_age": 3,
  "baseline_pct": 33.9,
  "observed_pct": 41.3,
  "gap_pp": 7.4,
  "shift_pp": 7.9,
  "cohort_size": 26400
}
```
</details>

## Diagonal: 2026-06

Calendar month 2026-06 is down across 10 cohorts at once (ages 1-11), mean gap -6.2 pp; worst cell is cohort 2026-01 at month 5: 22.9% vs 29.3% (-6.5 pp).
One month hitting every cohort is a calendar event - an outage, a pricing change or a festival - not a cohort problem; check the incident log for 2026-06.

*source: template (no API key)*

<details><summary>evidence</summary>

```json
{
  "type": "diagonal",
  "calendar_month": "2026-06",
  "cohorts_hit": 10,
  "age_from": 1,
  "age_to": 11,
  "mean_gap_pp": -6.2,
  "anchor_cohort": "2026-01",
  "anchor_age": 5,
  "baseline_pct": 29.3,
  "observed_pct": 22.9,
  "gap_pp": -6.5,
  "cohort_size": 8300
}
```
</details>

## What the aggregate hides

Blended month-3 retention is 33.0% against a 33.9% baseline - the headline reads flat. Equal-weighted it is 36.1%, and the 5 cohorts since the product change average 41.3%.
The aggregate hides this because the bad paid cohort carries 21.7% of month-3 weight and the post-change cohorts only 17.6%; at month 6 the mix gap is +2.1 pp. On the fitted curve the latest 5 cohorts project to 26.0-30.8% at month 12 vs 24.6% baseline.

*source: template (no API key)*

<details><summary>evidence</summary>

```json
{
  "curves": {
    "blended": [
      100.0,
      51.4,
      38.2,
      33.0,
      28.4,
      26.6,
      24.8,
      23.4,
      22.3,
      21.0,
      20.0,
      18.4,
      24.6
    ],
    "equal_weighted": [
      100.0,
      55.3,
      41.6,
      36.1,
      30.5,
      28.7,
      26.9,
      25.9,
      24.1,
      23.1,
      22.3,
      20.8,
      24.6
    ],
    "baseline": [
      100.0,
      51.4,
      38.8,
      33.9,
      31.1,
      29.3,
      28.1,
      27.1,
      26.4,
      25.8,
      25.3,
      24.9,
      24.6
    ]
  },
  "month_3": {
    "blended_pct": 33.0,
    "equal_weighted_pct": 36.1,
    "baseline_pct": 33.9,
    "mix_gap_pp": 3.1,
    "cohorts_observed": 13,
    "post_change_cohorts": 5,
    "post_change_mean_pct": 41.3,
    "post_change_weight_pct": 17.6,
    "bad_row_weight_pct": 21.7
  },
  "month_6": {
    "blended_pct": 24.8,
    "equal_weighted_pct": 26.9,
    "baseline_pct": 28.1,
    "mix_gap_pp": 2.1,
    "cohorts_observed": 10,
    "post_change_cohorts": 2,
    "post_change_mean_pct": 30.2,
    "post_change_weight_pct": 8.1,
    "bad_row_weight_pct": 24.1
  },
  "projection": {
    "baseline_month_12_pct": 24.6,
    "latest_cohorts": [
      {
        "cohort": "2026-05",
        "last_age": 5,
        "observed_pct": 32.2,
        "projected_month_12_pct": 26.9
      },
      {
        "cohort": "2026-06",
        "last_age": 4,
        "observed_pct": 33.0,
        "projected_month_12_pct": 26.0
      },
      {
        "cohort": "2026-07",
        "last_age": 3,
        "observed_pct": 42.3,
        "projected_month_12_pct": 30.7
      },
      {
        "cohort": "2026-08",
        "last_age": 2,
        "observed_pct": 48.7,
        "projected_month_12_pct": 30.8
      },
      {
        "cohort": "2026-09",
        "last_age": 1,
        "observed_pct": 63.0,
        "projected_month_12_pct": 30.1
      }
    ]
  }
}
```
</details>
