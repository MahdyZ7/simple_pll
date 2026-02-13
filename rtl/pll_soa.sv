module pll_soa #(
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
        localparam signed [COEFF_WIDTH-1:0] c0 =  +32'sd2447;  // 0.000145872 * 16777216 ≈ 2447
        localparam signed [COEFF_WIDTH-1:0] c1 =  -32'sd7333;  // -0.000437064 * 16777216 ≈ -7333
        localparam signed [COEFF_WIDTH-1:0] c2 =  +32'sd4876;  // 0.000290639 * 16777216 ≈ 4876
        localparam signed [COEFF_WIDTH-1:0] c3 =  +32'sd4895;  // 0.000291744 * 16777216 ≈ 4895
        localparam signed [COEFF_WIDTH-1:0] c4 =  -32'sd7323;  // -0.000436512 * 16777216 ≈ -7323
        localparam signed [COEFF_WIDTH-1:0] c5 =  +32'sd2438;  // 0.00014532 * 16777216 ≈ 2438

        // Y coefficients: 
        localparam signed [COEFF_WIDTH-1:0] cy1 =  +32'sd83822816;  // 4.99623 * 16777216 ≈ 83822816
        localparam signed [COEFF_WIDTH-1:0] cy2 =  -32'sd167519136;  // -9.98492 * 16777216 ≈ -167519136
        localparam signed [COEFF_WIDTH-1:0] cy3 =  +32'sd167392736;  // 9.97738 * 16777216 ≈ 167392736
        localparam signed [COEFF_WIDTH-1:0] cy4 =  -32'sd83633200;  // -4.98493 * 16777216 ≈ -83633200
        localparam signed [COEFF_WIDTH-1:0] cy5 =  +32'sd16714015;  // 0.996233 * 16777216 ≈ 16714015

    // Delay lines for x and y
	logic signed [DATA_WIDTH-1:0] x_delay [0:4];
	logic signed [DATA_WIDTH-1:0] y_delay [0:4];

	// Intermediate product accumulators (wider to prevent overflow)
	// logic signed [(DATA_WIDTH+COEFF_WIDTH)-1:0] acc_x, acc_y;
	logic signed [DATA_WIDTH+COEFF_WIDTH:0] temp_sum_x;  // Extra bits for final scaling
	logic signed [DATA_WIDTH+COEFF_WIDTH:0] temp_sum_y;  // Extra bits for final scaling

	// Input valid pipeline

	always_comb begin
		// Feedforward: c0*x[n] + c1*x[n-1] + c2*x[n-2] + c3*x[n-3]
		// Feedback: cy1*y[n-1] + cy2*y[n-2] + cy3*y[n-3]
		// x_in and x_delay are Q16, coefficients are Q16
		// Feedforward: Q24 * Q24 = Q48, shift by 24 to get Q24
		// Feedback: Q24 * Q24 = Q48, shift by 24 to get Q24
		temp_sum_x = (c0 * x_in) + (c1 * x_delay[0]) + (c2 * x_delay[1]) + (c3 * x_delay[2]) + (c4 * x_delay[3]) + (c5 * x_delay[4]);
		temp_sum_y = ((cy1 * y_delay[0]) + (cy2 * y_delay[1]) + (cy3 * y_delay[2]) + (cy4 * y_delay[3]) + (cy5 * y_delay[4]) + (1 << (FRAC_WIDTH-1))) >>> FRAC_WIDTH;
		y_out = ((temp_sum_x + temp_sum_y) + (1 << (FRAC_WIDTH-1))) >>> FRAC_WIDTH;  // Output is Q16
	end

	always_ff @(posedge clk or negedge rst_n) begin
		if (!rst_n) begin
			x_delay[0] <= 0;
			x_delay[1] <= 0;
			x_delay[2] <= 0;
			x_delay[3] <= 0;
			x_delay[4] <= 0;
			y_delay[0] <= 0;
			y_delay[1] <= 0;
			y_delay[2] <= 0;
			y_delay[3] <= 0;
			y_delay[4] <= 0;
		end else begin
			// Shift x delays: x -> x_delay, x -> x_delay[1], etc.
			if (valid_in) begin
				x_delay[0] <= x_in;
				x_delay[1] <= x_delay[0];
				x_delay[2] <= x_delay[1];
				x_delay[3] <= x_delay[2];
				x_delay[4] <= x_delay[3];
			end

			// Compute y and shift y delays
			if (valid_in) begin
				// Shift y delays
				y_delay[0] <= temp_sum_x + temp_sum_y;
				y_delay[1] <= y_delay[0];
				y_delay[2] <= y_delay[1];
				y_delay[3] <= y_delay[2];
				y_delay[4] <= y_delay[3];
			end

		end
	end
	assign valid_out = valid_in;

endmodule
