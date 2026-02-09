# Makefile for Questa Sim simulation

# Colors
BLUE = "\\033[36m"
NC = "\\033[0m"
RED = "\\033[91m"


# Questa Sim commands
VLIB = vlib.exe
VMAP = vmap.exe
VLOG = vlog.exe
VSIM = vsim.exe

# Icarus sim commands
ICARUS := iverilog
GTKWAVE := gtkwave


# Source files (add your .sv files here)
SV_FILES := $(shell find . -name "*sv")

# Testbench top module
TB_TOP = tb_pll_foa

# Library name
LIB_NAME := $(shell echo $(TB_TOP) | tr '[:lower:]' '[:upper:]')

# Simulation options
SIM_OPTIONS = -voptargs=+acc -quiet 
VERBOSE_OPTIONS := -hazards -lint -lrmclassinit -pedanticerrors -warning error -fsmverbose

all: compile simulate

icarus: icarus_run

# Create library
create_lib:
	@echo "$(BLUE)>> Create a logical library $(LIB_NAME) $(NC)"
	$(VLIB) -quiet $(LIB_NAME)

# Map library
map_lib: create_lib
	@echo "$(BLUE)>> Maping library to a directory $(LIB_NAME) $(NC)"
	$(VMAP) -quiet $(LIB_NAME) $(LIB_NAME)

# Compile SystemVerilog files
compile: map_lib
	@echo "$(BLUE)>> Compiling SystemVerilog files: $(SV_FILES) $(NC)"
	$(VLOG) -sv -quiet -work $(LIB_NAME) +acc $(SV_FILES)

# Run simulation
simulate: compile
	@echo "$(BLUE)>> Running simulation $(NC)"
	$(VSIM) $(SIM_OPTIONS) -L $(LIB_NAME) $(LIB_NAME).$(TB_TOP) -do "log -r /*;add wave -r /*; run -all;view wave;"

# Run cli simulation
cli: compile
	@echo "$(BLUE)>> Running simulation command line mode $(NC)"
	$(VSIM) -c $(SIM_OPTIONS) -L $(LIB_NAME) $(LIB_NAME).$(TB_TOP) -do "run -all;exit;"

do:
	@echo "$(BLUE)>> Running simulation form sim.do file $(NC)"
	$(VSIM) -do sim.do
do_noise:
	@echo "$(BLUE)>> Running simulation form sim.do file $(NC)"
	$(VSIM) -do sim_noise.do

do_fpga:
	@echo "$(BLUE)>> Running FPGA simulation form sim.do file for fpga $(NC)"
	$(VSIM) -do fpga/sim.do

icarus_compile:
	mkdir -p build
	@echo "$(BLUE)>> Compiling SystemVerilog files: $(SV_FILES) $(NC)"
	$(ICARUS)  -Wall -g2012  -o build/testbench $(SV_FILES)

icarus_run: icarus_compile
	cd build && ./testbench
	@if [ -f "./build/dump.vcd" ]; then \
		cd build && $(GTKWAVE) -M dump.vcd .dump.gtkw -a .dump.gtkw & \
	else \
		echo "$(RED) No dump.vcd file found, Make sure '\$$dumpvars' is included in the testbench $(NC)"; \
	fi

