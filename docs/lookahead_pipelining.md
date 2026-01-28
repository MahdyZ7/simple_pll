# Look-Ahead Pipelining for IIR Filters

## The Problem: Feedback Limits Clock Speed

In a standard IIR filter, the output `y[n]` depends on the previous output `y[n-1]`:

```
y[n] = c0·x[n] + c1·x[n-1] + ... + cy1·y[n-1] + cy2·y[n-2] + ...
                                        ↑
                              Must wait for this!
```

This creates a **feedback dependency** that limits clock speed.

### Why This Matters: The Critical Path

```
    ┌─────────────────── CRITICAL PATH (one clock cycle) ──────────────────┐
    │                                                                       │
    │                                                                       ▼
┌───┴───┐      ┌──────────┐      ┌──────────┐      ┌──────────┐      ┌─────────┐
│       │      │          │      │          │      │          │      │         │
│ y[n-1]├─────►│ MULTIPLY ├─────►│   ADD    ├─────►│ REGISTER ├─────►│  y[n]   │
│       │      │  (cy1)   │      │ (7 terms)│      │          │      │         │
└───────┘      └──────────┘      └──────────┘      └──────────┘      └────┬────┘
    ▲                                                                      │
    │                                                                      │
    └──────────────────────── FEEDBACK ────────────────────────────────────┘
                          (must complete in ONE cycle)
```

**The Problem**: You cannot insert a pipeline register in the feedback loop because `y[n]` requires `y[n-1]` to be computed first. The entire computation must finish in one clock cycle.

### Timing Breakdown

```
Component          │ Typical Delay
───────────────────┼──────────────
DSP Multiply       │ 3-4 ns
7-input Adder Tree │ 2-3 ns
Routing            │ 1-2 ns
Register Setup     │ 0.5 ns
───────────────────┼──────────────
TOTAL              │ 6.5-9.5 ns  →  Max ~150 MHz
```

At 1 GHz (1 ns cycle time), this path **cannot close timing**.

---

## The Solution: Look-Ahead Transformation

Look-ahead pipelining mathematically transforms the filter to depend on **older** outputs (y[n-2] instead of y[n-1]), creating slack for pipeline registers.

### Conceptual Overview

```
BEFORE: Tight feedback loop (no room for pipeline)
═══════════════════════════════════════════════════

     x[n] ───────────────────────────────────►┌─────┐
                                              │     │
     y[n-1] ──────► COMPUTE ─────────────────►│ ADD ├───► y[n]
         ▲                                    │     │       │
         │                                    └─────┘       │
         │                                                  │
         └────────────────── z⁻¹ ◄──────────────────────────┘
                          (1 cycle)


AFTER: Relaxed feedback loop (room for 2 pipeline stages)
═════════════════════════════════════════════════════════

     x[n] ───────────────────────────────────►┌─────┐
                                              │     │
     y[n-2] ──────► COMPUTE ─────────────────►│ ADD ├───► y[n]
         ▲                                    │     │       │
         │                                    └─────┘       │
         │                                                  │
         └─────── z⁻¹ ◄────── z⁻¹ ◄─────────────────────────┘
                (cycle 1)   (cycle 2)

                    ▲
                    │
          2 cycles available for feedback path!
```

---

## Mathematical Derivation

### Original Transfer Function

```
              N(z)         c0 + c1·z⁻¹ + c2·z⁻² + c3·z⁻³
    H(z) = ──────── = ─────────────────────────────────────
              D(z)      1 - cy1·z⁻¹ - cy2·z⁻² - cy3·z⁻³
```

### The Transformation Trick

Multiply top and bottom by `(1 + d₁·z⁻¹)` where `d₁ = cy1`:

```
              N(z) · (1 + cy1·z⁻¹)
    H(z) = ─────────────────────────
              D(z) · (1 + cy1·z⁻¹)
```

### Why This Works

The denominator expansion:

