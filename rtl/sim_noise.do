# sim.do - Questa Sim simulation script for pll_foa
# quit previous simulation if any
quit -sim
# Create and map library
vlib TB_PLL_FOA
vmap TB_PLL_FOA TB_PLL_FOA

# Compile all SystemVerilog files
vlog -sv -work TB_PLL_FOA +acc pll_foa.sv pll_foa_df2.sv pll_foa_2.sv pll_soa.sv pll_cfoa.sv pll_csoa.sv tb_pll_foa_stdNoise.sv

# Load simulation with full visibility
vsim -voptargs=+acc -L TB_PLL_FOA TB_PLL_FOA.tb_pll_foa_stdNoise

# Log all signals recursively
log -r /*

# Add top-level testbench signals
add wave -divider "Control Signals"
add wave /tb_pll_foa_stdNoise/clk
add wave /tb_pll_foa_stdNoise/rst_n
add wave /tb_pll_foa_stdNoise/valid_in
add wave /tb_pll_foa_stdNoise/valid_out_foa
# Add input/output as analog
add wave -divider "Input/Output (Analog)"
add wave -format analog-step -height 80 -radix signed /tb_pll_foa_stdNoise/x_in
add wave -format analog-step -height 80 -radix signed /tb_pll_foa_stdNoise/y_out_foa
add wave -format analog-step -height 80 -radix signed /tb_pll_foa_stdNoise/y_out_df2
add wave -format analog-step -height 80 -radix signed /tb_pll_foa_stdNoise/y_out_foa2
add wave -format analog-step -height 80 -radix signed /tb_pll_foa_stdNoise/y_out_soa
add wave -format analog-step -height 80 -radix signed /tb_pll_foa_stdNoise/y_out_cfoa
add wave -format analog-step -height 80 -radix signed /tb_pll_foa_stdNoise/y_out_csoa
# Add jitter difference signal
add wave -divider "Jitter Difference"
add wave /tb_pll_foa_stdNoise/toggle
add wave /tb_pll_foa_stdNoise/toggle_jitter
add wave -format analog-step -height 3 -radix signed /tb_pll_foa_stdNoise/jitter_diff
# Add internal DUT signals
# add wave -divider "DUT Internals"
# add wave -format analog-step -height 60 -radix signed /tb_pll_foa/dut/temp_sum

# # Add x_delay array as analog
# add wave -divider "X Delay Line (Analog)"
# add wave -format analog-step -height 50 -radix signed /tb_pll_foa/dut/x_delay(0)
# add wave -format analog-step -height 50 -radix signed /tb_pll_foa/dut/x_delay(1)
# add wave -format analog-step -height 50 -radix signed /tb_pll_foa/dut/x_delay(2)

# # Add y_delay array as analog
# add wave -divider "Y Delay Line - Feedback (Analog)"
# add wave -format analog-step -height 50 -radix signed /tb_pll_foa/dut/y_delay(0)
# add wave -format analog-step -height 50 -radix signed /tb_pll_foa/dut/y_delay(1)
# add wave -format analog-step -height 50 -radix signed /tb_pll_foa/dut/y_delay(2)

# Run simulation
run -all

# Zoom to fit all waveforms
wave zoom full

