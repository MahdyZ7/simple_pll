# Vivado TCL Script: Quick Non-Project Build
# Run from: build/vivado directory
# This is a non-project flow for quick builds

set part_name "xc7a35tcpg236-1"
set top_module "basys3_pll_top"
set src_dir "../../"
set fpga_dir "../../fpga"

# Read source files
read_verilog -sv [list \
    "${src_dir}/pll_foa.sv" \
    "${fpga_dir}/clk_divider.sv" \
    "${fpga_dir}/debounce.sv" \
    "${fpga_dir}/square_wave_gen.sv" \
    "${fpga_dir}/seven_seg_controller.sv" \
    "${fpga_dir}/led_status.sv" \
    "${fpga_dir}/basys3_pll_top.sv" \
]

# Read constraints
read_xdc "${fpga_dir}/constraints/basys3_pll.xdc"

# Synthesize
synth_design -top $top_module -part $part_name

# Report post-synthesis
report_utilization -file quick_synth_util.rpt
report_timing_summary -file quick_synth_timing.rpt

# Optimize
opt_design

# Place
place_design

# Report post-place
report_utilization -file quick_place_util.rpt

# Route
route_design

# Report post-route
report_utilization -file quick_route_util.rpt
report_timing_summary -file quick_route_timing.rpt
report_power -file quick_power.rpt

# Check timing
if {[get_property SLACK [get_timing_paths]] < 0} {
    puts "WARNING: Timing constraints not met!"
}

# Generate bitstream
write_bitstream -force ${top_module}.bit

puts "Quick build completed!"
puts "Bitstream: ${top_module}.bit"
