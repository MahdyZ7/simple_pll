module pll_cfoa_ni #(
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

	`include "pll_cfoa_noIntegrator_coeffs.svh"

    // Delay lines for x and y
	logic signed [DATA_WIDTH-1:0] x_delay [0:8];
	logic signed [DATA_WIDTH-1:0] y_delay [0:7];

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
			x_delay[5] <= 0;
			x_delay[6] <= 0;
			x_delay[7] <= 0;
			x_delay[8] <= 0;
			y_delay[0] <= 0;
			y_delay[1] <= 0;
			y_delay[2] <= 0;
			y_delay[3] <= 0;
			y_delay[4] <= 0;
			y_delay[5] <= 0;
			y_delay[6] <= 0;
			y_delay[7] <= 0;
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
			end

		end
	end
	assign valid_out = valid_in;

endmodule
