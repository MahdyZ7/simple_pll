module pll_foa_2 #(
    parameter DATA_WIDTH = 32,	// Input/output data width
    parameter COEFF_WIDTH = 32,	// Coefficient width (fixed-point)
	parameter FRAC_WIDTH = 24	// Fractional bits in fixed-point representation
) (
    input  logic							clk,
    input  logic							rst_n,
    input  logic							valid_in,
    input  logic signed [DATA_WIDTH-1:0]	x_in,
    output logic							valid_out,
    output logic signed [DATA_WIDTH-1:0]	y_out
);

        // Fixed point coefficients with frac size 24 :
        // X coefficients: 
        localparam signed [COEFF_WIDTH-1:0] c0 =  +32'sd16769260;  // 0.999526 * 16777216 ≈ 16769260
        localparam signed [COEFF_WIDTH-1:0] c1 =  +32'sd23502144;  // 1.40084 * 16777216 ≈ 23502144
        localparam signed [COEFF_WIDTH-1:0] c2 =  +32'sd6732893;  // 0.401312 * 16777216 ≈ 6732893

        // Y coefficients: 
        localparam signed [COEFF_WIDTH-1:0] cy1 =  -32'sd23496272;  // -1.40049 * 16777216 ≈ -23496272
        localparam signed [COEFF_WIDTH-1:0] cy2 =  -32'sd6730813;  // -0.401188 * 16777216 ≈ -6730813
	
    // Delay lines for x and y
	logic signed [DATA_WIDTH-1:0] x_delay [0:1];
	logic signed [DATA_WIDTH-1:0] y_delay [0:1];

	// Intermediate product accumulators (wider to prevent overflow)
	// logic signed [(DATA_WIDTH+COEFF_WIDTH)-1:0] acc_x, acc_y;
	logic signed [DATA_WIDTH+COEFF_WIDTH:0] temp_sum_x;  // Extra bits for final scaling
	logic signed [DATA_WIDTH+COEFF_WIDTH:0] temp_sum_y;  // Extra bits for final scaling

	// Input valid pipeline

	always_comb begin
		// Feedforward: c0*x[n] + c1*x[n-1] + c2*x[n-2]
		// Feedback: cy1*y[n-1] + cy2*y[n-2]
		// Feedforward: Q24 * Q0 = Q24
		// Feedback: Q24 * Q24 = Q48, shift by 24 to get Q24
		temp_sum_x = (c0 * x_in) + (c1 * x_delay[0]) + (c2 * x_delay[1]);
		temp_sum_y = ((cy1 * y_delay[0]) + (cy2 * y_delay[1]) + (1 << (FRAC_WIDTH-1))) >>> FRAC_WIDTH;
		y_out = ((temp_sum_x + temp_sum_y) + (1 << (FRAC_WIDTH-1))) >>> FRAC_WIDTH;  // Output is Q16
	end

	always_ff @(posedge clk or negedge rst_n) begin
		if (!rst_n) begin
			x_delay[0] <= 0;
			x_delay[1] <= 0;
			y_delay[0] <= 0;
			y_delay[1] <= 0;
		end else begin
			// Shift x delays: x -> x_delay, x -> x_delay[1], etc.
			if (valid_in) begin
				x_delay[0] <= x_in;
				x_delay[1] <= x_delay[0];
			end

			// Compute y and shift y delays
			if (valid_in) begin
				// Shift y delays
				y_delay[0] <= temp_sum_x + temp_sum_y;
				y_delay[1] <= y_delay[0];
			end

		end
	end
	assign valid_out = valid_in;

endmodule