```
    D(z) · (1 + cy1·z⁻¹)

    = (1 - cy1·z⁻¹ - cy2·z⁻² - cy3·z⁻³) · (1 + cy1·z⁻¹)

    = 1 + cy1·z⁻¹                          ← from multiplying by 1
        - cy1·z⁻¹ - cy1²·z⁻²               ← from -cy1·z⁻¹ term
        - cy2·z⁻² - cy2·cy1·z⁻³            ← from -cy2·z⁻² term
        - cy3·z⁻³ - cy3·cy1·z⁻⁴            ← from -cy3·z⁻³ term

    Collecting terms:

    = 1 + (cy1 - cy1)·z⁻¹ + (-cy1² - cy2)·z⁻² + (-cy2·cy1 - cy3)·z⁻³ + (-cy3·cy1)·z⁻⁴
          └──────┬──────┘
                 │
                 ▼
           EQUALS ZERO!

    = 1 + 0·z⁻¹ + cy2'·z⁻² + cy3'·z⁻³ + cy4'·z⁻⁴
          │
          └──► No y[n-1] dependency!
```

---

## Transformed Coefficients

### Coefficient Formulas (M=1 Look-Ahead)

```
┌──────────────────────────────────────────────────────────────────┐
│                     FEEDFORWARD COEFFICIENTS                      │
├──────────────┬────────────────────────┬─────────────────────────┤
│   Original   │        Formula         │       Transformed       │
├──────────────┼────────────────────────┼─────────────────────────┤
│     c0       │          c0            │          c0'            │
│     c1       │     c1 + c0·cy1        │          c1'            │
│     c2       │     c2 + c1·cy1        │          c2'            │
│     c3       │     c3 + c2·cy1        │          c3'            │
│     —        │       c3·cy1           │     c4' (NEW TAP)       │
└──────────────┴────────────────────────┴─────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                      FEEDBACK COEFFICIENTS                        │
├──────────────┬────────────────────────┬─────────────────────────┤
│   Original   │        Formula         │       Transformed       │
├──────────────┼────────────────────────┼─────────────────────────┤
│    cy1       │           0            │   CANCELLED (= 0)       │
│    cy2       │     cy2 + cy1²         │         cy2'            │
│    cy3       │    cy3 + cy2·cy1       │         cy3'            │
│     —        │      cy3·cy1           │    cy4' (NEW TAP)       │
└──────────────┴────────────────────────┴─────────────────────────┘
```

### Numerical Example (Our Filter)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           ORIGINAL COEFFICIENTS                          │
├─────────────────────────────────┬───────────────────────────────────────┤
│          Feedforward            │              Feedback                  │
├─────────────────────────────────┼───────────────────────────────────────┤
│  c0  =  +0.0742                 │  cy1 =  +2.7448                       │
│  c1  =  -0.0614                 │  cy2 =  -2.5169                       │
│  c2  =  -0.0737                 │  cy3 =  +0.7710                       │
│  c3  =  +0.0620                 │                                       │
└─────────────────────────────────┴───────────────────────────────────────┘
                                    │
                                    │  Apply M=1 Transformation
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         TRANSFORMED COEFFICIENTS                         │
├─────────────────────────────────┬───────────────────────────────────────┤
│          Feedforward            │              Feedback                  │
├─────────────────────────────────┼───────────────────────────────────────┤
│  c0' =  +0.0742                 │  cy1' =   0      ← CANCELLED!         │
│  c1' =  +0.1423                 │  cy2' =  +4.9168                      │
│  c2' =  -0.2422                 │  cy3' =  -6.1368                      │
│  c3' =  -0.1403                 │  cy4' =  +2.1162 ← NEW                │
│  c4' =  +0.1702  ← NEW          │                                       │
└─────────────────────────────────┴───────────────────────────────────────┘
```

---

## Pipeline Architecture

### Original Architecture (Direct Form 1)

```
                            SINGLE CLOCK CYCLE
    ◄───────────────────────────────────────────────────────────────────────►

    x[n] ────┬────────────────────────────────────────────────────┐
             │                                                     │
             ▼                                                     │
         ┌───────┐                                                 │
         │ × c0  │                                                 │
         └───┬───┘                                                 │
             │                                                     │
             ▼                                                     │
    x[n-1]──►(+)◄──┐                                               │
             │     │                                               │
             │ ┌───┴───┐                                           │
             │ │ × c1  │◄── x[n-1]                                 │
             │ └───────┘                                           │
             ▼                                                     │
            (+)◄──┐                                                │
             │    │                                                │
             │┌───┴───┐                                            │
             ││ × c2  │◄── x[n-2]                                  │
             │└───────┘                                            │
             ▼                                                     │
            (+)◄──┐                                                │
             │    │                                                │
             │┌───┴───┐                                            │
             ││ × c3  │◄── x[n-3]           ┌───────────────────┐  │
             │└───────┘                     │    FEEDBACK       │  │
             ▼                              │    (same cycle!)  │  │
            (+)◄───────────────────────────────────────────────────┤
             │                              │                   │  │
             │         ┌───────┐            │  ┌───────┐        │  │
             │         │ ×cy1  │◄───────────┼──┤y[n-1] │◄───┐   │  │
             │         └───┬───┘            │  └───────┘    │   │  │
             │             │                │               │   │  │
             ▼             ▼                │  ┌───────┐    │   │  │
            (+)◄──────────(+)◄──────────────┼──┤ ×cy2  │◄───┼───┤  │
             │                              │  └───────┘    │   │  │
             │                              │      ▲        │   │  │
             │                              │  y[n-2]       │   │  │
             │                              │               │   │  │
             │                              │  ┌───────┐    │   │  │
             │                              └──┤ ×cy3  │◄───┼───┘  │
             │                                 └───┬───┘    │      │
             │                                     ▲        │      │
             ▼                                  y[n-3]      │      │
         ┌───────┐                                          │      │
         │  REG  │──────────────────────────────────────────┘      │
         └───┬───┘                                                 │
             │                                                     │
             ▼                                                     │
           y[n] ◄──────────────────────────────────────────────────┘

    PROBLEM: Everything must complete in ONE cycle!
