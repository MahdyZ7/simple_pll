"""Design space exploration for fractional-order PLL systems.

Sweeps the parameter space to find stable PLL configurations with high
phase margin, gain margin, bandwidth, and robustness. Uses a fast path
that builds transfer functions directly from polynomial coefficients
(no sympy), achieving ~1-5ms per evaluation.

Port of design_space_exploration_fast.m.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import io
import itertools
import os
import sys
import time
import warnings
from multiprocessing import Pool
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd

from .approximations import (
    complex_first_order_approx,
    complex_second_order_approx,
    first_order_approx,
    second_order_approx,
)

# ---------------------------------------------------------------------------
# Section 1: Configuration
# ---------------------------------------------------------------------------


@dataclass
class SweepConfig:
    """Parameter sweep configuration.

    Attributes:
        approx: Approximation type — "foa", "soa", "cfoa", or "csoa".
        T_range: Sampling period values (s).
        alpha_f_range: Filter fractional order values.
        alpha_v_range: VCO fractional order values.
        beta_f_range: Filter complex imaginary part values.
        beta_v_range: VCO complex imaginary part values.
        kf_range: Filter gain values.
        kv_range: VCO gain values.
        tau_range: Filter time constant values.
        wc_range: Corner frequency values (rad/s).
        w_range: Carrier frequency values (rad/s, complex only).
        max_workers: Number of parallel workers (None = all CPUs).
        output_dir: Directory for CSV and plots.
    """

    approx: str = "foa"

    T_range: np.ndarray = field(
        default_factory=lambda: np.logspace(-10, -8, 6)
    )
    alpha_f_range: np.ndarray = field(
        default_factory=lambda: np.linspace(0.1, 0.9, 9)
    )
    alpha_v_range: np.ndarray = field(
        default_factory=lambda: np.linspace(0.1, 0.9, 9)
    )
    beta_f_range: np.ndarray = field(
        default_factory=lambda: np.array([0.0])
    )
    beta_v_range: np.ndarray = field(
        default_factory=lambda: np.array([0.0])
    )
    kf_range: np.ndarray = field(
        default_factory=lambda: np.logspace(-1, 6, 8)
    )
    kv_range: np.ndarray = field(
        default_factory=lambda: np.logspace(-1, 6, 8)
    )
    tau_range: np.ndarray = field(
        default_factory=lambda: np.logspace(-10, -1, 10)
    )
    wc_range: np.ndarray = field(
        default_factory=lambda: np.logspace(1, 10, 10)
    )
    w_range: np.ndarray = field(
        default_factory=lambda: np.array([2 * np.pi * 1e4])
    )
    max_workers: int | None = None
    output_dir: str = "exploration_results"

    def __post_init__(self) -> None:
        if self.approx == "compare":
            # Compare mode evaluates all 4 types per combo (4× work).
            # Reduce base ranges from their (large) defaults to keep
            # total evaluations manageable (~5M instead of ~20B).
            _reduce = [
                ("alpha_f_range", 9, lambda: np.linspace(0.1, 0.9, 5)),
                ("alpha_v_range", 9, lambda: np.linspace(0.1, 0.9, 5)),
                ("kf_range", 8, lambda: np.logspace(1, 6, 5)),
                ("kv_range", 8, lambda: np.logspace(1, 6, 5)),
                ("tau_range", 10, lambda: np.logspace(-10, -1, 5)),
                ("wc_range", 10, lambda: np.logspace(3, 10, 5)),
                ("T_range", 6, lambda: np.logspace(-10, -8, 3)),
            ]
            for attr, default_len, factory in _reduce:
                if len(getattr(self, attr)) == default_len:
                    setattr(self, attr, factory())
            # Expand beta/w for complex types (moderate grid)
            if len(self.beta_f_range) == 1 and self.beta_f_range[0] == 0.0:
                self.beta_f_range = np.linspace(0.1, 0.9, 10)
            if len(self.beta_v_range) == 1 and self.beta_v_range[0] == 0.0:
                self.beta_v_range = np.linspace(0.1, 0.9, 10)
            if len(self.w_range) == 1:
                self.w_range = np.logspace(3, 6, 3) * 2 * np.pi
            return

        is_complex = self.approx in ("cfoa", "csoa")
        # For complex types, expand beta and w ranges if still at defaults
        if is_complex:
            if len(self.beta_f_range) == 1 and self.beta_f_range[0] == 0.0:
                self.beta_f_range = np.linspace(0, 0.4, 5)
            if len(self.beta_v_range) == 1 and self.beta_v_range[0] == 0.0:
                self.beta_v_range = np.linspace(0, 0.4, 5)
            if len(self.w_range) == 1:
                self.w_range = np.logspace(
                    np.log10(2 * np.pi * 1e3),
                    np.log10(2 * np.pi * 1e5),
                    4,
                )
        else:
            # Real-only: force beta=0, w irrelevant (use single dummy)
            self.beta_f_range = np.array([0.0])
            self.beta_v_range = np.array([0.0])
            self.w_range = np.array([2 * np.pi * 1e4])

    @property
    def total_combinations(self) -> int:
        base = (
            len(self.alpha_f_range)
            * len(self.alpha_v_range)
            * len(self.beta_f_range)
            * len(self.beta_v_range)
            * len(self.kf_range)
            * len(self.kv_range)
            * len(self.tau_range)
            * len(self.wc_range)
            * len(self.w_range)
            * len(self.T_range)
        )
        if self.approx == "compare":
            return base * 4
        return base


# ---------------------------------------------------------------------------
# Section 1b: Incremental CSV writer
# ---------------------------------------------------------------------------

CSV_COLUMNS = [
    "alpha_f", "alpha_v", "beta_f", "beta_v",
    "kf", "kv", "tau", "wc", "w", "T",
    "approx", "stable", "max_pole_mag",
    "phase_margin", "gain_margin", "bandwidth",
    "noise_bandwidth", "peak_sensitivity", "lock_time",
]


class IncrementalCSVWriter:
    """Buffers results and flushes them to a CSV file periodically.

    Keeps at most ``flush_every`` rows in memory before appending to disk.
    When the file already exists (resume mode), the header is skipped.
    """

    def __init__(
        self,
        path: Path,
        flush_every: int = 5_000,
        *,
        append: bool = False,
    ) -> None:
        self.path = Path(path)
        self.flush_every = flush_every
        self._buffer: list[dict[str, Any]] = []
        self._total_written = 0
        self._append = append

        if not append:
            with open(self.path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
                writer.writeheader()

    def add(self, row: dict[str, Any]) -> None:
        self._buffer.append(row)
        if len(self._buffer) >= self.flush_every:
            self.flush()

    def flush(self) -> None:
        if not self._buffer:
            return
        with open(self.path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            for row in self._buffer:
                writer.writerow({k: row.get(k, "") for k in CSV_COLUMNS})
        self._total_written += len(self._buffer)
        self._buffer.clear()

    @property
    def total_written(self) -> int:
        return self._total_written + len(self._buffer)

    def close(self) -> None:
        self.flush()


def load_completed_params(csv_path: Path) -> set[tuple]:
    """Load already-completed parameter combos from an existing CSV.

    Returns a set of tuples (alpha_f, alpha_v, beta_f, beta_v, kf, kv,
    tau, wc, w, T, approx) that have already been evaluated, enabling
    the sweep to skip them on resume.
    """
    completed: set[tuple] = set()
    if not csv_path.exists():
        return completed

    param_keys = [
        "alpha_f", "alpha_v", "beta_f", "beta_v",
        "kf", "kv", "tau", "wc", "w", "T", "approx",
    ]
    try:
        df = pd.read_csv(csv_path)
        for _, row in df.iterrows():
            key = tuple(row[k] for k in param_keys)
            completed.add(key)
    except Exception:
        pass
    return completed


# ---------------------------------------------------------------------------
# Section 2: Fast-path PLL analysis (no sympy)
# ---------------------------------------------------------------------------


def _poly_pad_add(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Add two polynomial coefficient arrays, zero-padding the shorter one."""
    diff = len(a) - len(b)
    if diff > 0:
        b = np.concatenate([np.zeros(diff), b])
    elif diff < 0:
        a = np.concatenate([np.zeros(-diff), a])
    return a + b


