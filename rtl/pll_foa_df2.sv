module pll_foa_df2 #(
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

	`include "pll_foa_coeffs.svh"

    // Direct Form II: single set of delay elements (w)
	logic signed [DATA_WIDTH-1:0] w;
	logic signed [DATA_WIDTH-1:0] w_delay [0:2];

	// Wider accumulators to prevent overflow (matches pll_foa.sv)
	logic signed [DATA_WIDTH+COEFF_WIDTH-1:0] feedback_acc;
	logic signed [DATA_WIDTH+COEFF_WIDTH-1:0] feedforward_acc;

	always_comb begin
		// Feedback path: w[n] = x[n] + (cy1*w[n-1] + cy2*w[n-2] + cy3*w[n-3]) >> FRAC
		feedback_acc = cy1 * w_delay[0] + cy2 * w_delay[1] + cy3 * w_delay[2];
		w = x_in + ((feedback_acc + (1 <<< (FRAC_WIDTH-1))) >>> FRAC_WIDTH);
		// Feedforward path: y[n] = (c0*w[n] + c1*w[n-1] + c2*w[n-2] + c3*w[n-3]) >> FRAC
		feedforward_acc = c0 * w + c1 * w_delay[0] + c2 * w_delay[1] + c3 * w_delay[2];
		y_out = (feedforward_acc + (1 <<< (FRAC_WIDTH-1))) >>> FRAC_WIDTH;
	end

	always_ff @(posedge clk or negedge rst_n) begin
		if (!rst_n) begin
			w_delay[0] <= 0;
			w_delay[1] <= 0;
			w_delay[2] <= 0;
		end else if (valid_in) begin
			w_delay[0] <= w;
			w_delay[1] <= w_delay[0];
			w_delay[2] <= w_delay[1];
		end
	end
	assign valid_out = valid_in;

endmodule
