// Button Debouncer Module
// Filters out mechanical bounce from button presses
module debounce #(
    parameter CLK_FREQ = 100_000_000,  // 100 MHz
    parameter DEBOUNCE_MS = 20         // Debounce time in milliseconds
) (
    input  logic clk,
    input  logic rst_n,
    input  logic btn_in,      // Raw button input (active high)
    output logic btn_out,     // Debounced output (active high)
    output logic btn_pulse    // Single pulse on button press
);

    localparam DEBOUNCE_CYCLES = (CLK_FREQ / 1000) * DEBOUNCE_MS;
    localparam CNT_WIDTH = $clog2(DEBOUNCE_CYCLES + 1);

    logic [CNT_WIDTH-1:0] counter;
    logic btn_sync_0, btn_sync_1;
    logic btn_stable;
    logic btn_prev;

    // Synchronizer to avoid metastability
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            btn_sync_0 <= 1'b0;
            btn_sync_1 <= 1'b0;
        end else begin
            btn_sync_0 <= btn_in;
            btn_sync_1 <= btn_sync_0;
        end
    end

    // Debounce counter
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            counter <= '0;
            btn_stable <= 1'b0;
        end else begin
            if (btn_sync_1 != btn_stable) begin
                // Button changed, start counting
                if (counter >= DEBOUNCE_CYCLES - 1) begin
                    counter <= '0;
                    btn_stable <= btn_sync_1;
                end else begin
                    counter <= counter + 1;
                end
            end else begin
                counter <= '0;
            end
        end
    end

    // Output and edge detection
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            btn_out <= 1'b0;
            btn_prev <= 1'b0;
            btn_pulse <= 1'b0;
        end else begin
            btn_out <= btn_stable;
            btn_prev <= btn_stable;
            btn_pulse <= btn_stable & ~btn_prev;  // Rising edge detection
        end
    end

endmodule