```

### Look-Ahead Architecture (M=1, 3-Stage Pipeline)

```
    ════════════════════════════════════════════════════════════════════════
                              STAGE 1 (Clock Cycle 1)
    ════════════════════════════════════════════════════════════════════════

        x[n] ──────►┌───────┐
                    │ × c0' ├──────┐
                    └───────┘      │
                                   ▼
        x[n-1] ────►┌───────┐    ┌───┐    ┌─────┐
                    │ × c1' ├───►│ + ├───►│ REG │═══╗
                    └───────┘    └───┘    └─────┘   ║
                                   ▲                ║
        x[n-2] ────►┌───────┐      │                ║
                    │ × c2' ├──────┘                ║
                    └───────┘                       ║
                                                    ║
    ════════════════════════════════════════════════╬═══════════════════════
                              STAGE 2 (Clock Cycle 2)
    ════════════════════════════════════════════════╬═══════════════════════
                                                    ║
                    ╔═══════════════════════════════╝
                    ║
                    ▼
        x[n-3] ────►┌───────┐    ┌───┐
                    │ × c3' ├───►│   │
                    └───────┘    │   │    ┌─────┐
                                 │ + ├───►│ REG │═══╗
        x[n-4] ────►┌───────┐    │   │    └─────┘   ║
                    │ × c4' ├───►│   │              ║
                    └───────┘    └───┘              ║
                                   ▲                ║
                                   │                ║
        ┌──────────────────────────┘                ║
        │   FEEDBACK COMPUTATION                    ║
        │   (2 cycles available!)                   ║
        │                                           ║
        │   y[n-2] ────►┌────────┐                  ║
        │               │ × cy2' ├──┐               ║
        │               └────────┘  │               ║
        │                           ▼               ║
        │   y[n-3] ────►┌────────┐ (+)              ║
        │               │ × cy3' ├──┤               ║
        │               └────────┘  │               ║
        │                           ▼               ║
        │   y[n-4] ────►┌────────┐ (+)──────────────┤
        │               │ × cy4' ├──┘               │
        │               └────────┘                  │
        │                                           │
        └───────────────────────────────────────────┘
                                                    ║
    ════════════════════════════════════════════════╬═══════════════════════
                              STAGE 3 (Clock Cycle 3)
    ════════════════════════════════════════════════╬═══════════════════════
                                                    ║
                    ╔═══════════════════════════════╝
                    ║
                    ▼
                  ┌───┐    ┌─────────┐
                  │ + ├───►│ >>> 16  ├───►  y[n]
                  └───┘    └─────────┘
                    ▲           │
                    │           │
        (feedback)──┘           │
                                │
                                ▼
                           ┌─────────┐
                           │  y_out  │──────► Output
                           └────┬────┘
                                │
                                │  Feedback path has
                                │  2 full cycles!
                                ▼
                           ┌─────────┐
                           │  z⁻¹    │──► y[n-1] (not used)
                           └────┬────┘
                                │
                                ▼
                           ┌─────────┐
                           │  z⁻¹    │──► y[n-2] ──► feeds Stage 2
                           └────┬────┘
                                │
                                ▼
                           ┌─────────┐
                           │  z⁻¹    │──► y[n-3] ──► feeds Stage 2
                           └─────────┘
