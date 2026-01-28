module tb_pll_foa;
    logic clk, rst_n, valid_in;
    logic [31:0] x_in, y_out;
    logic valid_out;


    pll_foa #(.DATA_WIDTH(32)) dut (
        .clk, .rst_n, .valid_in, .x_in, .valid_out, .y_out
    );

	// iir_time_diff_filter #(.DATA_WIDTH(32)) dut_cl (
	// 	.clk, .rst_n, .valid_in, .x_in, .y_out, .valid_out
	// );
	// iir_time_diff_filter_single_cycle #(.DATA_WIDTH(32)) dut_cl (
	// 	.clk, .rst_n, .valid_in, .x_in, .y_out, .valid_out
	// );

    // Q24 format: value * 2^24 = value * 16777216
    // 25 in Q24 = 419430400
    // 50 in Q24 = 838860800
    // localparam Q24_25 = 64'd419430400;
    // localparam Q24_50 = 64'd838860800;

    always #1 clk = ~clk;  //  clock
	// always #200 x_in = ~x_in; // Change input every 20 time units
	always repeat (100) begin
		if (x_in == 32'd25)
			x_in = 32'd50;
		else
			x_in = 32'd25;
		#1000;
	end

    initial begin
		$dumpvars;
        clk = 0; rst_n = 0; valid_in = 0; x_in = 32'd25;
        #20 rst_n = 1;
		valid_in = 1;
    	#10000 $finish;
    end
endmodule