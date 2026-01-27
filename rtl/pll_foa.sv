module pll_foa #(
    parameter DATA_WIDTH = 64,  // Input/output data width
    parameter COEFF_WIDTH = 27  // Coefficient width (fixed-point)
) (
    input  logic                   clk,
    input  logic                   rst_n,
    input  logic                   valid_in,
    input  logic signed [DATA_WIDTH-1:0] x_in,
    output logic                   valid_out,
    output logic signed [DATA_WIDTH-1:0] y_out
);

localparam signed [COEFF_WIDTH-1:0] c0 =  +32'sd4863;  // 0.0742 * 65536 ≈ 4863
localparam signed [COEFF_WIDTH-1:0] c1 =  -32'sd4024;  // -0.0614 * 65536 ≈ -4024
localparam signed [COEFF_WIDTH-1:0] c2 =  -32'sd4830;  // -0.0737 * 65536 ≈ -4830
localparam signed [COEFF_WIDTH-1:0] c3 =  +32'sd4063;  // 0.062 * 65536 ≈ 4063

// Y coefficients: 
localparam signed [COEFF_WIDTH-1:0] cy1 =  +32'sd179883;  // 2.7448 * 65536 ≈ 179883
localparam signed [COEFF_WIDTH-1:0] cy2 =  -32'sd164948;  // -2.5169 * 65536 ≈ -164948
localparam signed [COEFF_WIDTH-1:0] cy3 =  +32'sd50528;  // 0.771 * 65536 ≈ 50528

    // Delay lines for x and y
    logic signed [DATA_WIDTH-1:0] x_delay [0:2];
    logic signed [DATA_WIDTH-1:0] y_delay [0:2];

    // Intermediate product accumulators (wider to prevent overflow)
    // logic signed [(DATA_WIDTH+COEFF_WIDTH)-1:0] acc_x, acc_y;
    logic signed [DATA_WIDTH+COEFF_WIDTH:0] temp_sum;  // Extra bits for final scaling

    // Input valid pipeline

	always_comb begin
		// Feedforward: c0*x[n] + c1*x[n-1] + c2*x[n-2] + c3*x[n-3]
		// Feedback: cy1*y[n-1] + cy2*y[n-2] + cy3*y[n-3]
		// x_in and x_delay are Q16, coefficients are Q16
		// Feedforward: Q24 * Q24 = Q48, shift by 24 to get Q24
		// Feedback: Q24 * Q24 = Q48, shift by 24 to get Q24
		temp_sum = ((c0 * x_in)) + ((c1 * x_delay[0])) + ((c2 * x_delay[1])) + ((c3 * x_delay[2]))
				 + ((cy1 * y_delay[0]) >>> 16) + ((cy2 * y_delay[1]) >>> 16) + ((cy3 * y_delay[2]) >>> 16);
		y_out = temp_sum >>> 16;  // Output is Q16
	end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            x_delay[0] <= 0;
            x_delay[1] <= 0;
            x_delay[2] <= 0;
            y_delay[0] <= 0;
            y_delay[1] <= 0;
            y_delay[2] <= 0;
        end else begin
            // Shift x delays: x -> x_delay, x -> x_delay[1], etc.
            if (valid_in) begin
                x_delay[0] <= x_in;
                x_delay[1] <= x_delay[0];
                x_delay[2] <= x_delay[1];
            end

            // Compute y and shift y delays
            if (valid_in) begin
                // Shift y delays
                y_delay[0] <= temp_sum;
                y_delay[1] <= y_delay[0];
                y_delay[2] <= y_delay[1];
            end

        end
    end
	assign valid_out = valid_in;

endmodule