```

### Timing Comparison

```
    ┌────────────────────────────────────────────────────────────────────────┐
    │                        ORIGINAL (No Pipeline)                          │
    ├────────────────────────────────────────────────────────────────────────┤
    │                                                                        │
    │    │◄────────────────── 1 cycle (~7 ns) ──────────────────►│          │
    │    │                                                        │          │
    │    ├──[MUL]──[MUL]──[MUL]──[ADD]──[ADD]──[MUL]──[ADD]──[REG]┤          │
    │    │        ALL IN ONE CYCLE = ~150 MHz max                 │          │
    │                                                                        │
    └────────────────────────────────────────────────────────────────────────┘

    ┌────────────────────────────────────────────────────────────────────────┐
    │                      LOOK-AHEAD (3-Stage Pipeline)                     │
    ├────────────────────────────────────────────────────────────────────────┤
    │                                                                        │
    │    │◄─ cycle 1 ─►│◄─ cycle 2 ─►│◄─ cycle 3 ─►│                        │
    │    │             │             │             │                        │
    │    ├──[MUL][ADD]─┼──[MUL][ADD]─┼────[ADD]────┤                        │
    │    │   ~2 ns     │    ~2 ns    │    ~1 ns    │                        │
    │    │             │             │             │                        │
    │         EACH STAGE = ~2 ns = ~500 MHz per stage                       │
    │                                                                        │
    │    Latency: 3 cycles                                                   │
    │    Throughput: 1 sample/cycle (same as original)                       │
    │                                                                        │
    └────────────────────────────────────────────────────────────────────────┘
```

---

## Trade-offs Summary

```
    ┌──────────────────┬───────────────┬───────────────┬───────────────┐
    │      Metric      │   Original    │  M=1 Lookahead│  M=2 Lookahead│
    ├──────────────────┼───────────────┼───────────────┼───────────────┤
    │  Max Clock       │   ~150 MHz    │   ~500 MHz    │   ~800 MHz    │
    │  Latency         │   1 cycle     │   3 cycles    │   5 cycles    │
    │  Throughput      │   1 samp/cyc  │   1 samp/cyc  │   1 samp/cyc  │
    │  Multipliers     │   7           │   9           │   11          │
    │  Adders          │   6           │   8           │   10          │
    │  Registers       │   6           │   ~14         │   ~22         │
    │  FF Taps (x)     │   4           │   5           │   6           │
    │  FB Taps (y)     │   3           │   3           │   3           │
    └──────────────────┴───────────────┴───────────────┴───────────────┘

    ┌─────────────────────────────────────────────────────────────────┐
    │                     WHEN TO USE EACH                            │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                 │
    │   ORIGINAL        Use when: Clock < 150 MHz                     │
    │   ════════              Pro: Minimum resources                  │
    │                         Con: Cannot be pipelined                │
    │                                                                 │
    │   M=1 LOOK-AHEAD  Use when: 150 MHz < Clock < 500 MHz           │
    │   ══════════════       Pro: Good speed/resource balance         │
    │                        Con: 3-cycle latency                     │
    │                                                                 │
    │   M=2 LOOK-AHEAD  Use when: 500 MHz < Clock < 800 MHz           │
    │   ══════════════       Pro: Highest clock speed                 │
    │                        Con: Most resources, 5-cycle latency     │
    │                                                                 │
    └─────────────────────────────────────────────────────────────────┘
