// Square Wave Generator Module
// Generates alternating +/- amplitude values in Q16 format
module square_wave_gen #(
    parameter DATA_WIDTH = 64
) (
    input  logic                        clk,
    input  logic                        rst_n,
    input  logic                        tick,          // Toggle trigger
    input  logic [3:0]                  amplitude_sel, // Amplitude selection
    output logic signed [DATA_WIDTH-1:0] wave_out,     // Q16 output
    output logic                        wave_state     // Current state (high/low)
);

    // Amplitude lookup table (integer values, will be shifted to Q16)
    // Provides a range of test amplitudes from small to large
    function automatic logic signed [31:0] get_amplitude(input logic [3:0] sel);
        case (sel)
            4'h0:  return 32'sd1;       // 1
            4'h1:  return 32'sd2;       // 2
            4'h2:  return 32'sd5;       // 5
            4'h3:  return 32'sd10;      // 10
            4'h4:  return 32'sd25;      // 25
            4'h5:  return 32'sd50;      // 50
            4'h6:  return 32'sd100;     // 100
            4'h7:  return 32'sd250;     // 250
            4'h8:  return 32'sd500;     // 500
            4'h9:  return 32'sd1000;    // 1000
            4'hA:  return 32'sd2500;    // 2500
            4'hB:  return 32'sd5000;    // 5000
            4'hC:  return 32'sd10000;   // 10000
            4'hD:  return 32'sd25000;   // 25000
            4'hE:  return 32'sd50000;   // 50000
            4'hF:  return 32'sd100000;  // 100000
            default: return 32'sd25;
        endcase
    endfunction

    logic signed [31:0] amplitude_int;
    logic signed [DATA_WIDTH-1:0] amplitude_q16;

    // Convert integer amplitude to Q16 (shift left by 16)
    always_comb begin
        amplitude_int = get_amplitude(amplitude_sel);
        amplitude_q16 = {{16{amplitude_int[31]}}, amplitude_int, 16'b0};
    end

    // Toggle wave state on each tick
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wave_state <= 1'b0;
        end else if (tick) begin
            wave_state <= ~wave_state;
        end
    end

    // Output positive or negative amplitude based on state
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wave_out <= '0;
        end else begin
            wave_out <= wave_state ? amplitude_q16 : -amplitude_q16;
        end
    end

endmodule
