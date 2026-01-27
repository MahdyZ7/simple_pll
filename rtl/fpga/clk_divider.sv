// Clock Divider Module for Basys 3
// Generates variable frequency ticks for square wave and display refresh
module clk_divider #(
    parameter CLK_FREQ = 100_000_000  // 100 MHz input clock
) (
    input  logic        clk,
    input  logic        rst_n,
    input  logic [2:0]  freq_sel,      // Frequency selection
    output logic        tick_test,     // Tick for square wave generation
    output logic        clk_display    // ~1 kHz pulse for 7-seg refresh
);

    // Display refresh counter (1 kHz = 100,000 cycles at 100 MHz)
    localparam DISPLAY_DIV = CLK_FREQ / 1000;
    logic [$clog2(DISPLAY_DIV)-1:0] display_cnt;

    // Frequency divider values for test pattern
    // freq_sel: 000=1Hz, 001=2Hz, 010=5Hz, 011=10Hz, 100=50Hz, 101=100Hz, 110=500Hz, 111=1kHz
    function automatic int get_divider(input logic [2:0] sel);
        case (sel)
            3'b000:  return CLK_FREQ / 1;       // 1 Hz
            3'b001:  return CLK_FREQ / 2;       // 2 Hz
            3'b010:  return CLK_FREQ / 5;       // 5 Hz
            3'b011:  return CLK_FREQ / 10;      // 10 Hz
            3'b100:  return CLK_FREQ / 50;      // 50 Hz
            3'b101:  return CLK_FREQ / 100;     // 100 Hz
            3'b110:  return CLK_FREQ / 500;     // 500 Hz
            3'b111:  return CLK_FREQ / 1000;    // 1 kHz
            default: return CLK_FREQ / 1;
        endcase
    endfunction

    // Test tick counter
    logic [26:0] test_cnt;
    logic [26:0] test_div;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            test_div <= get_divider(3'b000);
        end else begin
            test_div <= get_divider(freq_sel);
        end
    end

    // Display refresh divider
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            display_cnt <= '0;
            clk_display <= 1'b0;
        end else begin
            if (display_cnt >= DISPLAY_DIV - 1) begin
                display_cnt <= '0;
                clk_display <= 1'b1;
            end else begin
                display_cnt <= display_cnt + 1;
                clk_display <= 1'b0;
            end
        end
    end

    // Test tick divider
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            test_cnt <= '0;
            tick_test <= 1'b0;
        end else begin
            if (test_cnt >= test_div - 1) begin
                test_cnt <= '0;
                tick_test <= 1'b1;
            end else begin
                test_cnt <= test_cnt + 1;
                tick_test <= 1'b0;
            end
        end
    end

endmodule
