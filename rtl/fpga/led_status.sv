// LED Status Module
// Maps system status to Basys 3 LEDs
module led_status #(
    parameter DATA_WIDTH = 64
) (
    input  logic                        clk,
    input  logic                        rst_n,
    input  logic                        filter_en,      // SW[0]
    input  logic                        valid_in,       // To filter
    input  logic                        valid_out,      // From filter
    input  logic signed [DATA_WIDTH-1:0] y_out,         // Filter output
    input  logic [3:0]                  amplitude_sel,  // SW[7:4]
    input  logic [2:0]                  freq_sel,       // SW[3:1]
    input  logic                        wave_state,     // Square wave state
    output logic [15:0]                 led             // LED outputs
);

    // Overflow detection - check if output exceeds expected range
    // For Q16 format, overflow if integer part is too large
    logic [3:0] overflow_indicator;
    logic signed [47:0] y_out_upper;

    always_comb begin
        y_out_upper = y_out[DATA_WIDTH-1:16];
        // Simple overflow check: if upper bits are all 1s or all 0s (sign extended), no overflow
        // Otherwise, potential overflow
        if (y_out[DATA_WIDTH-1]) begin
            // Negative number - check for proper sign extension
            overflow_indicator = (y_out_upper < -48'sd2147483648) ? 4'hF : 4'h0;
        end else begin
            // Positive number
            overflow_indicator = (y_out_upper > 48'sd2147483647) ? 4'hF : 4'h0;
        end
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            led <= 16'h0000;
        end else begin
            led[0]     <= filter_en;                     // Filter enabled
            led[1]     <= valid_in;                      // valid_in active
            led[2]     <= valid_out;                     // valid_out active
            led[3]     <= y_out[DATA_WIDTH-1];           // Output sign (1=negative)
            led[7:4]   <= amplitude_sel;                 // Amplitude indicator
            led[10:8]  <= freq_sel;                      // Frequency selection
            led[11]    <= wave_state;                    // Square wave state
            led[15:12] <= overflow_indicator;            // Overflow indicator
        end
    end

endmodule
