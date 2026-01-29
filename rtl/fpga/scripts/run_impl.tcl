# Vivado TCL Script: Run Implementation and Generate Bitstream
# Run from: build/vivado directory (with project open)

set project_name "basys3_pll"

# Open project if not already open
if {[catch {current_project}]} {
    open_project ${project_name}.xpr
}

# Launch implementation
launch_runs impl_1 -jobs 4
wait_on_run impl_1

# Check for errors
if {[get_property PROGRESS [get_runs impl_1]] != "100%"} {
    puts "ERROR: Implementation failed!"
    exit 1
}

# Generate bitstream
launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1

# Open implemented design and report
open_run impl_1
report_utilization -file impl_utilization.rpt
report_timing_summary -file impl_timing.rpt
report_power -file impl_power.rpt

puts "Implementation and bitstream generation completed!"
puts "Bitstream: ${project_name}.runs/impl_1/basys3_pll_top.bit"
puts "Reports: impl_utilization.rpt, impl_timing.rpt, impl_power.rpt"
