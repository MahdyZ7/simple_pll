//-----------------------------------------------------------------------------
// IIR Time Difference Filter
// Equation: y[n] = 0.0704*x[n-0] - 0.0692*x[n-1] - 0.0704*x[n-2] + 0.0692*x[n-3]
//                + 2.8482*y[n-1] - 2.6990*y[n-2] + 0.8508*y[n-3]
//
// Fixed-Point Format: Q4.28 (4 integer bits, 28 fractional bits)
// This provides sufficient precision for the coefficients while allowing
// for the accumulation range needed by the feedback terms.
//-----------------------------------------------------------------------------

module iir_time_diff_filter #(
    parameter DATA_WIDTH = 32,          // Input/output data width
    parameter COEFF_WIDTH = 32,         // Coefficient width
    parameter FRAC_BITS = 16,           // Fractional bits for fixed-point
    parameter ACCUM_WIDTH = 64          // Accumulator width to prevent overflow
)(
    input  logic                        clk,
    input  logic                        rst_n,
    input  logic                        valid_in,             // Enable/valid input
    input  logic signed [DATA_WIDTH-1:0] x_in,          // Input sample
    output logic signed [DATA_WIDTH-1:0] y_out,         // Output sample
    output logic                        valid_out       // Output valid
);

    //-------------------------------------------------------------------------
    // Fixed-Point Coefficients (Q16.16 format)
    // To convert: coefficient * 2^16
    //-------------------------------------------------------------------------
    // Feedforward coefficients (b0, b1, b2, b3)
    localparam logic signed [COEFF_WIDTH-1:0] B0 =  32'sd2307;   //  0.0704 * 2^16
    localparam logic signed [COEFF_WIDTH-1:0] B1 = -32'sd2268;   // -0.0692 * 2^16
    localparam logic signed [COEFF_WIDTH-1:0] B2 = -32'sd2307;   // -0.0704 * 2^16
    localparam logic signed [COEFF_WIDTH-1:0] B3 =  32'sd2268;   //  0.0692 * 2^16
    
    // Feedback coefficients (a1, a2, a3) - note: negated for direct use
    // In the equation: y[n] = ... + a1*y[n-1] + a2*y[n-2] + a3*y[n-3]
    localparam logic signed [COEFF_WIDTH-1:0] A1 =  32'sd93330;  //  2.8482 * 2^16
    localparam logic signed [COEFF_WIDTH-1:0] A2 = -32'sd88440;  // -2.6990 * 2^16
    localparam logic signed [COEFF_WIDTH-1:0] A3 =  32'sd27879;  //  0.8508 * 2^16

    //-------------------------------------------------------------------------
    // Delay Line Registers
    //-------------------------------------------------------------------------
    logic signed [DATA_WIDTH-1:0] x_delay [0:3];    // x[n], x[n-1], x[n-2], x[n-3]
    logic signed [DATA_WIDTH-1:0] y_delay [0:2];    // y[n-1], y[n-2], y[n-3]
    
    //-------------------------------------------------------------------------
    // Intermediate Products and Accumulator
    //-------------------------------------------------------------------------
    logic signed [ACCUM_WIDTH-1:0] prod_b0, prod_b1, prod_b2, prod_b3;
    logic signed [ACCUM_WIDTH-1:0] prod_a1, prod_a2, prod_a3;
    logic signed [ACCUM_WIDTH-1:0] sum_ff, sum_fb, sum_total;
    logic signed [DATA_WIDTH-1:0]  y_result;
    
    //-------------------------------------------------------------------------
    // Pipeline Registers
    //-------------------------------------------------------------------------
    logic valid_pipe [0:2];
    
    //-------------------------------------------------------------------------
    // Stage 1: Update Delay Lines and Compute Products
    //-------------------------------------------------------------------------
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            // Reset delay lines
            for (int i = 0; i < 4; i++) x_delay[i] <= '0;
            for (int i = 0; i < 3; i++) y_delay[i] <= '0;
            
            // Reset products
            prod_b0 <= '0;
            prod_b1 <= '0;
            prod_b2 <= '0;
            prod_b3 <= '0;
            prod_a1 <= '0;
            prod_a2 <= '0;
            prod_a3 <= '0;
            
            valid_pipe[0] <= 1'b0;
        end else if (valid_in) begin
            // Shift delay lines
            x_delay[0] <= x_in;
            x_delay[1] <= x_delay[0];
            x_delay[2] <= x_delay[1];
            x_delay[3] <= x_delay[2];
            
            // Compute feedforward products
            prod_b0 <= $signed(x_in)       * $signed(B0);
            prod_b1 <= $signed(x_delay[0]) * $signed(B1);
            prod_b2 <= $signed(x_delay[1]) * $signed(B2);
            prod_b3 <= $signed(x_delay[2]) * $signed(B3);
            
            // Compute feedback products
            prod_a1 <= $signed(y_delay[0]) * $signed(A1);
            prod_a2 <= $signed(y_delay[1]) * $signed(A2);
            prod_a3 <= $signed(y_delay[2]) * $signed(A3);
            
            valid_pipe[0] <= 1'b1;
        end else begin
            valid_pipe[0] <= 1'b0;
        end
    end
    
    //-------------------------------------------------------------------------
    // Stage 2: Sum Products
    //-------------------------------------------------------------------------
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sum_ff <= '0;
            sum_fb <= '0;
            valid_pipe[1] <= 1'b0;
        end else begin
            // Sum feedforward terms
            sum_ff <= prod_b0 + prod_b1 + prod_b2 + prod_b3;
            
            // Sum feedback terms
            sum_fb <= prod_a1 + prod_a2 + prod_a3;
            
            valid_pipe[1] <= valid_pipe[0];
        end
    end
    
    //-------------------------------------------------------------------------
    // Stage 3: Final Sum, Scaling, and Output
    //-------------------------------------------------------------------------
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sum_total <= '0;
            y_result <= '0;
            valid_pipe[2] <= 1'b0;
        end else begin
            // Total sum
            sum_total <= sum_ff + sum_fb;
            
            // Scale back from Q4.28 (right shift by FRAC_BITS with rounding)
            y_result <= (sum_total + (1 << (FRAC_BITS-1))) >>> FRAC_BITS;
            
            valid_pipe[2] <= valid_pipe[1];
        end
    end
    
    //-------------------------------------------------------------------------
    // Update Output Delay Line
    //-------------------------------------------------------------------------
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            y_delay[0] <= '0;
            y_delay[1] <= '0;
            y_delay[2] <= '0;
            y_out <= '0;
            valid_out <= 1'b0;
        end else if (valid_pipe[2]) begin
            // Update feedback delay line
            y_delay[0] <= y_result;
            y_delay[1] <= y_delay[0];
            y_delay[2] <= y_delay[1];
            
            // Output
            y_out <= y_result;
            valid_out <= 1'b1;
        end else begin
            valid_out <= 1'b0;
        end
    end

