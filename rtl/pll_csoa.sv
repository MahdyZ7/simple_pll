module pll_csoa #(
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
        localparam signed [COEFF_WIDTH-1:0] c0 =  +32'sd2350;  // 0.000140065 * 16777216 ≈ 2350
        localparam signed [COEFF_WIDTH-1:0] c1 =  -32'sd16414;  // -0.000978371 * 16777216 ≈ -16414
        localparam signed [COEFF_WIDTH-1:0] c2 =  +32'sd46788;  // 0.00278881 * 16777216 ≈ 46788
        localparam signed [COEFF_WIDTH-1:0] c3 =  -32'sd65309;  // -0.00389269 * 16777216 ≈ -65309
        localparam signed [COEFF_WIDTH-1:0] c4 =  +32'sd32411;  // 0.00193182 * 16777216 ≈ 32411
        localparam signed [COEFF_WIDTH-1:0] c5 =  +32'sd32898;  // 0.00196086 * 16777216 ≈ 32898
        localparam signed [COEFF_WIDTH-1:0] c6 =  -32'sd65309;  // -0.00389269 * 16777216 ≈ -65309
        localparam signed [COEFF_WIDTH-1:0] c7 =  +32'sd46510;  // 0.00277221 * 16777216 ≈ 46510
        localparam signed [COEFF_WIDTH-1:0] c8 =  -32'sd16240;  // -0.000968002 * 16777216 ≈ -16240
        localparam signed [COEFF_WIDTH-1:0] c9 =  +32'sd2315;  // 0.000137991 * 16777216 ≈ 2315

        // Y coefficients: 
        localparam signed [COEFF_WIDTH-1:0] cy1 =  +32'sd150755328;  // 8.98572 * 16777216 ≈ 150755328
        localparam signed [COEFF_WIDTH-1:0] cy2 =  -32'sd602064128;  // -35.8858 * 16777216 ≈ -602064128
        localparam signed [COEFF_WIDTH-1:0] cy3 =  +32'sd1402586112;  // 83.6007 * 16777216 ≈ 1402586112
        localparam signed [COEFF_WIDTH-1:0] cy4 =  -32'sd2100537600;  // -125.202 * 16777216 ≈ -2100537600
        localparam signed [COEFF_WIDTH-1:0] cy5 =  +32'sd2097202304;  // 125.003 * 16777216 ≈ 2097202304
        localparam signed [COEFF_WIDTH-1:0] cy6 =  -32'sd1395912832;  // -83.2029 * 16777216 ≈ -1395912832
        localparam signed [COEFF_WIDTH-1:0] cy7 =  +32'sd597297600;  // 35.6017 * 16777216 ≈ 597297600
        localparam signed [COEFF_WIDTH-1:0] cy8 =  -32'sd149087024;  // -8.88628 * 16777216 ≈ -149087024
        localparam signed [COEFF_WIDTH-1:0] cy9 =  +32'sd16538884;  // 0.985794 * 16777216 ≈ 16538884

    // Delay lines for x and y
	logic signed [DATA_WIDTH-1:0] x_delay [0:13];
	logic signed [DATA_WIDTH-1:0] y_delay [0:12];

	// Intermediate product accumulators (wider to prevent overflow)
	// logic signed [(DATA_WIDTH+COEFF_WIDTH)-1:0] acc_x, acc_y;
	logic signed [DATA_WIDTH+COEFF_WIDTH:0] temp_sum_x;  // Extra bits for final scaling
	logic signed [DATA_WIDTH+COEFF_WIDTH:0] temp_sum_y;  // Extra bits for final scaling

	// Input valid pipeline

	always_comb begin
		// Feedforward: c0*x[n] + c1*x[n-1] + c2*x[n-2] + c3*x[n-3]
		// Feedback: cy1*y[n-1] + cy2*y[n-2] + cy3*y[n-3] + cy4*y[n-4] + cy5*y[n-5] + cy6*y[n-6] + cy7*y[n-7]
		// x_in and x_delay are Q16, coefficients are Q16
		// Feedforward: Q24 * Q24 = Q48, shift by 24 to get Q24
		// Feedback: Q24 * Q24 = Q48, shift by 24 to get Q24
		temp_sum_x = (c0 * x_in) + (c1 * x_delay[0]) + (c2 * x_delay[1]) + (c3 * x_delay[2]) +
						(c4 * x_delay[3]) + (c5 * x_delay[4]) + (c6 * x_delay[5]) + 
						(c7 * x_delay[6]) + (c8 * x_delay[7]) + (c9 * x_delay[8]);
		temp_sum_y = ((cy1 * y_delay[0]) + (cy2 * y_delay[1]) + (cy3 * y_delay[2]) + (cy4 * y_delay[3]) + 
						(cy5 * y_delay[4]) + (cy6 * y_delay[5]) + (cy7 * y_delay[6]) + 
						(cy8 * y_delay[7]) + (cy9 * y_delay[8]) + 
						(1 << (FRAC_WIDTH-1))) >>> FRAC_WIDTH;
		y_out = ((temp_sum_x + temp_sum_y) + (1 << (FRAC_WIDTH-1))) >>> FRAC_WIDTH;  // Output is Q16
	end

	always_ff @(posedge clk or negedge rst_n) begin
		if (!rst_n) begin
			x_delay[0] <= 0;
			x_delay[1] <= 0;
			x_delay[2] <= 0;
			x_delay[3] <= 0;
			x_delay[4] <= 0;
			x_delay[5] <= 0;
			x_delay[6] <= 0;
			x_delay[7] <= 0;
			x_delay[8] <= 0;
			x_delay[9] <= 0;
			x_delay[10] <= 0;
			x_delay[11] <= 0;
			x_delay[12] <= 0;
			x_delay[13] <= 0;
			y_delay[0] <= 0;
			y_delay[1] <= 0;
			y_delay[2] <= 0;
			y_delay[3] <= 0;
			y_delay[4] <= 0;
			y_delay[5] <= 0;
			y_delay[6] <= 0;
			y_delay[7] <= 0;
			y_delay[8] <= 0;
			y_delay[9] <= 0;
			y_delay[10] <= 0;
			y_delay[11] <= 0;
			y_delay[12] <= 0;
		end else begin
			// Shift x delays: x -> x_delay, x -> x_delay[1], etc.
			if (valid_in) begin
				x_delay[0] <= x_in;
				x_delay[1] <= x_delay[0];
				x_delay[2] <= x_delay[1];
				x_delay[3] <= x_delay[2];
				x_delay[4] <= x_delay[3];
				x_delay[5] <= x_delay[4];
				x_delay[6] <= x_delay[5];
				x_delay[7] <= x_delay[6];
				x_delay[8] <= x_delay[7];
				x_delay[9] <= x_delay[8];
				x_delay[10] <= x_delay[9];
				x_delay[11] <= x_delay[10];
				x_delay[12] <= x_delay[11];
				x_delay[13] <= x_delay[12];
			end

			// Compute y and shift y delays
			if (valid_in) begin
				// Shift y delays
				y_delay[0] <= temp_sum_x + temp_sum_y;
				y_delay[1] <= y_delay[0];
				y_delay[2] <= y_delay[1];
				y_delay[3] <= y_delay[2];
				y_delay[4] <= y_delay[3];
				y_delay[5] <= y_delay[4];
				y_delay[6] <= y_delay[5];
				y_delay[7] <= y_delay[6];
				y_delay[8] <= y_delay[7];
				y_delay[9] <= y_delay[8];
				y_delay[10] <= y_delay[9];
				y_delay[11] <= y_delay[10];
				y_delay[12] <= y_delay[11];
			end

		end
	end
	assign valid_out = valid_in;

endmodule
