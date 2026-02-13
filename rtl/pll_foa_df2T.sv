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

        // Fixed point coefficients with frac size 24 :
        // X coefficients: 
        localparam signed [COEFF_WIDTH-1:0] c0 =  +32'sd1244869;  // 0.0742 * 16777216 ≈ 1244869
        localparam signed [COEFF_WIDTH-1:0] c1 =  -32'sd1030121;  // -0.0614 * 16777216 ≈ -1030121
        localparam signed [COEFF_WIDTH-1:0] c2 =  -32'sd1236481;  // -0.0737 * 16777216 ≈ -1236481
        localparam signed [COEFF_WIDTH-1:0] c3 =  +32'sd1040187;  // 0.062 * 16777216 ≈ 1040187

        // Y coefficients: 
        localparam signed [COEFF_WIDTH-1:0] cy1 =  +32'sd46050104;  // 2.7448 * 16777216 ≈ 46050104
        localparam signed [COEFF_WIDTH-1:0] cy2 =  -32'sd42226576;  // -2.5169 * 16777216 ≈ -42226576
        localparam signed [COEFF_WIDTH-1:0] cy3 =  +32'sd12935234;  // 0.771 * 16777216 ≈ 12935234

    // Direct Form II Transpose: single set of delay elements (w)
	logic signed [DATA_WIDTH+COEFF_WIDTH-1:0] y_temp;
	logic signed [DATA_WIDTH+COEFF_WIDTH-1:0] w1;
	logic signed [DATA_WIDTH+COEFF_WIDTH-1:0] w1_delay;
	logic signed [DATA_WIDTH+COEFF_WIDTH-1:0] w2;
	logic signed [DATA_WIDTH+COEFF_WIDTH-1:0] w2_delay;
	logic signed [DATA_WIDTH+COEFF_WIDTH-1:0] w3;
	logic signed [DATA_WIDTH+COEFF_WIDTH-1:0] w3_delay;


	// Wider accumulators to prevent overflow (matches pll_foa.sv)
	// logic signed [DATA_WIDTH+COEFF_WIDTH:0] feedback_acc;
	// logic signed [DATA_WIDTH+COEFF_WIDTH:0] feedforward_acc;

	always_ff @(posedge clk or negedge rst_n) begin
		if (!rst_n) begin
			w3 <= 0;
			w2 <= 0;
			w1 <= 0;
			y_temp <= 0;
		end else begin
			w3 = ((y_temp * cy3) >>> FRAC_WIDTH) + x_in * c3;
			w2 = ((y_temp * cy2) >>> FRAC_WIDTH) + x_in * c2 + w3_delay;
			w1 = ((y_temp * cy1) >>> FRAC_WIDTH) + x_in * c1 + w2_delay;
			y_temp = x_in * c0 + w1_delay;
		end
		y_out = y_temp >>> FRAC_WIDTH;
	end

	always_ff @(posedge clk or negedge rst_n) begin
		if (!rst_n) begin
			w1_delay <= 0;
			w2_delay <= 0;
			w3_delay <= 0;
		end else if (valid_in) begin
			w1_delay <= w1;
			w2_delay <= w2;
			w3_delay <= w3;
		end
	end
	assign valid_out = valid_in;

endmodule
