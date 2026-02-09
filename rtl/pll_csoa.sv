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
        localparam signed [COEFF_WIDTH-1:0] c0 =  +32'sd16771680;  // 0.99967 * 16777216 ≈ 16771680
        localparam signed [COEFF_WIDTH-1:0] c1 =  +32'sd60968404;  // 3.634 * 16777216 ≈ 60968404
        localparam signed [COEFF_WIDTH-1:0] c2 =  +32'sd85523520;  // 5.0976 * 16777216 ≈ 85523520
        localparam signed [COEFF_WIDTH-1:0] c3 =  +32'sd57090988;  // 3.40289 * 16777216 ≈ 57090988
        localparam signed [COEFF_WIDTH-1:0] c4 =  +32'sd17725850;  // 1.05654 * 16777216 ≈ 17725850
        localparam signed [COEFF_WIDTH-1:0] c5 =  +32'sd1982377;  // 0.118159 * 16777216 ≈ 1982377
        localparam signed [COEFF_WIDTH-1:0] c6 =  +32'sd14636;  // 0.000872383 * 16777216 ≈ 14636
        localparam signed [COEFF_WIDTH-1:0] c7 =  -32'sd6079;  // -0.000362338 * 16777216 ≈ -6079

        // Y coefficients: 
        localparam signed [COEFF_WIDTH-1:0] cy1 =  -32'sd60976172;  // -3.63446 * 16777216 ≈ -60976172
        localparam signed [COEFF_WIDTH-1:0] cy2 =  -32'sd85521120;  // -5.09746 * 16777216 ≈ -85521120
        localparam signed [COEFF_WIDTH-1:0] cy3 =  -32'sd57083236;  // -3.40243 * 16777216 ≈ -57083236
        localparam signed [COEFF_WIDTH-1:0] cy4 =  -32'sd17722712;  // -1.05636 * 16777216 ≈ -17722712
        localparam signed [COEFF_WIDTH-1:0] cy5 =  -32'sd1982292;  // -0.118154 * 16777216 ≈ -1982292
        localparam signed [COEFF_WIDTH-1:0] cy6 =  -32'sd14704;  // -0.000876398 * 16777216 ≈ -14704
        localparam signed [COEFF_WIDTH-1:0] cy7 =  +32'sd6072;  // 0.00036194 * 16777216 ≈ 6072

    // Delay lines for x and y
	logic signed [DATA_WIDTH-1:0] x_delay [0:6];
	logic signed [DATA_WIDTH-1:0] y_delay [0:6];

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
		temp_sum_x = (c0 * x_in) + (c1 * x_delay[0]) + (c2 * x_delay[1]) + (c3 * x_delay[2]) + (c4 * x_delay[3]) + (c5 * x_delay[4]) + (c6 * x_delay[5]) + (c7 * x_delay[6]);
		temp_sum_y = ((cy1 * y_delay[0]) + (cy2 * y_delay[1]) + (cy3 * y_delay[2]) + (cy4 * y_delay[3]) + (cy5 * y_delay[4]) + (cy6 * y_delay[5]) + (cy7 * y_delay[6]) + (1 << (FRAC_WIDTH-1))) >>> FRAC_WIDTH;
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
			y_delay[0] <= 0;
			y_delay[1] <= 0;
			y_delay[2] <= 0;
			y_delay[3] <= 0;
			y_delay[4] <= 0;
			y_delay[5] <= 0;
			y_delay[6] <= 0;
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
			end

		end
	end
	assign valid_out = valid_in;

endmodule