endmodule


//-----------------------------------------------------------------------------
// Alternative: Single-Cycle Implementation (Higher Resource Usage)
// Use this if latency is critical and you have sufficient DSP resources
//-----------------------------------------------------------------------------
module iir_time_diff_filter_single_cycle #(
    parameter DATA_WIDTH = 32,
    parameter COEFF_WIDTH = 32,
    parameter FRAC_BITS = 16,
    parameter ACCUM_WIDTH = 64
)(
    input  logic                        clk,
    input  logic                        rst_n,
    input  logic                        valid_in,
    input  logic signed [DATA_WIDTH-1:0] x_in,
    output logic signed [DATA_WIDTH-1:0] y_out,
    output logic                        valid_out
);

    // Coefficients (Q16.16)
    localparam logic signed [COEFF_WIDTH-1:0] B0 =  32'sd2307;   //  0.0704 * 2^16
    localparam logic signed [COEFF_WIDTH-1:0] B1 = -32'sd2268;   // -0.0692 * 2^16
    localparam logic signed [COEFF_WIDTH-1:0] B2 = -32'sd2307;   // -0.0704 * 2^16
    localparam logic signed [COEFF_WIDTH-1:0] B3 =  32'sd2268;   //  0.0692 * 2^16
    localparam logic signed [COEFF_WIDTH-1:0] A1 =  32'sd93330;  //  2.8482 * 2^16
    localparam logic signed [COEFF_WIDTH-1:0] A2 = -32'sd88440;  // -2.6990 * 2^16
    localparam logic signed [COEFF_WIDTH-1:0] A3 =  32'sd27879;  //  0.8508 * 2^16

    // Delay lines
    logic signed [DATA_WIDTH-1:0] x_d1, x_d2, x_d3;
    logic signed [DATA_WIDTH-1:0] y_d1, y_d2, y_d3;
    
    // Combinational calculation
    logic signed [ACCUM_WIDTH-1:0] accum;
    logic signed [DATA_WIDTH-1:0]  y_next;
    
    // Combinational path
    always_comb begin
        accum = ($signed(x_in) * $signed(B0)) +
                ($signed(x_d1) * $signed(B1)) +
                ($signed(x_d2) * $signed(B2)) +
                ($signed(x_d3) * $signed(B3)) +
                ($signed(y_d1) * $signed(A1)) +
                ($signed(y_d2) * $signed(A2)) +
                ($signed(y_d3) * $signed(A3));
        
        // Round and scale
        y_next = (accum + (1 << (FRAC_BITS-1))) >>> FRAC_BITS;
    end
    
    // Sequential logic
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            x_d1 <= '0;
            x_d2 <= '0;
            x_d3 <= '0;
            y_d1 <= '0;
            y_d2 <= '0;
            y_d3 <= '0;
            y_out <= '0;
            valid_out <= 1'b0;
        end else if (valid_in) begin
            // Update x delay line
            x_d1 <= x_in;
            x_d2 <= x_d1;
            x_d3 <= x_d2;
            
            // Update y delay line and output
            y_d1 <= y_next;
            y_d2 <= y_d1;
            y_d3 <= y_d2;
            
            y_out <= y_next;
            valid_out <= 1'b1;
        end else begin
            valid_out <= 1'b0;
        end
    end

endmodule