def analyze_pll_fast(
    alpha_f: float,
    alpha_v: float,
    beta_f: float,
    beta_v: float,
    kf: float,
    kv: float,
    tau: float,
    wc: float,
    w: float,
    T: float,
    approx: str,
) -> dict[str, Any]:
    """Analyze a single PLL configuration using direct polynomial math.

    Builds filter and VCO transfer functions from El-Khazali polynomial
    coefficients, cascades with integrator, closes the loop, and checks
    stability via continuous-time poles.  Uses pure numpy/scipy — no
    control library in the hot path.  ~2 ms for unstable configs,
    ~5 ms for stable (plus ~25 ms if lock time is computed).

    Args:
        alpha_f: Filter fractional order (0, 1).
        alpha_v: VCO fractional order (0, 1).
        beta_f: Filter complex imaginary part [0, 1).
        beta_v: VCO complex imaginary part [0, 1).
        kf: Filter gain.
        kv: VCO gain.
        tau: Filter time constant.
        wc: Corner frequency (rad/s).
        w: Carrier frequency (rad/s, used for complex types).
        T: Sampling period (s).
        approx: Approximation type — "foa", "soa", "cfoa", "csoa".

    Returns:
        Dict with keys: stable, max_pole_mag, phase_margin, gain_margin,
        bandwidth, noise_bandwidth, peak_sensitivity, lock_time,
        and all input parameters.
    """
    result: dict[str, Any] = dict(
        alpha_f=alpha_f,
        alpha_v=alpha_v,
        beta_f=beta_f,
        beta_v=beta_v,
        kf=kf,
        kv=kv,
        tau=tau,
        wc=wc,
        w=w,
        T=T,
        approx=approx,
        stable=False,
        max_pole_mag=np.inf,
        phase_margin=np.nan,
        gain_margin=np.nan,
        bandwidth=np.nan,
        noise_bandwidth=np.nan,
        peak_sensitivity=np.nan,
        lock_time=np.nan,
    )

    try:
        # -- Get approximation coefficients for s^alpha (filter & VCO) --
        if approx == "foa":
            num_af, den_af = first_order_approx(alpha_f, wc)
            num_av, den_av = first_order_approx(alpha_v, wc)
        elif approx == "soa":
            num_af, den_af = second_order_approx(alpha_f, wc)
            num_av, den_av = second_order_approx(alpha_v, wc)
        elif approx == "cfoa":
            num_af, den_af = complex_first_order_approx(alpha_f, beta_f, w, wc)
            num_av, den_av = complex_first_order_approx(alpha_v, beta_v, w, wc)
        elif approx == "csoa":
            num_af, den_af = complex_second_order_approx(alpha_f, beta_f, w, wc)
            num_av, den_av = complex_second_order_approx(alpha_v, beta_v, w, wc)
        else:
            return result

        # -- Build polynomials using numpy (no control library) --
        # Filter: kf * den_af / (tau * num_af + den_af)
        num_filter = kf * den_af
        den_filter = _poly_pad_add(tau * num_af, den_af)

        # VCO: kv * den_av / num_av
        num_vco = kv * den_av
        den_vco = num_av

        # Open-loop: Filter * (1/s) * VCO
        #   num_ol = num_filter * [1] * num_vco
        #   den_ol = den_filter * [1,0] * den_vco
        num_ol = np.polymul(num_filter, num_vco)
        den_ol = np.polymul(np.polymul(den_filter, [1, 0]), den_vco)

        # Closed-loop: num_ol / (den_ol + num_ol)
        den_cl = _poly_pad_add(den_ol, num_ol)

        # -- Fast stability check via continuous-time poles --
        poles_ct = np.roots(den_cl)
        max_re = float(np.max(np.real(poles_ct)))
        # Store a stability metric: how far the worst pole is from
        # the imaginary axis (negative = stable margin).
        result["max_pole_mag"] = max_re
        result["stable"] = max_re < 0

        if not result["stable"]:
            return result

        # -- Stable: compute metrics from open-loop frequency response --
        try:
            w_test = np.logspace(-2, 12, 500)
            jw = 1j * w_test
            Gc_jw = np.polyval(num_ol, jw) / np.polyval(den_ol, jw)

            ol_mag = np.abs(Gc_jw)
            ol_phase = np.unwrap(np.angle(Gc_jw))
            ol_phase_deg = np.degrees(ol_phase)

            # Phase margin: phase at gain crossover (|Gc|=1)
            mag_db_ol = 20 * np.log10(np.maximum(ol_mag, 1e-30))
            crossings = np.where(np.diff(np.sign(mag_db_ol)))[0]
            if len(crossings) > 0:
                idx = crossings[0]
                pm_val = 180.0 + ol_phase_deg[idx]
                if np.isfinite(pm_val):
                    result["phase_margin"] = float(pm_val)

            # Gain margin: magnitude at phase crossover (phase=-180)
            phase_shifted = ol_phase_deg + 180.0
            pcrossings = np.where(np.diff(np.sign(phase_shifted)))[0]
            if len(pcrossings) > 0:
                idx = pcrossings[0]
                gm_linear = ol_mag[idx]
                if gm_linear > 0:
                    result["gain_margin"] = float(-20 * np.log10(gm_linear))
            else:
                result["gain_margin"] = float("inf")

            # Closed-loop from open-loop: T(jw) = Gc / (1 + Gc)
            T_jw = Gc_jw / (1.0 + Gc_jw)
            cl_mag = np.abs(T_jw)
            cl_mag_db = 20 * np.log10(np.maximum(cl_mag, 1e-30))

            # Bandwidth (-3 dB point)
            dc_gain_db = cl_mag_db[0]
            threshold = dc_gain_db - 3.0
            below = np.where(cl_mag_db < threshold)[0]
            if len(below) > 0:
                result["bandwidth"] = float(w_test[below[0]])

            # Noise bandwidth: B_n = (1/2pi) * integral |T(jw)|^2 dw
            mag_sq = cl_mag ** 2
            B_n = float(np.trapezoid(mag_sq, w_test) / (2.0 * np.pi))
            if np.isfinite(B_n) and B_n > 0:
                result["noise_bandwidth"] = B_n

            # Peak sensitivity: max |S(jw)| where S = 1/(1+Gc)
            S_jw = 1.0 / (1.0 + Gc_jw)
            Ms = float(np.max(np.abs(S_jw)))
            if np.isfinite(Ms):
                result["peak_sensitivity"] = Ms
        except Exception:
            pass

        # Lock time: analytical estimate from dominant CT pole.
        # t_lock ≈ -ln(0.02) / |Re(dominant_pole)| (2% settling).
        # Avoids expensive and numerically problematic discretization.
        try:
            dominant_re = np.max(np.real(poles_ct))
            if dominant_re < 0:
                result["lock_time"] = float(3.912 / abs(dominant_re))
        except Exception:
            pass

    except Exception:
        pass

    return result


# ---------------------------------------------------------------------------
# Helper for multiprocessing — module-level function (picklable)
# ---------------------------------------------------------------------------

def _analyze_wrapper(args: tuple) -> dict[str, Any]:
    """Unpack tuple and call analyze_pll_fast.  Must be module-level for pickle."""
    return analyze_pll_fast(*args)


_COMPARE_APPROX_TYPES = ("foa", "soa", "cfoa", "csoa")


def _compare_wrapper(args: tuple) -> list[dict[str, Any]]:
    """Evaluate all 4 approx types for one parameter combo.  Module-level for pickle."""
    return [analyze_pll_fast(*args, approx) for approx in _COMPARE_APPROX_TYPES]


# ---------------------------------------------------------------------------
# Section 3: Parameter grid generation
# ---------------------------------------------------------------------------


def build_param_grid(cfg: SweepConfig) -> itertools.product:
    """Build Cartesian product of all parameter combinations.

    Returns a lazy iterator of tuples, each containing the arguments for
    ``analyze_pll_fast`` in order.  The iterator is never materialised as a
    list so that even very large sweeps fit in memory.
    """
    return itertools.product(
        cfg.alpha_f_range,
        cfg.alpha_v_range,
        cfg.beta_f_range,
        cfg.beta_v_range,
        cfg.kf_range,
        cfg.kv_range,
        cfg.tau_range,
        cfg.wc_range,
        cfg.w_range,
        cfg.T_range,
        [cfg.approx],
    )


# ---------------------------------------------------------------------------
# Section 4: Parallel sweep execution
# ---------------------------------------------------------------------------


