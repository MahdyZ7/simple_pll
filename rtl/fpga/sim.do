# sim.do - Questa Sim simulation script for pll_foa

# Create and map library
vlib TB_BASYS3_PLL
vmap TB_BASYS3_PLL TB_BASYS3_PLL

# Compile all SystemVerilog files
vlog -sv -work TB_BASYS3_PLL +acc fpga/*.sv fpga/tb/tb_basys3_pll_top.sv

# Load simulation with full visibility
vsim -voptargs=+acc -L TB_BASYS3_PLL TB_BASYS3_PLL.tb_basys3_pll_top

# Log all signals recursively
log -r /*

# Add top-level testbench signals
add wave -divider "Control Signals"
add wave /tb_basys3_pll_top/clk
add wave /tb_basys3_pll_top/btnC
add wave /tb_basys3_pll_top/led
# add wave /tb_basys3_pll_top/led[1]

# Add input/output as analog
add wave -divider "Input/Output (Analog)"
add wave -format analog-step -height 80 -radix signed /tb_basys3_pll_top/dut/x_in
add wave -format analog-step -height 80 -radix signed /tb_basys3_pll_top/dut/y_out

# # Add internal DUT signals
# add wave -divider "DUT Internals"
# add wave -format analog-step -height 60 -radix signed /tb_basys3_pll_top/dut/temp_sum

# # Add x_delay array as analog
# add wave -divider "X Delay Line (Analog)"
# add wave -format analog-step -height 50 -radix signed /tb_basys3_pll_top/dut/x_delay(0)
# add wave -format analog-step -height 50 -radix signed /tb_basys3_pll_top/dut/x_delay(1)
# add wave -format analog-step -height 50 -radix signed /tb_basys3_pll_top/dut/x_delay(2)

# # Add y_delay array as analog
# add wave -divider "Y Delay Line - Feedback (Analog)"
# add wave -format analog-step -height 50 -radix signed /tb_basys3_pll_top/dut/y_delay(0)
# add wave -format analog-step -height 50 -radix signed /tb_basys3_pll_top/dut/y_delay(1)
# add wave -format analog-step -height 50 -radix signed /tb_basys3_pll_top/dut/y_delay(2)

# Run simulation
run -all

# Zoom to fit all waveforms
wave zoom full