wave:
	@if [ -f "./build/dump.vcd" ]; then \
		echo "$(BLUE) Icarus waves $(NC)"; \
		cd build && $(GTKWAVE) -M dump.vcd .dump.gtkw -a .dump.gtkw & \
	else \
		echo "$(RED) No waveform found for Icarus $(NC)"; \
	fi
	@if [ -f "vsim.wlf" ]; then \
		echo "$(BLUE) Questasim waves $(NC)"; \
		$(VSIM) -view vsim.wlf add wave -r /*; \
	else \
		echo "$(RED) No waveform found for Questasim $(NC)"; \
	fi

help:
	@echo "$(BLUE) \t *** Makefile rules for SystemVerilog *** $(NC)\n\
	This is a makefile to compile and simulate SystemVerilog projects using modelsim and icarus. \
	Make sure you atleast one of them installed.\n\
	In the makefile, Intialize the variable 'TB_TOP' to be the testbench of your project \
	\n$(BLUE) \t *** The Makefile Targets *** $(NC)\n\
	$(BLUE)all$(NC): The default. simulate using Questasim / Modelsim and display all waves \n\
	$(BLUE)compile$(NC): compile using Questasim to check for syntax errors\n\
	$(BLUE)cli$(NC): Command line simulation using Questasim / Modelsim \n\
	$(BLUE)do$(NC): Use sim.do file to \n\
	$(BLUE)icarus$(NC): simulate using icarus and display all waves \n\
	$(BLUE)wave$(NC): display waveforms of prevoius simulation \n\
	$(BLUE)help$(NC): display help \n\
	$(BLUE)clean$(NC): remove all simulation and graph files \n\
	$(BLUE)re$(NC): clean and resimulate \n\
	";

# Clean up
clean:
	rm -rf $(LIB_NAME) transcript *.wlf build *.vcd wlft*

re: clean all

# ============================================================================
# FPGA (Basys 3) Targets
# ============================================================================

# FPGA source files
FPGA_SRC := pll_foa.sv \
            fpga/clk_divider.sv \
            fpga/debounce.sv \
            fpga/square_wave_gen.sv \
            fpga/seven_seg_controller.sv \
            fpga/led_status.sv \
            fpga/basys3_pll_top.sv

FPGA_TB := fpga/tb/tb_basys3_pll_top.sv
FPGA_XDC := fpga/constraints/basys3_pll.xdc
FPGA_TOP := basys3_pll_top
FPGA_TB_TOP := tb_basys3_pll_top

# Vivado settings
VIVADO := vivado
VIVADO_PROJECT := basys3_pll
VIVADO_PART := xc7a35tcpg236-1

# Icarus FPGA simulation
fpga_icarus: fpga_icarus_compile fpga_icarus_run

fpga_icarus_compile:
	mkdir -p build/fpga
	@echo "$(BLUE)>> Compiling FPGA testbench with Icarus $(NC)"
	$(ICARUS) -Wall -g2012 -o build/fpga/$(FPGA_TB_TOP) $(FPGA_SRC) $(FPGA_TB)

fpga_icarus_run: fpga_icarus_compile
	cd build/fpga && ./$(FPGA_TB_TOP)
	@if [ -f "./build/fpga/tb_basys3_pll_top.vcd" ]; then \
		cd build/fpga && $(GTKWAVE) tb_basys3_pll_top.vcd & \
	else \
		echo "$(RED) No VCD file found $(NC)"; \
	fi

# Vivado project creation
vivado_project:
	@echo "$(BLUE)>> Creating Vivado project $(NC)"
	mkdir -p build/vivado
	cd build/vivado && $(VIVADO) -mode batch -source ../../fpga/scripts/create_project.tcl

# Vivado synthesis (requires project)
vivado_synth:
	@echo "$(BLUE)>> Running Vivado synthesis $(NC)"
	cd build/vivado && $(VIVADO) -mode batch -source ../../fpga/scripts/run_synth.tcl

# Vivado implementation and bitstream
vivado_impl:
	@echo "$(BLUE)>> Running Vivado implementation $(NC)"
	cd build/vivado && $(VIVADO) -mode batch -source ../../fpga/scripts/run_impl.tcl

# Quick Vivado non-project flow
vivado_quick:
	@echo "$(BLUE)>> Running Vivado non-project flow $(NC)"
	mkdir -p build/vivado
	cd build/vivado && $(VIVADO) -mode batch -source ../../fpga/scripts/quick_build.tcl

# Open Vivado GUI
vivado_gui:
	@echo "$(BLUE)>> Opening Vivado GUI $(NC)"
	cd build/vivado && $(VIVADO) $(VIVADO_PROJECT).xpr &

# Program FPGA
vivado_program:
	@echo "$(BLUE)>> Programming FPGA $(NC)"
	cd build/vivado && $(VIVADO) -mode batch -source ../../fpga/scripts/program.tcl

# FPGA clean
fpga_clean:
	rm -rf build/fpga build/vivado .Xil *.jou *.log

.PHONY: all create_lib map_lib compile simulate cli do icarus_compile \
	icarus_run wave help clean re \
	fpga_icarus fpga_icarus_compile fpga_icarus_run \
	vivado_project vivado_synth vivado_impl vivado_quick vivado_gui vivado_program fpga_clean