def run_sweep(
    cfg: SweepConfig,
    csv_path: Path | None = None,
    resume: bool = False,
) -> pd.DataFrame:
    """Run the full parameter sweep and return results as a DataFrame.

    Uses multiprocessing.Pool.imap_unordered for bounded memory usage
    (natural back-pressure) and incremental CSV flushing to disk so that
    progress is never lost.

    Args:
        cfg: Sweep configuration.
        csv_path: Path for incremental CSV output.  If None, results are
            only held in memory (legacy behaviour).
        resume: If True and *csv_path* exists, skip already-completed
            parameter combinations and continue from the point of failure.
    """
    total = cfg.total_combinations

    # --- Resume support ---
    completed: set[tuple] = set()
    append_mode = False
    if resume and csv_path and csv_path.exists():
        completed = load_completed_params(csv_path)
        if completed:
            append_mode = True
            print(f"Resuming: {len(completed):,} already completed — "
                  f"skipping those.")

    # Build grid, filtering out already-done combos when resuming
    grid_iter = build_param_grid(cfg)
    if completed:
        grid_iter = (
            args for args in grid_iter if args not in completed
        )
    remaining = total - len(completed)

    print(f"\n=== Fractional-Order PLL Design Space Exploration ===")
    print(f"Approximation type: {cfg.approx.upper()}")
    print(f"Total combinations: {total:,}")
    if completed:
        print(f"Already completed:  {len(completed):,}")
    print(f"Remaining:          {remaining:,}")
    print(f"Workers: {cfg.max_workers or os.cpu_count()}\n")

    t0 = time.perf_counter()

    # Incremental CSV writer — flushes every 5k rows
    writer: IncrementalCSVWriter | None = None
    if csv_path:
        writer = IncrementalCSVWriter(
            csv_path,
            flush_every=5_000,
            append=append_mode,
        )

    # Column-oriented storage — avoids per-row dict overhead (~10x less RAM)
    _cols: dict[str, list] = {k: [] for k in CSV_COLUMNS}

    def _collect(r: dict[str, Any]) -> None:
        for k in _cols:
            _cols[k].append(r[k])
        if writer:
            writer.add(r)

    chunk_size = max(1, remaining // 100)

    if cfg.max_workers == 1:
        for i, args in enumerate(grid_iter):
            _collect(_analyze_wrapper(args))
            if (i + 1) % chunk_size == 0 or (i + 1) == remaining:
                pct = 100 * (i + 1) / remaining
                done = len(completed) + i + 1
                print(f"  Progress: {pct:5.1f}%  ({done:,}/{total:,})", end="\r")
        print()
    else:
        with Pool(
            processes=cfg.max_workers,
            maxtasksperchild=50_000,
        ) as pool:
            for i, r in enumerate(
                pool.imap_unordered(_analyze_wrapper, grid_iter, chunksize=64)
            ):
                _collect(r)
                if (i + 1) % chunk_size == 0 or (i + 1) == remaining:
                    pct = 100 * (i + 1) / remaining
                    done = len(completed) + i + 1
                    print(
                        f"  Progress: {pct:5.1f}%  ({done:,}/{total:,})",
                        end="\r",
                    )
            print()

    if writer:
        writer.close()

    elapsed = time.perf_counter() - t0

    # If resuming, reload the full CSV so downstream analysis has everything
    if append_mode and csv_path and csv_path.exists():
        df = pd.read_csv(csv_path)
    else:
        df = pd.DataFrame(_cols)

    stable_count = int(df["stable"].sum())
    evaluated = len(df)

    print(f"Completed in {elapsed:.2f}s  ({remaining / max(elapsed, 0.001):,.0f} configs/sec)")
    print(
        f"Stable configurations: {stable_count:,} / {evaluated:,} "
        f"({100 * stable_count / max(evaluated, 1):.2f}%)\n"
    )

    return df


def run_comparison_sweep(
    cfg: SweepConfig,
    csv_path: Path | None = None,
    resume: bool = False,
) -> tuple[pd.DataFrame, dict[str, tuple[int, int]]]:
    """Run a cross-type comparison sweep (memory-efficient).

    Only stable results are kept in memory.  Per-type total/stable counts
    are tracked with running counters so the full grid is never materialised.
    Results are incrementally flushed to *csv_path* when provided.

    Args:
        cfg: Sweep configuration.
        csv_path: Path for incremental CSV output (stable results only).
        resume: If True and *csv_path* exists, skip already-completed
            base parameter combinations.

    Returns:
        ``(stable_df, type_counts)`` where *type_counts* maps each approx
        type to ``(total_evaluated, stable_count)``.
    """
    grid_size = cfg.total_combinations // 4
    total = cfg.total_combinations

    # --- Resume support ---
    completed_bases: set[tuple] = set()
    append_mode = False
    if resume and csv_path and csv_path.exists():
        # For compare mode, a completed "base" means all 4 types were run
        raw_completed = load_completed_params(csv_path)
        # Group by base params (strip approx)
        base_counts: dict[tuple, int] = {}
        for c in raw_completed:
            base = c[:-1]  # everything except approx
            base_counts[base] = base_counts.get(base, 0) + 1
        # Only consider fully completed bases (all 4 types done)
        completed_bases = {b for b, cnt in base_counts.items() if cnt >= 4}
        if completed_bases:
            append_mode = True
            print(f"Resuming: {len(completed_bases):,} base combos already "
                  f"completed — skipping those.")

    # Generator — never materialised as a list
    grid = itertools.product(
        cfg.alpha_f_range,
        cfg.alpha_v_range,
        cfg.beta_f_range,
        cfg.beta_v_range,
        cfg.kf_range,
        cfg.kv_range,
        cfg.tau_range,
        cfg.wc_range,
        cfg.w_range,
        cfg.T_range,
    )
    if completed_bases:
        grid = (args for args in grid if args not in completed_bases)

    remaining_bases = grid_size - len(completed_bases)
    remaining = remaining_bases * 4

    print(f"\n=== Fractional-Order PLL Cross-Type Comparison ===")
    print(f"Base parameter combos: {grid_size:,}")
    print(f"Total evaluations (x4 types): {total:,}")
    if completed_bases:
        print(f"Already completed:  {len(completed_bases) * 4:,}")
    print(f"Remaining:          {remaining:,}")
    print(f"Workers: {cfg.max_workers or os.cpu_count()}\n")

    t0 = time.perf_counter()

    # Incremental CSV writer for stable results
    writer: IncrementalCSVWriter | None = None
    if csv_path:
        writer = IncrementalCSVWriter(
            csv_path,
            flush_every=5_000,
            append=append_mode,
        )

    _MAX_IN_MEMORY = 100_000  # cap in-memory results to avoid OOM
    stable_results: list[dict[str, Any]] = []
    type_counts: dict[str, list[int]] = {
        a: [0, 0] for a in _COMPARE_APPROX_TYPES
    }  # [total, stable]
    chunk_size = max(1, remaining_bases // 100)

    def _collect_result(r: dict[str, Any]) -> None:
        type_counts[r["approx"]][0] += 1
        if r["stable"]:
            type_counts[r["approx"]][1] += 1
            if len(stable_results) < _MAX_IN_MEMORY:
                stable_results.append(r)
            if writer:
                writer.add(r)

    if cfg.max_workers == 1:
        for i, args in enumerate(grid):
            for r in _compare_wrapper(args):
                _collect_result(r)
            if (i + 1) % chunk_size == 0 or (i + 1) == remaining_bases:
                pct = 100 * (i + 1) / remaining_bases
                print(
                    f"  Progress: {pct:5.1f}%  ({(i + 1) * 4:,}/{remaining:,})",
                    end="\r",
                )
        print()
    else:
        with Pool(
            processes=cfg.max_workers,
            maxtasksperchild=50_000,
        ) as pool:
            for i, batch in enumerate(
                pool.imap_unordered(_compare_wrapper, grid, chunksize=64)
            ):
                for r in batch:
                    _collect_result(r)
                if (i + 1) % chunk_size == 0 or (i + 1) == remaining_bases:
                    pct = 100 * (i + 1) / remaining_bases
                    print(
                        f"  Progress: {pct:5.1f}%  ({(i + 1) * 4:,}/{remaining:,})",
                        end="\r",
                    )
            print()

    if writer:
        writer.close()

    elapsed = time.perf_counter() - t0

    # Build DataFrame — read from CSV when available (handles capped
    # in-memory results and resume scenarios).
    stable_count = sum(c[1] for c in type_counts.values())
    if csv_path and csv_path.exists() and stable_count > _MAX_IN_MEMORY:
        # Too many results for memory — read from CSV
        df = pd.read_csv(csv_path)
        if append_mode:
            type_counts = {a: [0, 0] for a in _COMPARE_APPROX_TYPES}
            for a in _COMPARE_APPROX_TYPES:
                sub = df[df["approx"] == a]
                type_counts[a][0] = len(sub)
                type_counts[a][1] = int(sub["stable"].sum()) if "stable" in sub.columns else 0
    elif append_mode and csv_path and csv_path.exists():
        df = pd.read_csv(csv_path)
        type_counts = {a: [0, 0] for a in _COMPARE_APPROX_TYPES}
        for a in _COMPARE_APPROX_TYPES:
            sub = df[df["approx"] == a]
            type_counts[a][0] = len(sub)
            type_counts[a][1] = int(sub["stable"].sum()) if "stable" in sub.columns else 0
    else:
        df = pd.DataFrame(stable_results) if stable_results else pd.DataFrame()

    stable_count = sum(c[1] for c in type_counts.values())

    print(f"Completed in {elapsed:.2f}s  ({remaining / max(elapsed, 0.001):,.0f} configs/sec)")
    print(
        f"Stable configurations: {stable_count:,} / {total:,} "
        f"({100 * stable_count / max(total, 1):.2f}%)\n"
    )

    # Convert to immutable tuples
    tc = {a: tuple(v) for a, v in type_counts.items()}
    return df, tc


# ---------------------------------------------------------------------------
# Section 5: Best configuration identification
# ---------------------------------------------------------------------------


def add_composite_score(df: pd.DataFrame) -> pd.DataFrame:
    """Add composite_score and rank columns to a DataFrame of stable configs.

    Each metric is normalized to [0, 1] using percentile ranking across the
    stable population, then combined with equal weights.  Metrics where
    *lower is better* are inverted so that a higher composite score always
    means a better PLL.

    Columns added:
        composite_score: float in [0, 1] — higher is better.
        rank: int starting at 1 — rank 1 is the best overall PLL.
    """
    if df.empty:
        df["composite_score"] = pd.Series(dtype=float)
        df["rank"] = pd.Series(dtype=int)
        return df

    out = df.copy()

    # Metrics and their direction (True = higher is better)
    metric_dirs: list[tuple[str, bool]] = [
        ("phase_margin",    True),
        ("gain_margin",     True),
        ("bandwidth",       True),
        ("max_pole_mag",    False),  # lower pole mag = more robust
        ("noise_bandwidth", False),  # lower = less noise passed
        ("peak_sensitivity", False), # lower = less noise amplification
        ("lock_time",       False),  # lower = faster lock
    ]

    # Build per-metric percentile scores (0–1), NaN-safe
    scores = pd.DataFrame(index=out.index)
    used = 0
    for metric, higher_better in metric_dirs:
        if metric not in out.columns:
            continue
        col = out[metric].copy()
        # Exclude non-finite values from ranking
        finite = col.where(np.isfinite(col))
        if finite.notna().sum() < 2:
            continue
        # Percentile rank: 0 = worst, 1 = best among finite values
        ranked = finite.rank(pct=True, na_option="keep")
        if not higher_better:
            ranked = 1.0 - ranked
        scores[metric] = ranked
        used += 1

    if used == 0:
        out["composite_score"] = 0.0
        out["rank"] = range(1, len(out) + 1)
        return out

    # Equal-weight average (NaN-tolerant: a config missing one metric is
    # not penalised, it just averages over fewer metrics)
    out["composite_score"] = scores.mean(axis=1, skipna=True)
    out["rank"] = (
        out["composite_score"]
        .rank(ascending=False, method="min", na_option="bottom")
        .astype(int)
    )

    return out


def find_best_configs(df: pd.DataFrame) -> dict[str, pd.Series | None]:
    """Identify optimal configurations across 7 criteria.

    Returns dict with keys: max_pm, max_gm, max_bw, min_pole,
    min_noise_bw, min_peak_sens, min_lock_time.
    Each value is a pandas Series (row) or None if no valid config found.
    """
    stable = df[df["stable"]].copy()
    if stable.empty:
        return dict(
            max_pm=None, max_gm=None, max_bw=None, min_pole=None,
            min_noise_bw=None, min_peak_sens=None, min_lock_time=None,
        )

    best: dict[str, pd.Series | None] = {}

    # Max phase margin
    valid = stable.dropna(subset=["phase_margin"])
    best["max_pm"] = valid.loc[valid["phase_margin"].idxmax()] if not valid.empty else None

    # Max gain margin (inf GM = best; among those, pick highest PM)
    valid = stable.dropna(subset=["gain_margin"])
    if not valid.empty:
        inf_gm = valid[np.isinf(valid["gain_margin"])]
        if not inf_gm.empty:
            pm_col = inf_gm["phase_margin"].fillna(-np.inf)
            best["max_gm"] = inf_gm.loc[pm_col.idxmax()]
        else:
            best["max_gm"] = valid.loc[valid["gain_margin"].idxmax()]
    else:
        best["max_gm"] = None

    # Max bandwidth
    valid = stable.dropna(subset=["bandwidth"])
    best["max_bw"] = valid.loc[valid["bandwidth"].idxmax()] if not valid.empty else None

    # Most robust (smallest max pole magnitude)
    best["min_pole"] = stable.loc[stable["max_pole_mag"].idxmin()]

    # Min noise bandwidth (best noise rejection)
    valid = stable.dropna(subset=["noise_bandwidth"])
    valid = valid[valid["noise_bandwidth"] > 0]
    best["min_noise_bw"] = valid.loc[valid["noise_bandwidth"].idxmin()] if not valid.empty else None

    # Min peak sensitivity (least noise amplification)
    valid = stable.dropna(subset=["peak_sensitivity"])
    best["min_peak_sens"] = valid.loc[valid["peak_sensitivity"].idxmin()] if not valid.empty else None

    # Min lock time (fastest acquisition)
    valid = stable.dropna(subset=["lock_time"])
    valid = valid[valid["lock_time"] > 0]
    best["min_lock_time"] = valid.loc[valid["lock_time"].idxmin()] if not valid.empty else None

    return best


def print_best_configs(best: dict[str, pd.Series | None]) -> None:
    """Pretty-print the optimal configurations."""
    labels = {
        "max_pm": "Max Phase Margin",
        "max_gm": "Max Gain Margin",
        "max_bw": "Max Bandwidth",
        "min_pole": "Most Robust (min pole mag)",
        "min_noise_bw": "Best Noise Rejection (min noise BW)",
        "min_peak_sens": "Least Noise Amplification (min Ms)",
        "min_lock_time": "Fastest Lock (min lock time)",
    }
    metric_keys = {
        "max_pm": "phase_margin",
        "max_gm": "gain_margin",
        "max_bw": "bandwidth",
        "min_pole": "max_pole_mag",
        "min_noise_bw": "noise_bandwidth",
        "min_peak_sens": "peak_sensitivity",
        "min_lock_time": "lock_time",
    }
    units = {
        "max_pm": "deg",
        "max_gm": "dB",
        "max_bw": "rad/s",
        "min_pole": "",
        "min_noise_bw": "rad/s",
        "min_peak_sens": "",
        "min_lock_time": "s",
    }
    param_names = [
        "alpha_f", "alpha_v", "beta_f", "beta_v", "kf", "kv", "tau", "wc",
    ]

    print("=== Optimal Configurations ===\n")
    for key, label in labels.items():
        row = best[key]
        if row is None:
            print(f"{label}: no valid configuration found\n")
            continue
        mk = metric_keys[key]
        u = units[key]
        print(f"{label} = {row[mk]:.4f} {u}:")
        params = ", ".join(f"{p}={row[p]:.4g}" for p in param_names)
        print(f"  {params}\n")


# ---------------------------------------------------------------------------
# Section 6: Pareto front
# ---------------------------------------------------------------------------


def find_pareto_front(
    obj1: np.ndarray, obj2: np.ndarray
) -> np.ndarray:
    """Find Pareto-optimal indices (maximizing both objectives).

    Uses an O(n log n) sweep: sort descending by obj1, then track the
    running maximum of obj2.  A point is Pareto-optimal iff its obj2
    value is strictly greater than the best obj2 seen so far (among
    points with higher obj1).

    Returns sorted indices (descending by obj1).
    """
    valid = ~(np.isnan(obj1) | np.isnan(obj2))
    valid_idx = np.where(valid)[0]
    if len(valid_idx) == 0:
        return np.array([], dtype=int)

    # Sort valid points by obj1 descending (ties broken by obj2 descending)
    order = np.lexsort((-obj2[valid_idx], -obj1[valid_idx]))
    sorted_idx = valid_idx[order]

    pareto = []
    max_obj2 = -np.inf
    for idx in sorted_idx:
        if obj2[idx] > max_obj2:
            pareto.append(idx)
            max_obj2 = obj2[idx]

    return np.array(pareto, dtype=int)


# ---------------------------------------------------------------------------
# Section 7: Visualization
# ---------------------------------------------------------------------------


def create_visualizations(
    df: pd.DataFrame,
    cfg: SweepConfig,
    output_dir: Path,
) -> None:
    """Generate 6 matplotlib figures and save to output_dir."""
    import matplotlib.pyplot as plt

    stable = df[df["stable"]]
    unstable = df[~df["stable"]]
    approx_label = cfg.approx.upper()

    # -- Figure 1: Stability heatmap alpha_f vs kf --
    fig, ax = plt.subplots(figsize=(8, 6))
    af_vals = np.sort(df["alpha_f"].unique())
    kf_vals = np.sort(df["kf"].unique())
    mat = np.zeros((len(af_vals), len(kf_vals)))
    for i, af in enumerate(af_vals):
        for j, kf in enumerate(kf_vals):
            mask = (np.abs(df["alpha_f"] - af) < 1e-10) & (
                np.abs(df["kf"] - kf) < 1e-10
            )
            subset = df[mask]
            mat[i, j] = subset["stable"].mean() if len(subset) else 0
    im = ax.imshow(
        mat,
        aspect="auto",
        origin="lower",
        extent=[
            np.log10(kf_vals[0]),
            np.log10(kf_vals[-1]),
            af_vals[0],
            af_vals[-1],
        ],
        cmap="viridis",
    )
    fig.colorbar(im, ax=ax, label="Stability probability")
    ax.set_xlabel(r"$\log_{10}(K_f)$")
    ax.set_ylabel(r"$\alpha_f$")
    ax.set_title(f"{approx_label}: Stability Probability (avg over other params)")
    fig.tight_layout()
    fig.savefig(output_dir / f"{cfg.approx}_fig1_heatmap_af_kf.png", dpi=150)
    plt.close(fig)

    # -- Figure 2: Stability heatmap alpha_f vs alpha_v --
    fig, ax = plt.subplots(figsize=(8, 6))
    av_vals = np.sort(df["alpha_v"].unique())
    mat2 = np.zeros((len(af_vals), len(av_vals)))
    for i, af in enumerate(af_vals):
        for j, av in enumerate(av_vals):
            mask = (np.abs(df["alpha_f"] - af) < 1e-10) & (
                np.abs(df["alpha_v"] - av) < 1e-10
            )
            subset = df[mask]
            mat2[i, j] = subset["stable"].mean() if len(subset) else 0
    im = ax.imshow(
        mat2,
        aspect="auto",
        origin="lower",
        extent=[av_vals[0], av_vals[-1], af_vals[0], af_vals[-1]],
        cmap="viridis",
    )
    fig.colorbar(im, ax=ax, label="Stability probability")
    ax.set_xlabel(r"$\alpha_v$ (VCO)")
    ax.set_ylabel(r"$\alpha_f$ (Filter)")
    ax.set_title(f"{approx_label}: Stability Probability (alpha_f vs alpha_v)")
    fig.tight_layout()
    fig.savefig(output_dir / f"{cfg.approx}_fig2_heatmap_af_av.png", dpi=150)
    plt.close(fig)

    # -- Figure 3: Scatter — stable vs unstable (3 sub-plots) --
    # Downsample to avoid matplotlib hanging on millions of markers
    _MAX_SCATTER = 20_000
    stable_s = stable.sample(n=min(len(stable), _MAX_SCATTER), random_state=42) if not stable.empty else stable
    unstable_s = unstable.sample(n=min(len(unstable), _MAX_SCATTER), random_state=42) if not unstable.empty else unstable

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    ax = axes[0]
    if not stable_s.empty:
        ax.scatter(
            stable_s["alpha_f"],
            np.log10(stable_s["kf"]),
            s=15,
            c="green",
            alpha=0.3,
            label="Stable",
        )
    if not unstable_s.empty:
        ax.scatter(
            unstable_s["alpha_f"],
            np.log10(unstable_s["kf"]),
            s=5,
            c="red",
            alpha=0.1,
            label="Unstable",
        )
    ax.set_xlabel(r"$\alpha_f$")
    ax.set_ylabel(r"$\log_{10}(K_f)$")
    ax.set_title(r"$\alpha_f$ vs $K_f$")
    ax.legend()
    ax.grid(True)

    ax = axes[1]
    if not stable_s.empty:
        ax.scatter(
            stable_s["alpha_f"],
            stable_s["alpha_v"],
            s=15,
            c="green",
            alpha=0.3,
            label="Stable",
        )
    if not unstable_s.empty:
        ax.scatter(
            unstable_s["alpha_f"],
            unstable_s["alpha_v"],
            s=5,
            c="red",
            alpha=0.1,
            label="Unstable",
        )
    ax.set_xlabel(r"$\alpha_f$")
    ax.set_ylabel(r"$\alpha_v$")
    ax.set_title(r"$\alpha_f$ vs $\alpha_v$")
    ax.legend()
    ax.grid(True)

    ax = axes[2]
    if not stable_s.empty:
        ax.scatter(
            np.log10(stable_s["tau"]),
            np.log10(stable_s["wc"]),
            s=15,
            c="green",
            alpha=0.3,
            label="Stable",
        )
    if not unstable_s.empty:
        ax.scatter(
            np.log10(unstable_s["tau"]),
            np.log10(unstable_s["wc"]),
            s=5,
            c="red",
            alpha=0.1,
            label="Unstable",
        )
    ax.set_xlabel(r"$\log_{10}(\tau)$")
    ax.set_ylabel(r"$\log_{10}(\omega_c)$")
    ax.set_title(r"$\tau$ vs $\omega_c$")
    ax.legend()
    ax.grid(True)

    fig.suptitle(f"{approx_label}: Stable vs Unstable Regions")
    fig.tight_layout()
    fig.savefig(output_dir / f"{cfg.approx}_fig3_scatter_regions.png", dpi=150)
    plt.close(fig)

    if stable.empty:
        print("  No stable configurations — skipping performance plots.")
        return

    # -- Figure 4: Performance metrics (4 sub-plots) --
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))

    ax = axes[0, 0]
    valid = stable.dropna(subset=["phase_margin"])
    if not valid.empty:
        valid_s = valid.sample(n=min(len(valid), _MAX_SCATTER), random_state=42)
        sc = ax.scatter(
            valid_s["alpha_f"],
            valid_s["phase_margin"],
            s=30,
            c=valid_s["kf"],
            cmap="viridis",
        )
        fig.colorbar(sc, ax=ax, label=r"$K_f$")
    ax.set_xlabel(r"$\alpha_f$")
    ax.set_ylabel("Phase Margin (deg)")
    ax.set_title(r"Phase Margin vs $\alpha_f$")
    ax.grid(True)

    ax = axes[0, 1]
    valid = stable.dropna(subset=["bandwidth"])
    if not valid.empty:
        valid_s = valid.sample(n=min(len(valid), _MAX_SCATTER), random_state=42)
        sc = ax.scatter(
            valid_s["alpha_v"],
            valid_s["bandwidth"],
            s=30,
            c=np.log10(valid_s["wc"]),
            cmap="viridis",
        )
        fig.colorbar(sc, ax=ax, label=r"$\log_{10}(\omega_c)$")
    ax.set_xlabel(r"$\alpha_v$")
    ax.set_ylabel("Bandwidth (rad/s)")
    ax.set_title(r"Bandwidth vs $\alpha_v$")
    ax.grid(True)

    ax = axes[1, 0]
    valid = stable.dropna(subset=["phase_margin", "bandwidth"])
    if not valid.empty:
        valid_s = valid.sample(n=min(len(valid), _MAX_SCATTER), random_state=42)
        sc = ax.scatter(
            valid_s["phase_margin"],
            valid_s["bandwidth"],
            s=30,
            c=valid_s["alpha_f"],
            cmap="viridis",
        )
        fig.colorbar(sc, ax=ax, label=r"$\alpha_f$")
    ax.set_xlabel("Phase Margin (deg)")
    ax.set_ylabel("Bandwidth (rad/s)")
    ax.set_title("PM vs BW Trade-off")
    ax.grid(True)

    ax = axes[1, 1]
    ax.hist(stable["max_pole_mag"], bins=30, edgecolor="black")
    ax.axvline(1.0, color="red", linestyle="--", linewidth=2)
    ax.set_xlabel("Max Pole Magnitude")
    ax.set_ylabel("Count")
    ax.set_title("Distribution of Max Pole Magnitudes")
    ax.grid(True)

    fig.suptitle(f"{approx_label}: Performance Metrics (Stable Configs)")
    fig.tight_layout()
    fig.savefig(output_dir / f"{cfg.approx}_fig4_performance.png", dpi=150)
    plt.close(fig)

    # -- Figure 5: 3D stability region --
    valid = stable.dropna(subset=["phase_margin"])
    if not valid.empty and len(valid) < 50000:
        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection="3d")
        sc = ax.scatter(
            valid["alpha_f"],
            valid["alpha_v"],
            np.log10(valid["tau"]),
            s=30,
            c=valid["phase_margin"],
            cmap="viridis",
        )
        fig.colorbar(sc, ax=ax, label="Phase Margin (deg)", shrink=0.6)
        ax.set_xlabel(r"$\alpha_f$")
        ax.set_ylabel(r"$\alpha_v$")
        ax.set_zlabel(r"$\log_{10}(\tau)$")
        ax.set_title(f"{approx_label}: 3D Stable Region")
        ax.view_init(elev=30, azim=45)
        fig.tight_layout()
        fig.savefig(
            output_dir / f"{cfg.approx}_fig5_3d_stability.png", dpi=150
        )
        plt.close(fig)

    # -- Figure 6: Pareto front (PM vs BW) --
    valid = stable.dropna(subset=["phase_margin", "bandwidth"])
    if len(valid) > 1:
        pm_arr = valid["phase_margin"].values
        bw_arr = valid["bandwidth"].values
        pidx = find_pareto_front(pm_arr, bw_arr)

        # Downsample background scatter, but always keep Pareto points
        fig, ax = plt.subplots(figsize=(8, 6))
        if len(valid) > _MAX_SCATTER:
            idx = np.random.default_rng(42).choice(len(valid), _MAX_SCATTER, replace=False)
        else:
            idx = np.arange(len(valid))
        sc = ax.scatter(
            pm_arr[idx],
            bw_arr[idx],
            s=20,
            c=valid["alpha_f"].values[idx],
            cmap="viridis",
            alpha=0.5,
        )
        fig.colorbar(sc, ax=ax, label=r"$\alpha_f$")
        ax.scatter(
            pm_arr[pidx],
            bw_arr[pidx],
            s=60,
            facecolors="none",
            edgecolors="red",
            linewidths=2,
            label="Pareto optimal",
        )
        ax.set_xlabel("Phase Margin (deg)")
        ax.set_ylabel("Bandwidth (rad/s)")
        ax.set_title(f"{approx_label}: Pareto Front — PM vs BW")
        ax.legend()
        ax.grid(True)
        fig.tight_layout()
        fig.savefig(output_dir / f"{cfg.approx}_fig6_pareto.png", dpi=150)
        plt.close(fig)

    # -- Figure 7: Noise metrics (4 sub-plots) --
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))

    # Noise bandwidth vs alpha_f
    ax = axes[0, 0]
    valid = stable.dropna(subset=["noise_bandwidth"])
    valid = valid[valid["noise_bandwidth"] > 0]
    if not valid.empty:
        valid_s = valid.sample(n=min(len(valid), _MAX_SCATTER), random_state=42)
        sc = ax.scatter(
            valid_s["alpha_f"],
            np.log10(valid_s["noise_bandwidth"]),
            s=30,
            c=np.log10(valid_s["tau"]),
            cmap="viridis",
        )
        fig.colorbar(sc, ax=ax, label=r"$\log_{10}(\tau)$")
    ax.set_xlabel(r"$\alpha_f$")
    ax.set_ylabel(r"$\log_{10}(B_n)$ (rad/s)")
    ax.set_title(r"Noise Bandwidth vs $\alpha_f$")
    ax.grid(True)

    # Peak sensitivity vs alpha_f
    ax = axes[0, 1]
    valid = stable.dropna(subset=["peak_sensitivity"])
    if not valid.empty:
        valid_s = valid.sample(n=min(len(valid), _MAX_SCATTER), random_state=42)
        sc = ax.scatter(
            valid_s["alpha_f"],
            valid_s["peak_sensitivity"],
            s=30,
            c=valid_s["phase_margin"],
            cmap="viridis",
        )
        fig.colorbar(sc, ax=ax, label="Phase Margin (deg)")
        ax.axhline(2.0, color="red", linestyle="--", linewidth=1.5, label="Ms = 2.0")
        ax.legend()
    ax.set_xlabel(r"$\alpha_f$")
    ax.set_ylabel(r"$M_s$ (peak sensitivity)")
    ax.set_title(r"Peak Sensitivity vs $\alpha_f$")
    ax.grid(True)

    # Lock time vs bandwidth
    ax = axes[1, 0]
    valid = stable.dropna(subset=["lock_time", "bandwidth"])
    valid = valid[(valid["lock_time"] > 0) & (valid["bandwidth"] > 0)]
    if not valid.empty:
        valid_s = valid.sample(n=min(len(valid), _MAX_SCATTER), random_state=42)
        sc = ax.scatter(
            np.log10(valid_s["bandwidth"]),
            np.log10(valid_s["lock_time"]),
            s=30,
            c=valid_s["alpha_f"],
            cmap="viridis",
        )
        fig.colorbar(sc, ax=ax, label=r"$\alpha_f$")
    ax.set_xlabel(r"$\log_{10}$(Bandwidth) (rad/s)")
    ax.set_ylabel(r"$\log_{10}$(Lock Time) (s)")
    ax.set_title("Lock Time vs Bandwidth")
    ax.grid(True)

    # BW / Bn ratio histogram (noise efficiency — ideal is close to 1)
    ax = axes[1, 1]
    valid = stable.dropna(subset=["bandwidth", "noise_bandwidth"])
    valid = valid[(valid["bandwidth"] > 0) & (valid["noise_bandwidth"] > 0)]
    if not valid.empty:
        ratio = valid["noise_bandwidth"] / valid["bandwidth"]
        ratio = ratio[np.isfinite(ratio) & (ratio > 0)]
        if not ratio.empty:
            ax.hist(np.log10(ratio), bins=30, edgecolor="black")
            ax.axvline(
                np.log10(np.pi / 2), color="red", linestyle="--",
                linewidth=1.5, label=r"$\pi/2$ (2nd-order optimal)",
            )
            ax.legend()
    ax.set_xlabel(r"$\log_{10}(B_n / BW)$")
    ax.set_ylabel("Count")
    ax.set_title("Noise Efficiency Ratio")
    ax.grid(True)

    fig.suptitle(f"{approx_label}: Noise Metrics (Stable Configs)")
    fig.tight_layout()
    fig.savefig(output_dir / f"{cfg.approx}_fig7_noise_metrics.png", dpi=150)
    plt.close(fig)

    # -- Figure 8: Pareto front (BW vs Noise BW) --
    # Maximize BW, minimize Noise BW → maximize BW, maximize -Bn
    valid = stable.dropna(subset=["bandwidth", "noise_bandwidth"])
    valid = valid[(valid["bandwidth"] > 1.0) & (valid["noise_bandwidth"] > 0)]
    if len(valid) > 1:
        bw_arr = valid["bandwidth"].values
        neg_bn = -valid["noise_bandwidth"].values  # minimize Bn = maximize -Bn
        pidx = find_pareto_front(bw_arr, neg_bn)

        fig, ax = plt.subplots(figsize=(8, 6))
        if len(valid) > _MAX_SCATTER:
            idx = np.random.default_rng(42).choice(len(valid), _MAX_SCATTER, replace=False)
        else:
            idx = np.arange(len(valid))
        bn_arr = valid["noise_bandwidth"].values
        sc = ax.scatter(
            np.log10(bw_arr[idx]),
            np.log10(bn_arr[idx]),
            s=20,
            c=valid["alpha_f"].values[idx],
            cmap="viridis",
            alpha=0.5,
        )
        fig.colorbar(sc, ax=ax, label=r"$\alpha_f$")
        ax.scatter(
            np.log10(bw_arr[pidx]),
            np.log10(bn_arr[pidx]),
            s=60,
            facecolors="none",
            edgecolors="red",
            linewidths=2,
            label="Pareto optimal",
        )
        ax.set_xlabel(r"$\log_{10}$(Bandwidth) (rad/s)")
        ax.set_ylabel(r"$\log_{10}$(Noise Bandwidth) (rad/s)")
        ax.set_title(f"{approx_label}: Pareto Front — BW vs Noise BW")
        ax.legend()
        ax.grid(True)
        fig.tight_layout()
        fig.savefig(output_dir / f"{cfg.approx}_fig8_pareto_bw_bn.png", dpi=150)
        plt.close(fig)


