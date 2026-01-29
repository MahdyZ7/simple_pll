# Basys 3 FPGA Test Wrapper for PLL IIR Filter

This directory contains an FPGA wrapper to test the `pll_foa` IIR filter on a Digilent Basys 3 board (Xilinx Artix-7 XC7A35T).

## Overview

The wrapper provides:
- Internal square wave generator with configurable frequency (1Hz-1kHz) and amplitude
- Switch-controlled parameters for real-time testing
- 4-digit seven-segment hex display showing filter input/output
- LED status indicators

## Module Hierarchy

```
basys3_pll_top.sv          (Top-level wrapper)
├── clk_divider.sv         (Clock dividers for display & test pattern)
├── debounce.sv            (Button debouncer)
├── square_wave_gen.sv     (Configurable test pattern generator)
├── pll_foa.sv             (IIR Filter DUT - in parent directory)
├── seven_seg_controller.sv (4-digit multiplexed display driver)
└── led_status.sv          (LED status mapping)
```

## Switch Assignments (SW[15:0])

| Switch | Function | Description |
|--------|----------|-------------|
| SW[0] | Enable | Filter enable (gates valid_in) |
| SW[3:1] | Freq Select | 000=1Hz, 001=2Hz, 010=5Hz, 011=10Hz, 100=50Hz, 101=100Hz, 110=500Hz, 111=1kHz |
| SW[7:4] | Amplitude | 16 levels: 1, 2, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 25000, 50000, 100000 |
| SW[8] | Input Source | 0=Internal square wave, 1=Reserved |
| SW[11:9] | Display Slice | Selects which 16-bit portion of 64-bit value to display |
| SW[12] | Display Mode | 0=Output (y_out), 1=Input (x_in) |
| SW[15:13] | Reserved | Future use |

## LED Assignments (LED[15:0])

| LED | Function |
|-----|----------|
| LED[0] | Filter enabled |
| LED[1] | valid_in active |
| LED[2] | valid_out active |
| LED[3] | Output sign (1=negative) |
| LED[7:4] | Amplitude selection indicator |
| LED[10:8] | Frequency selection indicator |
| LED[11] | Square wave state (high/low) |
| LED[15:12] | Overflow indicator |

## Button Assignments

| Button | Function |
|--------|----------|
| BTNC | System reset (active-high, debounced) |

## Display Slice Selection (SW[11:9])

The 64-bit Q16 fixed-point values are displayed 16 bits at a time:

| Value | Bits Displayed | Content |
|-------|----------------|---------|
| 000 | [15:0] | Fractional LSB |
| 001 | [31:16] | Fractional MSB |
| 010 | [47:32] | Integer LSB |
| 011 | [63:48] | Integer MSB / Sign |

## Build Instructions

### Simulation (Icarus Verilog)

```bash
cd rtl
make fpga_icarus
```

### Vivado Project Flow

```bash
cd rtl

# Create Vivado project
make vivado_project

# Open GUI (optional)
make vivado_gui

# Run synthesis
make vivado_synth

# Run implementation and generate bitstream
make vivado_impl

# Program FPGA
make vivado_program
```

### Vivado Quick Build (Non-Project)

```bash
cd rtl
make vivado_quick
```

## Hardware Testing

1. Program the Basys 3 with the generated bitstream
2. Set SW[0]=1 to enable the filter
3. Set SW[3:1]=000 for 1Hz (visible LED[11] toggling)
4. Set SW[7:4]=0100 for amplitude=25
5. Observe the 7-segment display showing filter output
6. Use SW[11:9] to view different portions of the 64-bit output
7. Toggle SW[12] to switch between viewing input and output

## File Structure

```
fpga/
├── basys3_pll_top.sv           # Top-level wrapper
├── clk_divider.sv              # Clock divider
├── debounce.sv                 # Button debouncer
├── square_wave_gen.sv          # Test pattern generator
├── seven_seg_controller.sv     # 7-segment display driver
├── led_status.sv               # LED status mapper
├── README.md                   # This file
├── constraints/
│   └── basys3_pll.xdc          # Basys 3 pin constraints
├── scripts/
│   ├── create_project.tcl      # Create Vivado project
│   ├── run_synth.tcl           # Run synthesis
│   ├── run_impl.tcl            # Run implementation
│   ├── quick_build.tcl         # Non-project build
│   └── program.tcl             # Program FPGA
└── tb/
    └── tb_basys3_pll_top.sv    # Simulation testbench
```

## Signal Flow

```
SW[3:1] ──> clk_divider ──> tick_test
                               │
SW[7:4] ──> square_wave_gen <──┘
                │
                v
SW[0] ───> valid_in gate
                │
                v
           ┌─────────┐
x_in ────> │ pll_foa │ ────> y_out ──> display_mux ──> seven_seg_controller
           └─────────┘                (SW[11:9])
                ^
                │
BTNC ──> debounce ──> rst_n
```
