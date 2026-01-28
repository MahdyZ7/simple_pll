#!/bin/bash
# Script to update Vivado project files
set -e

# sources
cp pll_foa.sv /mnt/c/Users/amahd/Documents/Vivado/Simple_pll\
/Simple_pll.srcs/sources_1/imports/rtl/

cp -r fpga/*.sv /mnt/c/Users/amahd/Documents/Vivado/Simple_pll\
/Simple_pll.srcs/sources_1/imports/rtl/fpga/

# testbench
cp tb_pll_foa.sv /mnt/c/Users/amahd/Documents/Vivado/Simple_pll\
/Simple_pll.srcs/sim_1/imports/rtl/

cp fpga/tb/tb_basys3_pll_top.sv /mnt/c/Users/amahd/Documents/Vivado/Simple_pll\
/Simple_pll.srcs/sim_1/imports/rtl/fpga/tb/


# constraints
cp fpga/constraints/basys3_pll.xdc /mnt/c/Users/amahd/Documents/Vivado/Simple_pll\
/Simple_pll.srcs/constrs_1/imports/constraints/