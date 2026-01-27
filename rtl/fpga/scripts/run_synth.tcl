# Vivado TCL Script: Run Synthesis
# Run from: build/vivado directory (with project open)

set project_name "basys3_pll"

# Open project if not already open
if {[catch {current_project}]} {
    open_project ${project_name}.xpr
}

# Reset synthesis run
reset_run synth_1

# Launch synthesis
launch_runs synth_1 -jobs 4
wait_on_run synth_1

# Check for errors
if {[get_property PROGRESS [get_runs synth_1]] != "100%"} {
    puts "ERROR: Synthesis failed!"
    exit 1
}

# Open synthesized design and report
open_run synth_1
report_utilization -file synth_utilization.rpt
report_timing_summary -file synth_timing.rpt

puts "Synthesis completed successfully!"
puts "Reports: synth_utilization.rpt, synth_timing.rpt"
