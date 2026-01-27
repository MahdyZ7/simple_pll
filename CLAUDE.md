# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PLL (Phase-Locked Loop) filter implementation with both C++ fixed-point modeling and SystemVerilog RTL. The C++ code generates and validates fixed-point coefficients, while the RTL implements IIR filters for hardware.

## Build Commands

### C++ Fixed-Point Model (`cpp/`)
```bash
make -C cpp          # Build the fixed-point coefficient generator
make -C cpp clean    # Remove object files
make -C cpp fclean   # Remove all build artifacts
make -C cpp re       # Clean rebuild
./cpp/main           # Run coefficient generator
```

### RTL Simulation (`rtl/`)

**Icarus Verilog (open source):**
```bash
make -C rtl icarus   # Compile and run with GTKWave
```

**Questa/ModelSim:**
```bash
make -C rtl          # Compile and simulate with GUI
make -C rtl cli      # Command-line simulation only
make -C rtl compile  # Compile only (syntax check)
```

**Waveform viewing:**
```bash
make -C rtl wave     # View previous simulation waveforms
```

## Architecture

### C++ Component
- `Fixed.hpp`: Template class for arbitrary-precision fixed-point arithmetic with configurable fractional bits
- `main.cpp`: Generates fixed-point IIR filter coefficients for the RTL. Uses `print_cofficients()` to output SystemVerilog-ready `localparam` declarations

### RTL Component
- `pll_foa.sv`: Single-cycle IIR filter using Q24 fixed-point (24 fractional bits)
- `pll_foa_cl.sv`: Contains two variants:
  - `iir_time_diff_filter`: 3-stage pipelined implementation
  - `iir_time_diff_filter_single_cycle`: Combinational implementation for lower latency
- `tb_pll_foa.sv`: Testbench with alternating input (25/50) to exercise the filter

### Coefficient Workflow
The C++ model converts floating-point IIR coefficients to fixed-point format. Run the C++ program to regenerate coefficients when filter parameters change, then copy the output to the RTL modules.

Filter equation: `y[n] = c0*x[n] + c1*x[n-1] + c2*x[n-2] + c3*x[n-3] + cy1*y[n-1] + cy2*y[n-2] + cy3*y[n-3]`
