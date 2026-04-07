"""Interactive exploration of PLL design-space exploration CSV results.

Load one or more CSV files produced by ``pll-explore``, filter by parameter
ranges, sort by any metric, find Pareto-optimal configurations, and compare
results across approximation types.

Usage:
  pll-analyze results.csv                        # summary of file
  pll-analyze *.csv --top 20                     # top 20 across all files
  pll-analyze foa.csv --sort phase_margin        # sort by phase margin
  pll-analyze foa.csv --filter "alpha_f>0.3,kf<100"
  pll-analyze foa.csv --pareto phase_margin bandwidth
  pll-analyze foa.csv soa.csv --compare          # side-by-side comparison
  pll-analyze foa.csv --export best.csv --top 50 # export filtered results
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_results(*paths: str | Path) -> pd.DataFrame:
    """Load and concatenate one or more CSV result files."""
    frames = []
    for p in paths:
        p = Path(p)
        if not p.exists():
            print(f"Warning: {p} not found, skipping.", file=sys.stderr)
            continue
        df = pd.read_csv(p)
        df["_source"] = p.name
        frames.append(df)
    if not frames:
        print("Error: no valid CSV files found.", file=sys.stderr)
        sys.exit(1)
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def apply_filters(df: pd.DataFrame, filter_str: str) -> pd.DataFrame:
    """Apply comma-separated filter expressions like 'alpha_f>0.3,kf<100'.

    Supported operators: >, <, >=, <=, ==, !=
    """
    for expr in filter_str.split(","):
        expr = expr.strip()
        if not expr:
            continue
        for op_str, op_fn in [
            (">=", lambda a, b: a >= b),
            ("<=", lambda a, b: a <= b),
            ("!=", lambda a, b: a != b),
            ("==", lambda a, b: a == b),
            (">", lambda a, b: a > b),
            ("<", lambda a, b: a < b),
        ]:
            if op_str in expr:
                col, val = expr.split(op_str, 1)
                col = col.strip()
                val = val.strip()
                if col not in df.columns:
                    print(f"Warning: column '{col}' not found, skipping filter.", file=sys.stderr)
                    break
                try:
                    val_num = float(val)
                except ValueError:
                    # String comparison
                    df = df[op_fn(df[col], val)]
                    break
                df = df[op_fn(df[col].astype(float), val_num)]
                break
    return df


# ---------------------------------------------------------------------------
# Pareto front
# ---------------------------------------------------------------------------

def pareto_front(
    df: pd.DataFrame,
    obj1_col: str,
    obj2_col: str,
    *,
    obj1_higher_better: bool = True,
    obj2_higher_better: bool = True,
) -> pd.DataFrame:
    """Find 2D Pareto-optimal rows (maximizing both objectives by default).

    Use obj1_higher_better=False or obj2_higher_better=False for metrics
    where lower is better (e.g. noise_bandwidth, lock_time).
    """
    valid = df.dropna(subset=[obj1_col, obj2_col]).copy()
    if valid.empty:
        return valid

    o1 = valid[obj1_col].values.copy()
    o2 = valid[obj2_col].values.copy()
    if not obj1_higher_better:
        o1 = -o1
    if not obj2_higher_better:
        o2 = -o2

    # Sort by o1 descending, sweep for running max of o2
    order = np.lexsort((-o2, -o1))
    pareto_idx = []
    max_o2 = -np.inf
    for idx in order:
        if o2[idx] > max_o2:
            pareto_idx.append(idx)
            max_o2 = o2[idx]

    return valid.iloc[pareto_idx].copy()


# Lower-is-better metrics
_LOWER_BETTER = {"max_pole_mag", "noise_bandwidth", "peak_sensitivity", "lock_time"}


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

_PARAM_COLS = [
    "alpha_f", "alpha_v", "beta_f", "beta_v",
    "kf", "kv", "tau", "wc", "w", "T",
]
_METRIC_COLS = [
    "phase_margin", "gain_margin", "bandwidth",
    "noise_bandwidth", "peak_sensitivity", "lock_time",
    "max_pole_mag",
]


def print_summary(df: pd.DataFrame) -> None:
    """Print a summary of the loaded dataset."""
    total = len(df)
    stable = df["stable"].sum() if "stable" in df.columns else "N/A"
    approx_types = df["approx"].unique() if "approx" in df.columns else []

    print(f"\n{'=' * 60}")
    print(f"  Total rows:    {total:,}")
    print(f"  Stable:        {stable:,}")
    print(f"  Approx types:  {', '.join(str(a).upper() for a in approx_types)}")
    if "_source" in df.columns:
        sources = df["_source"].unique()
        print(f"  Source files:  {', '.join(sources)}")
    print(f"{'=' * 60}\n")

    # Parameter ranges
    print("Parameter ranges:")
    for p in _PARAM_COLS:
        if p in df.columns:
            vals = df[p].dropna()
            if not vals.empty:
                unique = vals.nunique()
                print(f"  {p:>10s}: [{vals.min():.4g}, {vals.max():.4g}]  ({unique} unique)")

    # Metric stats (stable only)
    stable_df = df[df["stable"]] if "stable" in df.columns else df
    if not stable_df.empty:
        print(f"\nMetric statistics (stable configs):")
        for m in _METRIC_COLS:
            if m in stable_df.columns:
                col = stable_df[m].dropna()
                if not col.empty:
                    direction = "(lower=better)" if m in _LOWER_BETTER else "(higher=better)"
                    print(
                        f"  {m:>20s}: "
                        f"min={col.min():.4g}  "
                        f"median={col.median():.4g}  "
                        f"max={col.max():.4g}  "
                        f"{direction}"
                    )
    print()


def print_top(df: pd.DataFrame, n: int, sort_by: str | None) -> None:
    """Print the top N configurations, sorted by sort_by or composite_score."""
    from .explore import add_composite_score

    stable_df = df[df["stable"]].copy() if "stable" in df.columns else df.copy()
    if stable_df.empty:
        print("No stable configurations found.")
        return

    # Add composite score if not present
    if "composite_score" not in stable_df.columns:
        stable_df = add_composite_score(stable_df)

    if sort_by:
        ascending = sort_by in _LOWER_BETTER
        stable_df = stable_df.sort_values(sort_by, ascending=ascending, na_position="last")
    else:
        stable_df = stable_df.sort_values("composite_score", ascending=False)

    top = stable_df.head(n)

    sort_label = sort_by or "composite_score"
    print(f"\n=== Top {min(n, len(top))} by {sort_label} ===\n")

    for i, (_, row) in enumerate(top.iterrows(), 1):
        approx_str = f"[{row['approx'].upper():>4s}] " if "approx" in row.index else ""
        score_str = f"score={row['composite_score']:.3f}  " if "composite_score" in row.index else ""

        parts = [f"#{i:<3d} {approx_str}{score_str}"]

        for m in _METRIC_COLS:
            if m in row.index and pd.notna(row[m]):
                parts.append(f"{m}={row[m]:.4g}")

        print("  " + "  ".join(parts))

        params = "  ".join(
            f"{p}={row[p]:.4g}" for p in _PARAM_COLS
            if p in row.index and pd.notna(row[p])
        )
        print(f"      {params}")
    print()


def print_best_per_metric(df: pd.DataFrame) -> None:
    """Print the single best config for each metric."""
    stable_df = df[df["stable"]].copy() if "stable" in df.columns else df.copy()
    if stable_df.empty:
        print("No stable configurations found.")
        return

    print(f"\n=== Best Configuration Per Metric ===\n")

    for m in _METRIC_COLS:
        if m not in stable_df.columns:
            continue
        col = stable_df[m].dropna()
        if col.empty:
            continue
        if m in _LOWER_BETTER:
            # filter out zeros for lock_time/noise_bandwidth
            if m in ("lock_time", "noise_bandwidth"):
                col = col[col > 0]
                if col.empty:
                    continue
            best_idx = col.idxmin()
            direction = "min"
        else:
            best_idx = col.idxmax()
            direction = "max"

        row = stable_df.loc[best_idx]
        approx_str = f"[{row['approx'].upper()}] " if "approx" in row.index else ""
        params = ", ".join(
            f"{p}={row[p]:.4g}" for p in _PARAM_COLS
            if p in row.index and pd.notna(row[p])
        )
        print(f"  {m} ({direction}) = {row[m]:.4g}  {approx_str}")
        print(f"    {params}")
    print()


def print_pareto(df: pd.DataFrame, col1: str, col2: str) -> None:
    """Find and print the Pareto front for two objectives."""
    stable_df = df[df["stable"]].copy() if "stable" in df.columns else df.copy()
    if stable_df.empty:
        print("No stable configurations found.")
        return

    higher1 = col1 not in _LOWER_BETTER
    higher2 = col2 not in _LOWER_BETTER

    pf = pareto_front(
        stable_df, col1, col2,
        obj1_higher_better=higher1,
        obj2_higher_better=higher2,
    )

    dir1 = "max" if higher1 else "min"
    dir2 = "max" if higher2 else "min"
    print(f"\n=== Pareto Front: {col1} ({dir1}) vs {col2} ({dir2}) ===")
    print(f"  {len(pf)} Pareto-optimal configurations\n")

    for i, (_, row) in enumerate(pf.iterrows(), 1):
        if i > 20:
            print(f"  ... and {len(pf) - 20} more")
            break
        approx_str = f"[{row['approx'].upper()}] " if "approx" in row.index else ""
        params = ", ".join(
            f"{p}={row[p]:.4g}" for p in _PARAM_COLS
            if p in row.index and pd.notna(row[p])
        )
        print(
            f"  [{i:>2d}] {approx_str}"
            f"{col1}={row[col1]:.4g}  "
            f"{col2}={row[col2]:.4g}"
        )
        print(f"       {params}")
    print()


def print_comparison(df: pd.DataFrame) -> None:
    """Compare metrics across approximation types."""
    if "approx" not in df.columns:
        print("No 'approx' column found — cannot compare types.")
        return

    stable_df = df[df["stable"]].copy() if "stable" in df.columns else df.copy()
    types = sorted(stable_df["approx"].unique())

    print(f"\n=== Comparison Across Approximation Types ===\n")
    print(f"{'Metric':<22s}", end="")
    for t in types:
        print(f"  {t.upper():>12s}", end="")
    print()
    print("-" * (22 + 14 * len(types)))

    # Stability rate
    print(f"{'Stable count':<22s}", end="")
    for t in types:
        sub = df[df["approx"] == t] if "approx" in df.columns else df
        cnt = int(sub["stable"].sum()) if "stable" in sub.columns else len(sub)
        total = len(sub)
        pct = 100 * cnt / total if total else 0
        print(f"  {cnt:>5d} ({pct:4.1f}%)", end="")
    print()

    for m in _METRIC_COLS:
        if m not in stable_df.columns:
            continue
        # Mean
        print(f"{m + ' (mean)':<22s}", end="")
        for t in types:
            sub = stable_df[stable_df["approx"] == t][m].dropna()
            if not sub.empty:
                print(f"  {sub.mean():>12.4g}", end="")
            else:
                print(f"  {'N/A':>12s}", end="")
        print()

        # Best
        label = "min" if m in _LOWER_BETTER else "max"
        print(f"{m + f' ({label})':<22s}", end="")
        for t in types:
            sub = stable_df[stable_df["approx"] == t][m].dropna()
            if m in ("lock_time", "noise_bandwidth"):
                sub = sub[sub > 0]
            if not sub.empty:
                val = sub.min() if m in _LOWER_BETTER else sub.max()
                print(f"  {val:>12.4g}", end="")
            else:
                print(f"  {'N/A':>12s}", end="")
        print()
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Explore PLL design-space exploration CSV results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  pll-analyze results.csv
  pll-analyze foa_results.csv --top 20 --sort phase_margin
  pll-analyze results.csv --filter "alpha_f>=0.3,kf<1000"
  pll-analyze results.csv --pareto phase_margin bandwidth
  pll-analyze results.csv --pareto bandwidth noise_bandwidth
  pll-analyze foa.csv soa.csv --compare
  pll-analyze results.csv --best
  pll-analyze results.csv --export filtered.csv --filter "stable==True"
""",
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="CSV result file(s) to analyze.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Number of top configurations to show (default: 10).",
    )
    parser.add_argument(
        "--sort",
        type=str,
        default=None,
        help="Metric to sort by (default: composite_score).",
    )
    parser.add_argument(
        "--filter",
        type=str,
        default=None,
        dest="filter_expr",
        help='Comma-separated filters, e.g. "alpha_f>0.3,kf<100".',
    )
    parser.add_argument(
        "--pareto",
        nargs=2,
        metavar=("OBJ1", "OBJ2"),
        help="Find Pareto front for two metrics.",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Compare metrics across approximation types.",
    )
    parser.add_argument(
        "--best",
        action="store_true",
        help="Show the single best config per metric.",
    )
    parser.add_argument(
        "--stable-only",
        action="store_true",
        help="Only include stable configurations.",
    )
    parser.add_argument(
        "--export",
        type=str,
        default=None,
        help="Export filtered results to a new CSV file.",
    )
    parser.add_argument(
        "--approx",
        type=str,
        default=None,
        help="Filter to a specific approx type (foa, soa, cfoa, csoa).",
    )

    args = parser.parse_args()

    # Load
    df = load_results(*args.files)

    # Apply filters
    if args.stable_only or args.sort or args.best or args.pareto:
        df = df[df["stable"]] if "stable" in df.columns else df

    if args.approx:
        if "approx" in df.columns:
            df = df[df["approx"] == args.approx]
        else:
            print(f"Warning: no 'approx' column found.", file=sys.stderr)

    if args.filter_expr:
        df = apply_filters(df, args.filter_expr)

    if df.empty:
        print("No results match the given filters.")
        sys.exit(0)

    # Summary always shown
    print_summary(df)

    # Actions
    if args.compare:
        print_comparison(df)

    if args.best:
        print_best_per_metric(df)

    if args.pareto:
        print_pareto(df, args.pareto[0], args.pareto[1])

    # Top N (always shown unless only --compare or --best requested)
    if not args.compare or args.sort or args.top != 10:
        print_top(df, args.top, args.sort)

    # Export
    if args.export:
        export_path = Path(args.export)
        df.to_csv(export_path, index=False)
        print(f"Exported {len(df):,} rows to {export_path}")


if __name__ == "__main__":
    main()