def create_comparison_visualizations(
    df: pd.DataFrame,
    output_dir: Path,
    type_counts: dict[str, tuple[int, int]] | None = None,
) -> None:
    """Generate comparison-specific plots across all 4 approximation types.

    Args:
        df: DataFrame of **stable** results (all rows have ``stable=True``).
        output_dir: Directory for output PNGs.
        type_counts: Mapping ``{approx: (total, stable_count)}``.  Used for
            the stability-rate bar chart.
    """
    import matplotlib.pyplot as plt

    approx_types = ["foa", "soa", "cfoa", "csoa"]
    colors = {"foa": "#1f77b4", "soa": "#ff7f0e", "cfoa": "#2ca02c", "csoa": "#d62728"}

    # -- Figure 1: Bar chart — stability rate per type --
    fig, ax = plt.subplots(figsize=(8, 5))
    rates = []
    for a in approx_types:
        if type_counts and a in type_counts:
            tot, stab = type_counts[a]
            rates.append(100 * stab / tot if tot else 0)
        else:
            sub = df[df["approx"] == a]
            rates.append(100 * sub["stable"].mean() if len(sub) else 0)
    bars = ax.bar(
        [a.upper() for a in approx_types],
        rates,
        color=[colors[a] for a in approx_types],
        edgecolor="black",
    )
    for bar, rate in zip(bars, rates):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.5,
            f"{rate:.1f}%",
            ha="center",
            va="bottom",
            fontweight="bold",
        )
    ax.set_ylabel("Stability Rate (%)")
    ax.set_title("Stability Rate by Approximation Type")
    ax.set_ylim(0, max(rates) * 1.15 if max(rates) > 0 else 10)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_dir / "compare_fig1_stability_rate.png", dpi=150)
    plt.close(fig)

    # -- Figure 2: Box plots — PM, BW, GM, pole mag, noise metrics --
    # df may already contain only stable rows (memory-efficient mode)
    stable = df[df["stable"]] if "stable" in df.columns else df
    metrics = [
        ("phase_margin", "Phase Margin (deg)"),
        ("bandwidth", "Bandwidth (rad/s)"),
        ("gain_margin", "Gain Margin (dB)"),
        ("max_pole_mag", "Max Pole Magnitude"),
        ("noise_bandwidth", "Noise Bandwidth (rad/s)"),
        ("peak_sensitivity", "Peak Sensitivity (Ms)"),
        ("lock_time", "Lock Time (s)"),
    ]
    n_metrics = len(metrics)
    n_cols = 3
    n_rows = (n_metrics + n_cols - 1) // n_cols
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(15, 4 * n_rows))
    axes_flat = axes.flat
    for ax, (metric, label) in zip(axes_flat, metrics):
        data_per_type = []
        labels_present = []
        for a in approx_types:
            sub = stable[stable["approx"] == a].dropna(subset=[metric])
            if not sub.empty:
                data_per_type.append(sub[metric].values)
                labels_present.append(a.upper())
        if data_per_type:
            bp = ax.boxplot(data_per_type, labels=labels_present, patch_artist=True)
            for patch, a in zip(bp["boxes"], [a.lower() for a in labels_present]):
                patch.set_facecolor(colors.get(a, "gray"))
                patch.set_alpha(0.7)
        ax.set_ylabel(label)
        ax.set_title(label)
        ax.grid(axis="y", alpha=0.3)
    # Hide unused subplot axes
    for i in range(n_metrics, n_rows * n_cols):
        axes.flat[i].set_visible(False)
    fig.suptitle("Performance Distributions by Approximation Type")
    fig.tight_layout()
    fig.savefig(output_dir / "compare_fig2_boxplots.png", dpi=150)
    plt.close(fig)

    # -- Figure 3: Best-type heatmap (alpha_f vs alpha_v → best PM type) --
    af_vals = np.sort(df["alpha_f"].unique())
    av_vals = np.sort(df["alpha_v"].unique())
    type_to_int = {"foa": 0, "soa": 1, "cfoa": 2, "csoa": 3}
    best_mat = np.full((len(af_vals), len(av_vals)), np.nan)
    for i, af in enumerate(af_vals):
        for j, av in enumerate(av_vals):
            mask = (
                (np.abs(stable["alpha_f"] - af) < 1e-10)
                & (np.abs(stable["alpha_v"] - av) < 1e-10)
            )
            sub = stable[mask].dropna(subset=["phase_margin"])
            if not sub.empty:
                best_idx = sub["phase_margin"].idxmax()
                best_mat[i, j] = type_to_int.get(sub.loc[best_idx, "approx"], np.nan)

    if not np.all(np.isnan(best_mat)):
        from matplotlib.colors import ListedColormap

        cmap = ListedColormap([colors[a] for a in approx_types])
        fig, ax = plt.subplots(figsize=(8, 6))
        im = ax.imshow(
            best_mat,
            aspect="auto",
            origin="lower",
            extent=[av_vals[0], av_vals[-1], af_vals[0], af_vals[-1]],
            cmap=cmap,
            vmin=-0.5,
            vmax=3.5,
            interpolation="nearest",
        )
        cbar = fig.colorbar(im, ax=ax, ticks=[0, 1, 2, 3])
        cbar.ax.set_yticklabels([a.upper() for a in approx_types])
        ax.set_xlabel(r"$\alpha_v$ (VCO)")
        ax.set_ylabel(r"$\alpha_f$ (Filter)")
        ax.set_title("Best Approx Type by Phase Margin (per alpha pair)")
        fig.tight_layout()
        fig.savefig(output_dir / "compare_fig3_best_type_heatmap.png", dpi=150)
        plt.close(fig)

    # -- Figure 4: PM vs BW scatter by type --
    valid = stable.dropna(subset=["phase_margin", "bandwidth"])
    if not valid.empty:
        fig, ax = plt.subplots(figsize=(8, 6))
        for a in approx_types:
            sub = valid[valid["approx"] == a]
            if not sub.empty:
                ax.scatter(
                    sub["phase_margin"],
                    sub["bandwidth"],
                    s=20,
                    c=colors[a],
                    alpha=0.4,
                    label=a.upper(),
                )
        ax.set_xlabel("Phase Margin (deg)")
        ax.set_ylabel("Bandwidth (rad/s)")
        ax.set_title("PM vs BW Trade-off by Approximation Type")
        ax.legend()
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(output_dir / "compare_fig4_pm_bw_scatter.png", dpi=150)
        plt.close(fig)


