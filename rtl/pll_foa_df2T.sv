module pll_foa_df2T #(
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

    // Direct Form II Transposed state registers (product precision: 2*FRAC_WIDTH fractional bits)
	logic signed [DATA_WIDTH+COEFF_WIDTH:0] w1_delay;
	logic signed [DATA_WIDTH+COEFF_WIDTH:0] w2_delay;
	logic signed [DATA_WIDTH+COEFF_WIDTH:0] w3_delay;

	logic signed [DATA_WIDTH+COEFF_WIDTH:0] y_full;

	// DF2T: y[n]  = c0*x[n] + w1[n-1]
	//       w1[n] = c1*x[n] + cy1*y[n] + w2[n-1]
	//       w2[n] = c2*x[n] + cy2*y[n] + w3[n-1]
	//       w3[n] = c3*x[n] + cy3*y[n]
	always_comb begin
		y_full = c0 * x_in + w1_delay;
		y_out  = (y_full + (1 << (FRAC_WIDTH-1))) >>> FRAC_WIDTH;
	end

	always_ff @(posedge clk or negedge rst_n) begin
		if (!rst_n) begin
			w1_delay <= 0;
			w2_delay <= 0;
			w3_delay <= 0;
		end else if (valid_in) begin
			w1_delay <= c1 * x_in + cy1 * y_out + w2_delay;
			w2_delay <= c2 * x_in + cy2 * y_out + w3_delay;
			w3_delay <= c3 * x_in + cy3 * y_out;
		end
	end
	assign valid_out = valid_in;

endmodule
