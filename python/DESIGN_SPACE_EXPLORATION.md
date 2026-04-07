# Design Space Exploration for Fractional-Order PLL

## 1. Overview

This tool performs an exhaustive sweep of the fractional-order PLL parameter space to identify stable configurations with optimal phase margin, gain margin, bandwidth, and robustness. It is the Python port of `design_space_exploration_fast.m`.

Fractional-order PLLs replace the integer-order integrators/filters in a classical PLL with fractional-order operators `s^alpha` (where `0 < alpha < 1`). The El-Khazali approximation converts these irrational operators into rational transfer functions suitable for digital implementation. This tool explores which combinations of fractional orders and gains yield stable, high-performance PLLs.

## 2. PLL Architecture

```
            +-----+     +----+     +-----+
  ref -->( )--> | Gf  | --> | 1/s| --> | Gvco| --+--> output
          ^     +-----+     +----+     +-----+   |
          |               Filter    Integrator  VCO  |
          +------------------------------------------+
                         (unity feedback)
```

- **Filter (Gf):** `kf / (tau * s^alpha_f + 1)` — fractional-order low-pass filter
- **Integrator:** `1/s` — standard integrator (phase accumulation)
- **VCO (Gvco):** `kv / s^alpha_v` — fractional-order voltage-controlled oscillator

The open-loop transfer function is `Gc = Gf * (1/s) * Gvco`, and the closed-loop PLL is `Gpll = feedback(Gc, 1)`.

For complex-order types, the fractional exponent becomes `s^(alpha + j*beta)`, adding a frequency-dependent phase rotation controlled by the carrier frequency `w`.

## 3. Approximation Types

| Type | Abbr | Polynomial Degree | Parameters |
|------|------|------------------|------------|
| First-Order El-Khazali | FOA | 1/1 per operator | alpha, wc |
| Second-Order El-Khazali | SOA | 2/2 per operator | alpha, wc |
| Complex First-Order | CFOA | 3/3 per operator | alpha, beta, w, wc |
| Complex Second-Order | CSOA | 4+/4+ per operator | alpha, beta, w, wc |

Higher-order approximations are more accurate across a wider frequency range but produce higher-degree transfer functions (more poles/zeros to manage).

## 4. Parameter Space

| Parameter | Symbol | Range | Scale | Units | Physical Meaning |
|-----------|--------|-------|-------|-------|------------------|
| Filter order | alpha_f | 0.1 - 0.9 | linear | — | Fractional order of the loop filter |
| VCO order | alpha_v | 0.1 - 0.9 | linear | — | Fractional order of the VCO |
| Filter beta | beta_f | 0 - 0.4 | linear | — | Imaginary part (complex types only) |
| VCO beta | beta_v | 0 - 0.4 | linear | — | Imaginary part (complex types only) |
| Filter gain | kf | 0.1 - 100 | log | — | Loop filter gain |
| VCO gain | kv | 0.1 - 100 | log | Hz/V | VCO sensitivity |
| Time constant | tau | 1e-4 - 0.1 | log | s | Filter time constant |
| Corner freq | wc | 10 - 10000 | log | rad/s | El-Khazali approximation center |
| Carrier freq | w | 2pi*1e3 - 2pi*1e5 | log | rad/s | Complex-order carrier (CFOA/CSOA) |
| Sampling period | T | 1e-10 - 1e-8 | log | s | Discretization period |

Default grid sizes:
- **FOA/SOA (real):** 9 x 9 x 1 x 1 x 8 x 8 x 8 x 8 x 1 x 3 = ~995K configs
- **CFOA/CSOA (complex):** 9 x 9 x 5 x 5 x 8 x 8 x 8 x 8 x 4 x 3 = ~99M (use `--small` or reduce points)

## 5. Metrics

For each configuration, the tool computes:

| Metric | Source | Description | Direction |
|--------|--------|-------------|-----------|
| **Stability** | `max(abs(poles(Gpll_d))) < 1` | Discrete-time stability check | — |
| **Max pole magnitude** | `max(abs(poles(Gpll_d)))` | Distance from unit circle (robustness) | lower = better |
| **Phase margin** (deg) | `control.margin(Gc)` | Open-loop phase margin | higher = better |
| **Gain margin** (dB) | `control.margin(Gc)` | Open-loop gain margin | higher = better |
| **Bandwidth** (rad/s) | Closed-loop -3dB point | Closed-loop -3dB bandwidth | higher = better |
| **Noise bandwidth** (rad/s) | `(1/2pi) * integral |T(jw)|^2 dw` | Equivalent noise bandwidth | lower = better |
| **Peak sensitivity** (Ms) | `max |S(jw)|` where `S = 1/(1+Gc)` | Worst-case noise amplification | lower = better |
| **Lock time** (s) | Discrete step response 2% settling | Time to lock within 2% of final value | lower = better |