# ---------------------------------------------------------------------------
# Section 8: Rules-of-thumb analysis
# ---------------------------------------------------------------------------


def analyze_rules_of_thumb(df: pd.DataFrame, approx: str) -> list[str]:
    """Compute statistical rules of thumb from sweep results.

    Returns a list of plain-English rule strings.
    """
    rules: list[str] = []
    stable = df[df["stable"]]
    total = len(df)
    stable_count = len(stable)

    if stable_count == 0:
        rules.append(
            f"No stable configurations found for {approx.upper()}."
        )
        return rules

    rules.append(
        f"{approx.upper()}: {stable_count:,}/{total:,} "
        f"({100 * stable_count / total:.1f}%) configurations are stable."
    )

    # Parameter sensitivity (correlation with stability)
    param_names = ["alpha_f", "alpha_v", "kf", "kv", "tau", "wc"]
    if approx in ("cfoa", "csoa"):
        param_names += ["beta_f", "beta_v", "w"]

    rules.append("")
    rules.append("Parameter sensitivity (correlation with stability):")
    for p in param_names:
        corr = df[p].corr(df["stable"].astype(float))
        if abs(corr) > 0.05:
            direction = "increases" if corr > 0 else "decreases"
            rules.append(
                f"  - Increasing {p} {direction} stability "
                f"(r = {corr:+.3f})"
            )

    # Stability boundaries per parameter
    rules.append("")
    rules.append("Stability boundaries (>50% stable region):")
    for p in param_names:
        vals = np.sort(df[p].unique())
        stable_fracs = []
        for v in vals:
            mask = np.abs(df[p] - v) < 1e-10 * max(1, abs(v))
            subset = df[mask]
            stable_fracs.append(subset["stable"].mean() if len(subset) else 0)
        stable_fracs = np.array(stable_fracs)
        good = vals[stable_fracs > 0.5]
        if len(good) > 0:
            rules.append(f"  - {p}: stable region [{good[0]:.4g}, {good[-1]:.4g}]")
        else:
            best_val = vals[np.argmax(stable_fracs)]
            rules.append(
                f"  - {p}: no >50% region; peak stability "
                f"at {best_val:.4g} ({stable_fracs.max():.1%})"
            )

    # Metric correlations for stable configs
    metrics = [
        "phase_margin", "gain_margin", "bandwidth",
        "noise_bandwidth", "peak_sensitivity", "lock_time",
    ]
    rules.append("")
    rules.append("Metric correlations (among stable configs):")
    for m in metrics:
        valid = stable.dropna(subset=[m])
        if len(valid) < 10:
            continue
        for p in param_names:
            corr = valid[p].corr(valid[m])
            if abs(corr) > 0.1:
                direction = "increases" if corr > 0 else "decreases"
                rules.append(
                    f"  - {p} {direction} {m} (r = {corr:+.3f})"
                )

    # PM-BW trade-off
    valid = stable.dropna(subset=["phase_margin", "bandwidth"])
    if len(valid) > 10:
        corr = valid["phase_margin"].corr(valid["bandwidth"])
        if corr < -0.1:
            rules.append(
                f"\nPM-BW trade-off: negative correlation (r = {corr:+.3f}) "
                f"— higher phase margin tends to reduce bandwidth."
            )
        elif corr > 0.1:
            rules.append(
                f"\nPM-BW synergy: positive correlation (r = {corr:+.3f}) "
                f"— phase margin and bandwidth increase together."
            )
        else:
            rules.append(
                f"\nPM-BW trade-off: weak correlation (r = {corr:+.3f})."
            )

    # BW vs Noise BW trade-off
    valid = stable.dropna(subset=["bandwidth", "noise_bandwidth"])
    valid = valid[(valid["bandwidth"] > 0) & (valid["noise_bandwidth"] > 0)]
    if len(valid) > 10:
        corr = valid["bandwidth"].corr(valid["noise_bandwidth"])
        ratio = valid["noise_bandwidth"] / valid["bandwidth"]
        rules.append(
            f"\nBW-Noise BW correlation: r = {corr:+.3f}"
        )
        rules.append(
            f"  Bn/BW ratio: mean={ratio.mean():.2f}, "
            f"median={ratio.median():.2f}, min={ratio.min():.2f}"
        )
        rules.append(
            f"  (ideal 2nd-order PLL has Bn/BW = pi/2 = {np.pi/2:.2f})"
        )

    # Peak sensitivity summary
    valid = stable.dropna(subset=["peak_sensitivity"])
    if len(valid) > 10:
        good_ms = valid[valid["peak_sensitivity"] < 2.0]
        rules.append(
            f"\nPeak sensitivity (Ms): "
            f"mean={valid['peak_sensitivity'].mean():.2f}, "
            f"min={valid['peak_sensitivity'].min():.2f}"
        )
        rules.append(
            f"  Configs with Ms < 2.0 (good noise rejection): "
            f"{len(good_ms):,} ({100 * len(good_ms) / len(valid):.1f}%)"
        )

    # Lock time summary
    valid = stable.dropna(subset=["lock_time"])
    valid = valid[valid["lock_time"] > 0]
    if len(valid) > 10:
        rules.append(
            f"\nLock time: mean={valid['lock_time'].mean():.2e} s, "
            f"min={valid['lock_time'].min():.2e} s, "
            f"median={valid['lock_time'].median():.2e} s"
        )

    return rules