```

---

## Implementation Notes

### Coefficient Precision Warning

```
    ┌─────────────────────────────────────────────────────────────────┐
    │  ⚠  TRANSFORMED COEFFICIENTS CAN BE MUCH LARGER!               │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                 │
    │     Original cy2 = -2.5169                                      │
    │                       │                                         │
    │                       ▼                                         │
    │     Transformed cy2' = +4.9168   (almost 2x magnitude!)         │
    │                                                                 │
    │     Original cy3 = +0.7710                                      │
    │                       │                                         │
    │                       ▼                                         │
    │     Transformed cy3' = -6.1368   (8x magnitude!)                │
    │                                                                 │
    │  SOLUTION: Increase COEFF_WIDTH or use wider accumulators       │
    │                                                                 │
    └─────────────────────────────────────────────────────────────────┘
```

### Verification Strategy

```
    ┌─────────────────────────────────────────────────────────────────┐
    │                    TESTBENCH VERIFICATION                       │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                 │
    │      ┌──────────────┐         ┌──────────────────┐             │
    │      │   ORIGINAL   │         │    LOOK-AHEAD    │             │
    │      │    FILTER    │         │      FILTER      │             │
    │      └──────┬───────┘         └────────┬─────────┘             │
    │             │                          │                        │
    │    x[n] ───►├──────────────────────────┤                        │
    │             │                          │                        │
    │             ▼                          ▼                        │
    │         y_original              y_lookahead                     │
    │             │                          │                        │
    │             │    ┌──────────────┐      │                        │
    │             └───►│   COMPARE    │◄─────┘                        │
    │                  │  (account    │                               │
    │                  │   for 2-cyc  │                               │
    │                  │   latency)   │                               │
    │                  └──────┬───────┘                               │
    │                         │                                       │
    │                         ▼                                       │
    │                  Should match within                            │
    │                  quantization error!                            │
    │                                                                 │
    └─────────────────────────────────────────────────────────────────┘
```

---

## Alternative High-Speed Approaches

```
    ┌─────────────────────────────────────────────────────────────────┐
    │              OTHER OPTIONS FOR HIGH-SPEED IIR                   │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                 │
    │  1. PARALLEL/BLOCK PROCESSING                                   │
    │     ─────────────────────────                                   │
    │     Process N samples simultaneously                            │
    │     Throughput: N samples/cycle                                 │
    │     Cost: N× hardware                                           │
    │                                                                 │
    │  2. POLYPHASE DECOMPOSITION                                     │
    │     ────────────────────────                                    │
    │     Split into M parallel slower filters                        │
    │     Each runs at Fclk/M                                         │
    │     Effective rate: Fclk                                        │
    │                                                                 │
    │  3. INCREMENTAL/DELTA-SIGMA                                     │
    │     ───────────────────────                                     │
    │     Use 1-bit inputs with oversampling                          │
    │     Simpler arithmetic                                          │
    │     Requires different filter design                            │
    │                                                                 │
    │  4. APPROXIMATE COMPUTING                                       │
    │     ──────────────────────                                      │
    │     Accept small errors for speed                               │
    │     Truncate intermediate results                               │
    │     Use shorter multipliers                                     │
    │                                                                 │
    └─────────────────────────────────────────────────────────────────┘
```

---

## References

1. K. K. Parhi, "VLSI Digital Signal Processing Systems", Wiley, 1999
2. K. K. Parhi, "Pipelining in IIR Digital Filters", IEEE Trans. ASSP, 1988
3. M. Potkonjak, J. Rabaey, "Retiming for Scheduling", IEEE Trans. VLSI, 1994

---

## File Locations

| File | Description |
|------|-------------|
| `rtl/pll_foa.sv` | Original (non-pipelined) filter |
| `rtl/pll_foa_lookahead.sv` | Look-ahead pipelined implementation |
| `rtl/tb_pll_foa.sv` | Testbench |