Stability is checked on the **discretized** closed-loop system (Tustin/bilinear transform), ensuring the design is valid for digital implementation.

A **composite score** (0-1) ranks configurations by percentile-averaging all metrics with equal weight. Configurations are ranked so that rank 1 is the best overall PLL.

## 6. How to Run

### `pll-explore` — Sweep the parameter space

```bash
# Install dependencies (from python/ directory)
python -m uv sync

# Quick test (small grid, ~100 configs)
uv run pll-explore --approx foa --small

# Full FOA sweep
uv run pll-explore --approx foa

# SOA with 4 workers, no plots
uv run pll-explore --approx soa --workers 4 --no-plots

# Complex first-order with custom grid
uv run pll-explore --approx cfoa --alpha-f-points 5 --kf-points 4

# Run all four approximation types
uv run pll-explore --approx all --small

# Cross-type comparison (evaluates all 4 types per parameter combo)
uv run pll-explore --approx compare --small

# Serial mode (for debugging)
uv run pll-explore --approx foa --small --serial

# Resume a crashed or interrupted run from its partial CSV
uv run pll-explore --approx foa --resume
```

#### Incremental saving and resume

Results are saved incrementally to a `{approx}_results_raw.csv` file (or `compare_results_raw.csv` for compare mode) every 5,000 evaluations. If the sweep is interrupted (crash, Ctrl-C, OOM), use `--resume` to continue from where it stopped. The tool reads the existing CSV, identifies already-completed parameter combinations, and only evaluates the remaining ones.

#### CLI Options

| Flag | Description |
|------|-------------|
| `--approx {foa,soa,cfoa,csoa,all,compare}` | Approximation type (default: foa). `compare` evaluates all 4 types per combo for cross-comparison. |
| `--workers N` | Number of parallel workers (default: all CPUs) |
| `--serial` | Single-threaded mode |
| `--small` | Small test grid (~36-144 configs) |
| `--no-plots` | Skip matplotlib figure generation |
| `--output-dir DIR` | Output directory (default: exploration_results) |
| `--resume` | Resume a previous run from its partial CSV output |
| `--alpha-f-points N` | Override number of alpha_f grid points |
| `--alpha-v-points N` | Override number of alpha_v grid points |
| `--kf-points N` | Override number of kf grid points |
| `--kv-points N` | Override number of kv grid points |
| `--tau-points N` | Override number of tau grid points |
| `--wc-points N` | Override number of wc grid points |
| `--T-points N` | Override number of T grid points |

### `pll-analyze` — Explore and compare results

After running `pll-explore`, use `pll-analyze` to load the CSV results and find the best configurations.

```bash
# Summary of a result file
uv run pll-analyze exploration_results/foa_results.csv

# Top 20 by composite score
uv run pll-analyze exploration_results/foa_results.csv --top 20

# Sort by a specific metric
uv run pll-analyze exploration_results/foa_results.csv --sort phase_margin

# Filter by parameter ranges
uv run pll-analyze exploration_results/foa_results.csv --filter "alpha_f>=0.3,kf<1000"

# Find Pareto-optimal configs for two metrics
uv run pll-analyze exploration_results/foa_results.csv --pareto phase_margin bandwidth

# Pareto front minimizing noise bandwidth while maximizing bandwidth
uv run pll-analyze exploration_results/foa_results.csv --pareto bandwidth noise_bandwidth

# Best single config per metric
uv run pll-analyze exploration_results/foa_results.csv --best

# Compare across multiple approximation types
uv run pll-analyze exploration_results/foa_results.csv exploration_results/soa_results.csv --compare

# Filter to one approx type from a combined file
uv run pll-analyze exploration_results/compare_results.csv --approx cfoa --top 10

# Export filtered results to a new CSV
uv run pll-analyze exploration_results/foa_results.csv --filter "phase_margin>45" --export best_pm.csv
```

#### CLI Options

| Flag | Description |
|------|-------------|
| `files` (positional) | One or more CSV result files to load |
| `--top N` | Number of top configurations to show (default: 10) |
| `--sort METRIC` | Sort by a specific metric instead of composite score |
| `--filter EXPR` | Comma-separated filters, e.g. `"alpha_f>0.3,kf<100"` |
| `--pareto OBJ1 OBJ2` | Find Pareto-optimal configs for two metrics |
| `--compare` | Side-by-side comparison across approximation types |
| `--best` | Show the single best config for each metric |
| `--stable-only` | Only include stable configurations |
| `--approx TYPE` | Filter to a specific approximation type |
| `--export FILE` | Export filtered results to a new CSV file |

Supported filter operators: `>`, `<`, `>=`, `<=`, `==`, `!=`.

### Output Files

All output goes to `--output-dir` (default: `exploration_results/`):