def analyze_comparison(
    df: pd.DataFrame,
    type_counts: dict[str, tuple[int, int]] | None = None,
) -> list[str]:
    """Cross-type comparison analysis.

    Args:
        df: DataFrame of **stable** results (may contain only stable rows).
        type_counts: Mapping ``{approx: (total, stable_count)}``.

    Returns plain-English rules comparing all 4 approximation types.
    """
    approx_types = ["foa", "soa", "cfoa", "csoa"]
    rules: list[str] = []

    # --- Stability rate per type ---
    rules.append("=== Cross-Type Comparison ===")
    rules.append("")
    rules.append("Stability rate per type:")
    for a in approx_types:
        if type_counts and a in type_counts:
            tot, stab = type_counts[a]
            if tot == 0:
                continue
            rate = 100 * stab / tot
            rules.append(f"  {a.upper()}: {rate:.1f}%  ({stab:,}/{tot:,})")
        else:
            sub = df[df["approx"] == a]
            if len(sub) == 0:
                continue
            rate = 100 * sub["stable"].mean()
            count = int(sub["stable"].sum())
            rules.append(f"  {a.upper()}: {rate:.1f}%  ({count:,}/{len(sub):,})")

    # --- Head-to-head winners ---
    # Group by base parameters (everything except approx and metrics).
    # Uses a vectorized approach: create a composite group key from
    # rounded parameters, then use groupby + idxmax/idxmin per metric.
    base_params = [
        "alpha_f", "alpha_v", "beta_f", "beta_v",
        "kf", "kv", "tau", "wc", "w", "T",
    ]
    stable = df[df["stable"]].copy() if "stable" in df.columns and not df["stable"].all() else df.copy()

    if not stable.empty and len(stable) < 10_000_000:
        # Build a hashable group key from rounded params
        # (rounding avoids float precision issues in groupby)
        key_parts = []
        for p in base_params:
            rounded = stable[p].round(10).astype(str)
            key_parts.append(rounded)
        stable["_gkey"] = key_parts[0].str.cat(key_parts[1:], sep="|")

        # Count types per group to find contests (>= 2 types stable)
        group_sizes = stable.groupby("_gkey")["approx"].nunique()
        contest_keys = set(group_sizes[group_sizes >= 2].index)
        contest_df = stable[stable["_gkey"].isin(contest_keys)]
        total_contests = len(contest_keys)

        wins: dict[str, dict[str, int]] = {
            a: {"pm": 0, "bw": 0, "robustness": 0,
                "noise_bw": 0, "peak_sens": 0, "lock": 0}
            for a in approx_types
        }

        if total_contests > 0:
            # For each metric, find the winner per group vectorially
            gk = "_gkey"
            for metric_key, col, ascending in [
                ("pm", "phase_margin", False),
                ("bw", "bandwidth", False),
                ("robustness", "max_pole_mag", True),
                ("lock", "lock_time", True),
                ("noise_bw", "noise_bandwidth", True),
                ("peak_sens", "peak_sensitivity", True),
            ]:
                sub = contest_df.dropna(subset=[col])
                if ascending and col in ("noise_bandwidth", "lock_time"):
                    sub = sub[sub[col] > 0]
                if sub.empty:
                    continue
                if ascending:
                    idx = sub.groupby(gk)[col].idxmin()
                else:
                    idx = sub.groupby(gk)[col].idxmax()
                winner_types = sub.loc[idx, "approx"]
                for a in approx_types:
                    wins[a][metric_key] = int((winner_types == a).sum())

            rules.append("")
            rules.append(
                f"Head-to-head winners ({total_contests:,} contests "
                f"where >= 2 types are stable):"
            )
            for metric_label, metric_key in [
                ("Phase Margin", "pm"),
                ("Bandwidth", "bw"),
                ("Robustness", "robustness"),
                ("Noise Rejection (min Bn)", "noise_bw"),
                ("Noise Amplification (min Ms)", "peak_sens"),
                ("Lock Time (fastest)", "lock"),
            ]:
                winner_parts = []
                for a in approx_types:
                    cnt = wins[a][metric_key]
                    if cnt > 0:
                        pct = 100 * cnt / total_contests
                        winner_parts.append(f"{a.upper()}: {cnt} ({pct:.0f}%)")
                rules.append(f"  {metric_label}: {', '.join(winner_parts)}")

        stable.drop(columns=["_gkey"], inplace=True, errors="ignore")

        # --- Best type per metric (overall) ---
        rules.append("")
        rules.append("Best type per metric (overall across all stable configs):")

        # Best avg PM
        pm_avgs = {}
        for a in approx_types:
            sub = stable[stable["approx"] == a].dropna(subset=["phase_margin"])
            if not sub.empty:
                pm_avgs[a] = sub["phase_margin"].mean()
        if pm_avgs:
            best = max(pm_avgs, key=pm_avgs.get)
            rules.append(
                f"  Avg Phase Margin: {best.upper()} ({pm_avgs[best]:.1f} deg)"
            )

        # Best avg BW
        bw_avgs = {}
        for a in approx_types:
            sub = stable[stable["approx"] == a].dropna(subset=["bandwidth"])
            if not sub.empty:
                bw_avgs[a] = sub["bandwidth"].mean()
        if bw_avgs:
            best = max(bw_avgs, key=bw_avgs.get)
            rules.append(
                f"  Avg Bandwidth: {best.upper()} ({bw_avgs[best]:.1f} rad/s)"
            )

        # Best avg robustness (lowest avg pole mag)
        pole_avgs = {}
        for a in approx_types:
            sub = stable[stable["approx"] == a]
            if not sub.empty:
                pole_avgs[a] = sub["max_pole_mag"].mean()
        if pole_avgs:
            best = min(pole_avgs, key=pole_avgs.get)
            rules.append(
                f"  Avg Robustness: {best.upper()} "
                f"(avg pole mag {pole_avgs[best]:.4f})"
            )

        # Best avg noise BW (lowest = best noise rejection)
        nb_avgs = {}
        for a in approx_types:
            sub = stable[stable["approx"] == a].dropna(subset=["noise_bandwidth"])
            sub = sub[sub["noise_bandwidth"] > 0]
            if not sub.empty:
                nb_avgs[a] = sub["noise_bandwidth"].mean()
        if nb_avgs:
            best = min(nb_avgs, key=nb_avgs.get)
            rules.append(
                f"  Avg Noise BW (lower=better): {best.upper()} "
                f"({nb_avgs[best]:.2f} rad/s)"
            )

        # Best avg peak sensitivity (lowest = least amplification)
        ps_avgs = {}
        for a in approx_types:
            sub = stable[stable["approx"] == a].dropna(subset=["peak_sensitivity"])
            if not sub.empty:
                ps_avgs[a] = sub["peak_sensitivity"].mean()
        if ps_avgs:
            best = min(ps_avgs, key=ps_avgs.get)
            rules.append(
                f"  Avg Peak Sensitivity (lower=better): {best.upper()} "
                f"(Ms = {ps_avgs[best]:.2f})"
            )

        # Best avg lock time (lowest = fastest)
        lt_avgs = {}
        for a in approx_types:
            sub = stable[stable["approx"] == a].dropna(subset=["lock_time"])
            sub = sub[sub["lock_time"] > 0]
            if not sub.empty:
                lt_avgs[a] = sub["lock_time"].mean()
        if lt_avgs:
            best = min(lt_avgs, key=lt_avgs.get)
            rules.append(
                f"  Avg Lock Time (lower=better): {best.upper()} "
                f"({lt_avgs[best]:.2e} s)"
            )

    return rules


