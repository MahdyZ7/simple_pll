module tb_pll_foa;
    logic clk, rst_n, valid_in;
    logic [31:0] x_in, y_out;
    logic valid_out;


    pll_foa #(.DATA_WIDTH(32)) dut (
        .clk, .rst_n, .valid_in, .x_in, .valid_out, .y_out
    );

    always #1 clk = ~clk;  //  clock
	logic toggle;
	logic toggle_jitter;
	logic signed [31:0] amp_noise;

	always #100 amp_noise = $urandom_range(0, 4) - 2;
	always #(32'd100) toggle = ~toggle;
	always #(32'd100 + amp_noise) toggle_jitter = ~toggle_jitter;
	assign x_in = (toggle ? 32'd25 : 32'd50) + amp_noise;


    initial begin
		$dumpvars;
        clk = 0; rst_n = 0; valid_in = 0;
		toggle = 0; toggle_jitter = 0;
		amp_noise = 0;
        #20 rst_n = 1;
		valid_in = 1;
		repeat(10000) @(posedge clk);
    	$stop;
    end
	
endmodule