# Vivado TCL Script: Program FPGA
# Run from: build/vivado directory

set bitstream "basys3_pll_top.bit"

# Check if bitstream exists (try multiple locations)
set bit_paths [list \
    $bitstream \
    "basys3_pll.runs/impl_1/basys3_pll_top.bit" \
]

set found_bit ""
foreach path $bit_paths {
    if {[file exists $path]} {
        set found_bit $path
        break
    }
}

if {$found_bit eq ""} {
    puts "ERROR: Bitstream not found!"
    puts "Expected locations:"
    foreach path $bit_paths {
        puts "  - $path"
    }
    exit 1
}

puts "Using bitstream: $found_bit"

# Open hardware manager
open_hw_manager

# Connect to hardware server
connect_hw_server -allow_non_jtag

# Open target (auto-detect)
open_hw_target

# Get the device
set device [lindex [get_hw_devices] 0]
current_hw_device $device

# Set programming file
set_property PROGRAM.FILE $found_bit [current_hw_device]

# Program device
program_hw_devices [current_hw_device]

puts "FPGA programmed successfully!"

# Close connection
close_hw_target
disconnect_hw_server
close_hw_manager