| File | Description |
|------|-------------|
| `{approx}_results_raw.csv` | Incremental raw results (all configs, used for `--resume`) |
| `{approx}_results.csv` | Stable configurations scored and ranked by composite score |
| `compare_results_raw.csv` | Incremental raw results for compare mode |
| `compare_results.csv` | Scored/ranked stable configs from compare mode |
| `{approx}_fig1_heatmap_af_kf.png` | Stability heatmap: alpha_f vs kf |
| `{approx}_fig2_heatmap_af_av.png` | Stability heatmap: alpha_f vs alpha_v |
| `{approx}_fig3_scatter_regions.png` | Stable vs unstable scatter plots |
| `{approx}_fig4_performance.png` | Performance metric scatter/histogram |
| `{approx}_fig5_3d_stability.png` | 3D stability region |
| `{approx}_fig6_pareto.png` | Pareto front (PM vs BW) |
| `{approx}_fig7_noise_metrics.png` | Noise bandwidth, peak sensitivity, lock time |
| `{approx}_fig8_pareto_bw_bn.png` | Pareto front (BW vs Noise BW) |
| `compare_fig1_stability_rate.png` | Bar chart: stability rate per type |
| `compare_fig2_boxplots.png` | Box plots: metrics by type |
| `compare_fig3_best_type_heatmap.png` | Best type per (alpha_f, alpha_v) pair |
| `compare_fig4_pm_bw_scatter.png` | PM vs BW scatter by type |
| `rules_of_thumb.txt` | Automated statistical findings |

## 7. Results Summary

*This section will be populated after running the full sweeps.*

### FOA (First-Order)

| Metric | Best Value | alpha_f | alpha_v | kf | kv | tau | wc |
|--------|-----------|---------|---------|----|----|-----|-----|
| Phase Margin | — | — | — | — | — | — | — |
| Gain Margin | — | — | — | — | — | — | — |
| Bandwidth | — | — | — | — | — | — | — |
| Robustness | — | — | — | — | — | — | — |

### SOA (Second-Order)

*(To be filled after sweep)*

### CFOA (Complex First-Order)

*(To be filled after sweep)*

### CSOA (Complex Second-Order)

*(To be filled after sweep)*

## 8. Rules of Thumb

*Generated automatically by `analyze_rules_of_thumb()`. Run the exploration to populate.*

## 9. Figures

### Per-type figures (`{approx}_fig*.png`)

1. **Stability Heatmap (alpha_f vs kf):** Shows the probability of stability for each (alpha_f, kf) combination, averaged over all other parameters. Reveals which filter orders and gains are most likely to produce stable PLLs.

2. **Stability Heatmap (alpha_f vs alpha_v):** Shows how the interaction between filter and VCO fractional orders affects stability. Diagonal patterns indicate coupled stability constraints.

3. **Scatter: Stable vs Unstable Regions:** Three projections showing where stable (green) and unstable (red) configurations cluster in the parameter space: (alpha_f, kf), (alpha_f, alpha_v), and (tau, wc).

4. **Performance Metrics:** Four subplots for stable configurations:
   - Phase margin vs alpha_f (colored by kf)
   - Bandwidth vs alpha_v (colored by log(wc))
   - PM vs BW trade-off (colored by alpha_f)
   - Histogram of max pole magnitudes

5. **3D Stability Region:** Stable configurations plotted in (alpha_f, alpha_v, log(tau)) space, colored by phase margin. Reveals the shape of the stable region.

6. **Pareto Front (PM vs BW):** All stable configurations in the phase margin vs bandwidth plane, with Pareto-optimal points (red circles) highlighted. These represent the best achievable trade-offs.

7. **Noise Metrics:** Four subplots:
   - Noise bandwidth vs alpha_f (colored by tau)
   - Peak sensitivity vs alpha_f (colored by phase margin, with Ms=2.0 reference line)
   - Lock time vs bandwidth (colored by alpha_f)
   - Noise efficiency ratio histogram (Bn/BW, with pi/2 reference for 2nd-order optimal)

8. **Pareto Front (BW vs Noise BW):** Bandwidth vs noise bandwidth trade-off, with Pareto-optimal points highlighted. Maximizes bandwidth while minimizing noise passed through.

### Compare-mode figures (`compare_fig*.png`)

1. **Stability Rate:** Bar chart showing the percentage of stable configurations for each approximation type.

2. **Box Plots:** Side-by-side box plots for all metrics (PM, BW, GM, pole mag, noise BW, Ms, lock time) broken down by approximation type.

3. **Best Type Heatmap:** For each (alpha_f, alpha_v) pair, shows which approximation type achieves the highest phase margin.

4. **PM vs BW Scatter:** Phase margin vs bandwidth scatter plot colored by approximation type, showing how each type trades off between these two key metrics.
