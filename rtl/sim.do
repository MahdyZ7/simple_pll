# sim.do - Questa Sim simulation script for pll_foa
# quit previous simulation if any
quit -sim
# Create and map library
vlib TB_PLL_FOA
vmap TB_PLL_FOA TB_PLL_FOA

# Compile all SystemVerilog files
vlog -sv -work TB_PLL_FOA +acc +incdir+../generated/rtl pll_foa.sv pll_foa_2.sv pll_foa_df2.sv pll_foa_df2T.sv \
	pll_cfoa.sv pll_csoa.sv pll_soa.sv fpga/clk_divider.sv tb_pll_foa.sv \
	./NoIntegrator/pll_foa_ni.sv ./NoIntegrator/pll_cfoa_ni.sv ./NoIntegrator/pll_csoa_ni.sv \
	./NoIntegrator/pll_soa_ni.sv


# Load simulation with full visibility
vsim -voptargs=+acc -L TB_PLL_FOA TB_PLL_FOA.tb_pll_foa

# Log all signals recursively
log -r /*

# Add top-level testbench signals
add wave -divider "Control Signals"
add wave /tb_pll_foa/clk
add wave /tb_pll_foa/clock_slow
add wave /tb_pll_foa/clock_slow_jittered
add wave /tb_pll_foa/rst_n
add wave /tb_pll_foa/valid_in
add wave /tb_pll_foa/valid_out_foa

# Add input/output as analog
add wave -divider "Input/Output (Analog)"
add wave -format analog-step -height 80 -radix signed /tb_pll_foa/x_in
add wave -format analog-step -height 80 -radix signed /tb_pll_foa/y_out_foa
add wave -format analog-step -height 80 -radix signed /tb_pll_foa/y_out_df2
add wave -format analog-step -height 80 -radix signed /tb_pll_foa/y_out_df2T
add wave -format analog-step -height 80 -radix signed /tb_pll_foa/y_out_foa2
add wave -format analog-step -height 80 -radix signed /tb_pll_foa/y_out_soa
add wave -format analog-step -height 80 -radix signed /tb_pll_foa/y_out_cfoa
add wave -format analog-step -height 80 -radix signed /tb_pll_foa/y_out_csoa
add wave -divider "NO Integrator (Analog)"
add wave -format analog-step -height 80 -radix signed /tb_pll_foa/y_out_foa_ni
add wave -format analog-step -height 80 -radix signed /tb_pll_foa/y_out_soa_ni
add wave -format analog-step -height 80 -radix signed /tb_pll_foa/y_out_cfoa_ni
add wave -format analog-step -height 80 -radix signed /tb_pll_foa/y_out_csoa_ni

# # Add internal DUT signals
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