# ---------------------------------------------------------------------------
# Section 9: CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for design space exploration."""
    warnings.filterwarnings("ignore", message="invalid value encountered in divide")
    warnings.filterwarnings("ignore", message="invalid value encountered in subtract")
    warnings.filterwarnings("ignore", message="An ill-conditioned matrix")
    warnings.filterwarnings("ignore", message="Badly conditioned filter")
    warnings.filterwarnings("ignore", category=FutureWarning)

    parser = argparse.ArgumentParser(
        description="Fractional-order PLL design space exploration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  pll-explore --approx foa
  pll-explore --approx soa --workers 4
  pll-explore --approx cfoa --small
  pll-explore --approx compare --small        # cross-type comparison
  pll-explore --approx foa --alpha-f-points 5 --kf-points 4
  pll-explore --approx foa --resume           # continue from partial CSV
""",
    )
    parser.add_argument(
        "--approx",
        choices=["foa", "soa", "cfoa", "csoa", "all", "compare"],
        default="foa",
        help=(
            "Approximation type to sweep (default: foa). "
            "'all' runs 4 independent sweeps. "
            "'compare' evaluates all 4 types per parameter combo for cross-comparison."
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of parallel workers (default: all CPUs).",
    )
    parser.add_argument(
        "--serial",
        action="store_true",
        help="Run single-threaded (useful for debugging).",
    )
    parser.add_argument(
        "--small",
        action="store_true",
        help="Use a small grid for quick testing (3x3x2x2x2x2x1x1).",
    )
    parser.add_argument(
        "--output-dir",
        default="exploration_results",
        help="Output directory for CSV and plots (default: exploration_results).",
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Skip plot generation.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume a previous run from its partial CSV output.",
    )
    # Fine-grained grid control
    parser.add_argument("--alpha-f-points", type=int, default=None)
    parser.add_argument("--alpha-v-points", type=int, default=None)
    parser.add_argument("--kf-points", type=int, default=None)
    parser.add_argument("--kv-points", type=int, default=None)
    parser.add_argument("--tau-points", type=int, default=None)
    parser.add_argument("--wc-points", type=int, default=None)
    parser.add_argument("--T-points", type=int, default=None)

    args = parser.parse_args()

    # Use non-interactive backend if no display
    if args.no_plots or os.environ.get("DISPLAY") is None:
        matplotlib.use("Agg")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ---- Compare mode: cross-type comparison ----
    if args.approx == "compare":
        cfg = SweepConfig(approx="compare", output_dir=args.output_dir)

        if args.serial:
            cfg.max_workers = 1
        elif args.workers:
            cfg.max_workers = args.workers

        if args.small:
            cfg.alpha_f_range = np.linspace(0.1, 0.9, 3)
            cfg.alpha_v_range = np.linspace(0.1, 0.9, 3)
            cfg.kf_range = np.logspace(-1, 2, 2)
            cfg.kv_range = np.logspace(-1, 2, 2)
            cfg.tau_range = np.logspace(-4, -1, 2)
            cfg.wc_range = np.logspace(1, 4, 2)
            cfg.T_range = np.array([1e-9])
            cfg.beta_f_range = np.linspace(0, 0.4, 2)
            cfg.beta_v_range = np.linspace(0, 0.4, 2)
            cfg.w_range = np.array([2 * np.pi * 1e4])

        # Apply fine-grained overrides
        if args.alpha_f_points:
            cfg.alpha_f_range = np.linspace(0.1, 0.9, args.alpha_f_points)
        if args.alpha_v_points:
            cfg.alpha_v_range = np.linspace(0.1, 0.9, args.alpha_v_points)
        if args.kf_points:
            cfg.kf_range = np.logspace(-1, 2, args.kf_points)
        if args.kv_points:
            cfg.kv_range = np.logspace(-1, 2, args.kv_points)
        if args.tau_points:
            cfg.tau_range = np.logspace(-4, -1, args.tau_points)
        if args.wc_points:
            cfg.wc_range = np.logspace(1, 4, args.wc_points)
        if args.T_points:
            cfg.T_range = np.logspace(-10, -8, args.T_points)

        print(f"\nParameter space for COMPARE mode:")
        print(f"  alpha_f:  {len(cfg.alpha_f_range)} points "
              f"[{cfg.alpha_f_range[0]:.2f} - {cfg.alpha_f_range[-1]:.2f}]")
        print(f"  alpha_v:  {len(cfg.alpha_v_range)} points "
              f"[{cfg.alpha_v_range[0]:.2f} - {cfg.alpha_v_range[-1]:.2f}]")
        print(f"  beta_f:   {len(cfg.beta_f_range)} points "
              f"[{cfg.beta_f_range[0]:.2f} - {cfg.beta_f_range[-1]:.2f}]")
        print(f"  beta_v:   {len(cfg.beta_v_range)} points "
              f"[{cfg.beta_v_range[0]:.2f} - {cfg.beta_v_range[-1]:.2f}]")
        print(f"  kf:       {len(cfg.kf_range)} points "
              f"[{cfg.kf_range[0]:.2g} - {cfg.kf_range[-1]:.2g}]")
        print(f"  kv:       {len(cfg.kv_range)} points "
              f"[{cfg.kv_range[0]:.2g} - {cfg.kv_range[-1]:.2g}]")
        print(f"  tau:      {len(cfg.tau_range)} points "
              f"[{cfg.tau_range[0]:.2e} - {cfg.tau_range[-1]:.2e}]")
        print(f"  wc:       {len(cfg.wc_range)} points "
              f"[{cfg.wc_range[0]:.2g} - {cfg.wc_range[-1]:.2g}]")
        print(f"  w:        {len(cfg.w_range)} points "
              f"[{cfg.w_range[0]:.2g} - {cfg.w_range[-1]:.2g}]")
        print(f"  T:        {len(cfg.T_range)} points "
              f"[{cfg.T_range[0]:.2e} - {cfg.T_range[-1]:.2e}]")
        print(f"  Types:    4 (FOA, SOA, CFOA, CSOA)")
        print(f"  Total:    {cfg.total_combinations:,}")

        # Run comparison sweep — results are incrementally saved to CSV
        compare_csv = output_dir / "compare_results_raw.csv"
        df, type_counts = run_comparison_sweep(
            cfg, csv_path=compare_csv, resume=args.resume
        )

        # Save scored/ranked CSV — top-10 first
        if not df.empty:
            csv_path = output_dir / "compare_results.csv"
            scored = add_composite_score(df)
            scored = scored.sort_values("rank")
            # Save top configs to ranked CSV (raw results in compare_results_raw.csv)
            top_n = min(10_000, len(scored))
            scored.head(top_n).to_csv(csv_path, index=False)
            print(f"Top {top_n:,} configs saved to {csv_path}")
            if len(scored) > top_n:
                print(f"  (full {len(scored):,} stable results in compare_results_raw.csv)")
            top10 = scored.head(10)
            print(f"\n=== Top 10 PLLs (composite score) ===\n")
            for _, row in top10.iterrows():
                print(
                    f"  Rank {int(row['rank']):>2d}  "
                    f"score={row['composite_score']:.3f}  "
                    f"[{row['approx'].upper():>4s}]  "
                    f"PM={row['phase_margin']:6.1f} deg  "
                    f"BW={row['bandwidth']:10.1f} rad/s  "
                    f"Bn={row['noise_bandwidth']:10.1f} rad/s  "
                    f"Ms={row['peak_sensitivity']:5.2f}  "
                    f"Lock={row['lock_time']:.2e} s  "
                    f"| af={row['alpha_f']:.2f} av={row['alpha_v']:.2f} "
                    f"kf={row['kf']:.2g} kv={row['kv']:.2g} "
                    f"tau={row['tau']:.1e} wc={row['wc']:.2g}"
                )
            print()

        # Best configs (across all types — df has only stable rows)
        try:
            best = find_best_configs(df)
            print_best_configs(best)
        except Exception as exc:
            print(f"Warning: could not compute best configs: {exc}")

        # Cross-type analysis
        all_rules: list[str] = []
        try:
            comp_rules = analyze_comparison(df, type_counts)
            all_rules = list(comp_rules)
            print()
            for r in comp_rules:
                print(r)
            print()
        except Exception as exc:
            print(f"Warning: cross-type analysis failed: {exc}")

        # Per-type metric summaries (stable-only; full rules-of-thumb
        # need all data so are skipped in compare mode to save memory)
        all_rules.append("")
        for approx in ("foa", "soa", "cfoa", "csoa"):
            tot, stab = type_counts.get(approx, (0, 0))
            sub = df[df["approx"] == approx] if not df.empty else df
            header = (
                f"{approx.upper()}: {stab:,}/{tot:,} "
                f"({100 * stab / tot:.1f}%) stable"
                if tot > 0
                else f"{approx.upper()}: no evaluations"
            )
            all_rules.append(header)
            print(header)
            if not sub.empty:
                # Metrics where higher is better
                for metric, label in [
                    ("phase_margin", "Phase Margin"),
                    ("bandwidth", "Bandwidth"),
                ]:
                    valid = sub.dropna(subset=[metric])
                    if not valid.empty:
                        line = (
                            f"  {label}: "
                            f"mean={valid[metric].mean():.2f}, "
                            f"median={valid[metric].median():.2f}, "
                            f"best={valid[metric].max():.2f}"
                        )
                        all_rules.append(line)
                        print(line)
                # Metrics where lower is better
                for metric, label in [
                    ("max_pole_mag", "Max Pole Mag"),
                    ("noise_bandwidth", "Noise BW"),
                    ("peak_sensitivity", "Peak Sensitivity"),
                    ("lock_time", "Lock Time"),
                ]:
                    valid = sub.dropna(subset=[metric])
                    if metric in ("noise_bandwidth", "lock_time"):
                        valid = valid[valid[metric] > 0]
                    if not valid.empty:
                        line = (
                            f"  {label}: "
                            f"mean={valid[metric].mean():.4g}, "
                            f"best={valid[metric].min():.4g}"
                        )
                        all_rules.append(line)
                        print(line)
            all_rules.append("")
            print()

        # Comparison plots
        if not args.no_plots:
            try:
                print("Generating comparison plots...")
                create_comparison_visualizations(df, output_dir, type_counts)
                print(f"Comparison plots saved to {output_dir}/\n")
            except Exception as exc:
                print(f"Warning: plot generation failed: {exc}")

        # Write rules to file
        rules_path = output_dir / "rules_of_thumb.txt"
        rules_path.write_text("\n".join(all_rules), encoding="utf-8")
        print(f"Rules of thumb saved to {rules_path}")
        return

    # ---- Single-type or "all" mode ----
    approx_types = (
        ["foa", "soa", "cfoa", "csoa"] if args.approx == "all" else [args.approx]
    )

    all_rules: list[str] = []

    for approx in approx_types:
        cfg = SweepConfig(approx=approx, output_dir=args.output_dir)

        if args.serial:
            cfg.max_workers = 1
        elif args.workers:
            cfg.max_workers = args.workers

        if args.small:
            cfg.alpha_f_range = np.linspace(0.1, 0.9, 3)
            cfg.alpha_v_range = np.linspace(0.1, 0.9, 3)
            cfg.kf_range = np.logspace(-1, 2, 2)
            cfg.kv_range = np.logspace(-1, 2, 2)
            cfg.tau_range = np.logspace(-4, -1, 2)
            cfg.wc_range = np.logspace(1, 4, 2)
            cfg.T_range = np.array([1e-9])
            if approx in ("cfoa", "csoa"):
                cfg.beta_f_range = np.linspace(0, 0.4, 2)
                cfg.beta_v_range = np.linspace(0, 0.4, 2)
                cfg.w_range = np.array([2 * np.pi * 1e4])

        # Apply fine-grained overrides
        if args.alpha_f_points:
            cfg.alpha_f_range = np.linspace(0.1, 0.9, args.alpha_f_points)
        if args.alpha_v_points:
            cfg.alpha_v_range = np.linspace(0.1, 0.9, args.alpha_v_points)
        if args.kf_points:
            cfg.kf_range = np.logspace(-1, 2, args.kf_points)
        if args.kv_points:
            cfg.kv_range = np.logspace(-1, 2, args.kv_points)
        if args.tau_points:
            cfg.tau_range = np.logspace(-4, -1, args.tau_points)
        if args.wc_points:
            cfg.wc_range = np.logspace(1, 4, args.wc_points)
        if args.T_points:
            cfg.T_range = np.logspace(-10, -8, args.T_points)

        print(f"\nParameter space for {approx.upper()}:")
        print(f"  alpha_f:  {len(cfg.alpha_f_range)} points "
              f"[{cfg.alpha_f_range[0]:.2f} - {cfg.alpha_f_range[-1]:.2f}]")
        print(f"  alpha_v:  {len(cfg.alpha_v_range)} points "
              f"[{cfg.alpha_v_range[0]:.2f} - {cfg.alpha_v_range[-1]:.2f}]")
        print(f"  beta_f:   {len(cfg.beta_f_range)} points "
              f"[{cfg.beta_f_range[0]:.2f} - {cfg.beta_f_range[-1]:.2f}]")
        print(f"  beta_v:   {len(cfg.beta_v_range)} points "
              f"[{cfg.beta_v_range[0]:.2f} - {cfg.beta_v_range[-1]:.2f}]")
        print(f"  kf:       {len(cfg.kf_range)} points "
              f"[{cfg.kf_range[0]:.2g} - {cfg.kf_range[-1]:.2g}]")
        print(f"  kv:       {len(cfg.kv_range)} points "
              f"[{cfg.kv_range[0]:.2g} - {cfg.kv_range[-1]:.2g}]")
        print(f"  tau:      {len(cfg.tau_range)} points "
              f"[{cfg.tau_range[0]:.2e} - {cfg.tau_range[-1]:.2e}]")
        print(f"  wc:       {len(cfg.wc_range)} points "
              f"[{cfg.wc_range[0]:.2g} - {cfg.wc_range[-1]:.2g}]")
        print(f"  w:        {len(cfg.w_range)} points "
              f"[{cfg.w_range[0]:.2g} - {cfg.w_range[-1]:.2g}]")
        print(f"  T:        {len(cfg.T_range)} points "
              f"[{cfg.T_range[0]:.2e} - {cfg.T_range[-1]:.2e}]")
        print(f"  Total:    {cfg.total_combinations:,}")

        # Run sweep — results are incrementally saved to CSV
        raw_csv = output_dir / f"{approx}_results_raw.csv"
        df = run_sweep(cfg, csv_path=raw_csv, resume=args.resume)

        # Save scored/ranked CSV — top-10 first
        csv_path = output_dir / f"{approx}_results.csv"
        stable_df = df[df["stable"]]
        if not stable_df.empty:
            scored = add_composite_score(stable_df)
            scored = scored.sort_values("rank")
            scored.to_csv(csv_path, index=False)
            print(f"Stable configs saved to {csv_path}")
            top10 = scored.head(10)
            print(f"\n=== Top 10 PLLs (composite score) ===\n")
            for _, row in top10.iterrows():
                print(
                    f"  Rank {int(row['rank']):>2d}  "
                    f"score={row['composite_score']:.3f}  "
                    f"PM={row['phase_margin']:6.1f} deg  "
                    f"BW={row['bandwidth']:10.1f} rad/s  "
                    f"Bn={row['noise_bandwidth']:10.1f} rad/s  "
                    f"Ms={row['peak_sensitivity']:5.2f}  "
                    f"Lock={row['lock_time']:.2e} s  "
                    f"| af={row['alpha_f']:.2f} av={row['alpha_v']:.2f} "
                    f"kf={row['kf']:.2g} kv={row['kv']:.2g} "
                    f"tau={row['tau']:.1e} wc={row['wc']:.2g}"
                )
            print()

        # Best configs
        best = find_best_configs(df)
        print_best_configs(best)

        # Pareto front — exclude degenerate configs (BW ≈ 0 are useless PLLs)
        valid = stable_df.dropna(subset=["phase_margin", "bandwidth"])
        valid = valid[valid["bandwidth"] > 1.0]
        if len(valid) > 1:
            pm_arr = valid["phase_margin"].values
            bw_arr = valid["bandwidth"].values
            pidx = find_pareto_front(pm_arr, bw_arr)
            print(f"Pareto-optimal configs (PM vs BW): {len(pidx)}")
            for k, pi in enumerate(pidx[:10]):
                row = valid.iloc[pi]
                print(
                    f"  [{k + 1}] PM={row['phase_margin']:.1f} deg, "
                    f"BW={row['bandwidth']:.1f} rad/s | "
                    f"alpha_f={row['alpha_f']:.2f}, "
                    f"alpha_v={row['alpha_v']:.2f}, "
                    f"kf={row['kf']:.2f}, kv={row['kv']:.2f}, "
                    f"tau={row['tau']:.2e}, wc={row['wc']:.2g}, "
                )
            print()

        # Pareto front — BW vs Noise BW (maximize BW, minimize Bn)
        valid = stable_df.dropna(subset=["bandwidth", "noise_bandwidth"])
        valid = valid[(valid["bandwidth"] > 1.0) & (valid["noise_bandwidth"] > 0)]
        if len(valid) > 1:
            bw_arr = valid["bandwidth"].values
            neg_bn = -valid["noise_bandwidth"].values
            pidx = find_pareto_front(bw_arr, neg_bn)
            print(f"Pareto-optimal configs (BW vs Noise BW): {len(pidx)}")
            for k, pi in enumerate(pidx[:10]):
                row = valid.iloc[pi]
                bn_bw = row["noise_bandwidth"] / row["bandwidth"]
                print(
                    f"  [{k + 1}] BW={row['bandwidth']:.1f} rad/s, "
                    f"Bn={row['noise_bandwidth']:.1f} rad/s, "
                    f"Bn/BW={bn_bw:.2f} | "
                    f"alpha_f={row['alpha_f']:.2f}, "
                    f"alpha_v={row['alpha_v']:.2f}, "
                    f"kf={row['kf']:.2f}, kv={row['kv']:.2f}, "
                    f"tau={row['tau']:.2e}, wc={row['wc']:.2g}, "
                )
            print()

        # Plots
        if not args.no_plots:
            print(f"Generating plots for {approx.upper()}...")
            create_visualizations(df, cfg, output_dir)
            print(f"Plots saved to {output_dir}/\n")

        # Rules of thumb
        rules = analyze_rules_of_thumb(df, approx)
        all_rules.extend(rules)
        all_rules.append("")

        print("=== Rules of Thumb ===")
        for r in rules:
            print(r)
        print()

    # Write rules to file
    rules_path = output_dir / "rules_of_thumb.txt"
    rules_path.write_text("\n".join(all_rules), encoding="utf-8")
    print(f"Rules of thumb saved to {rules_path}")


if __name__ == "__main__":
    main()
