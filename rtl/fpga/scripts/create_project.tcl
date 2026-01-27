# Vivado TCL Script: Create Basys 3 PLL Project
# Run from: build/vivado directory

set project_name "basys3_pll"
set part_name "xc7a35tcpg236-1"
set src_dir "../../"
set fpga_dir "../../fpga"

# Create project
create_project $project_name . -part $part_name -force

# Set project properties
set_property target_language Verilog [current_project]
set_property default_lib work [current_project]

# Add source files
add_files -norecurse [list \
    "${src_dir}/pll_foa.sv" \
    "${fpga_dir}/clk_divider.sv" \
    "${fpga_dir}/debounce.sv" \
    "${fpga_dir}/square_wave_gen.sv" \
    "${fpga_dir}/seven_seg_controller.sv" \
    "${fpga_dir}/led_status.sv" \
    "${fpga_dir}/basys3_pll_top.sv" \
]

# Add constraints
add_files -fileset constrs_1 -norecurse "${fpga_dir}/constraints/basys3_pll.xdc"

# Add simulation sources
set_property SOURCE_SET sources_1 [get_filesets sim_1]
add_files -fileset sim_1 -norecurse "${fpga_dir}/tb/tb_basys3_pll_top.sv"

# Set top module
set_property top basys3_pll_top [current_fileset]
set_property top tb_basys3_pll_top [get_filesets sim_1]

# Update compile order
update_compile_order -fileset sources_1
update_compile_order -fileset sim_1

puts "Project created successfully!"
puts "Open with: vivado basys3_pll.xpr"
