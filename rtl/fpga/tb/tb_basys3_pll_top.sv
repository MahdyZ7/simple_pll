// Testbench for Basys 3 PLL Top-Level Wrapper
`timescale 1ns / 1ps

module tb_basys3_pll_top;

    // Parameters - use much smaller clock dividers for simulation
    // With CLK_FREQ=10000 and 1kHz test frequency, divider = 10 cycles per tick
    localparam CLK_FREQ = 10_000;     // 10 kHz simulated clock frequency
    localparam CLK_PERIOD = 100;      // 100 ns period (10 MHz actual, but dividers think 10 kHz)
    localparam DATA_WIDTH = 64;

    // DUT Signals
    logic        clk;
    logic        btnC;
    logic [15:0] sw;
    logic [15:0] led;
    logic [6:0]  seg;
    logic        dp;
    logic [3:0]  an;

    // Instantiate DUT with faster clock for simulation
    basys3_pll_top #(
        .CLK_FREQ(CLK_FREQ),
        .DATA_WIDTH(DATA_WIDTH)
    ) dut (
        .clk(clk),
        .btnC(btnC),
        .sw(sw),
        .led(led),
        .seg(seg),
        .dp(dp),
        .an(an)
    );

    // Clock generation
    initial begin
        clk = 0;
        forever #(CLK_PERIOD/2) clk = ~clk;
    end

    // Helper task to wait for N clock cycles
    task automatic wait_cycles(input int n);
        repeat(n) @(posedge clk);
    endtask

    // Helper task to press reset button
    // With CLK_FREQ=10000 and DEBOUNCE_MS=20, need (10000/1000)*20 = 200 cycles per transition
    task automatic press_reset();
        btnC = 1;
        wait_cycles(500);  // Hold for debounce (200+ cycles needed)
        btnC = 0;
        wait_cycles(500);  // Wait for debounce to complete
        $display("  press_reset done: btn_debounced=%b, rst_n=%b", dut.btn_debounced, dut.rst_n);
    endtask

    // Helper function to decode 7-segment to hex
    function automatic logic [3:0] seg_to_hex(input logic [6:0] s);
        case (s)
            7'b1000000: return 4'h0;
            7'b1111001: return 4'h1;
            7'b0100100: return 4'h2;
            7'b0110000: return 4'h3;
            7'b0011001: return 4'h4;
            7'b0010010: return 4'h5;
            7'b0000010: return 4'h6;
            7'b1111000: return 4'h7;
            7'b0000000: return 4'h8;
            7'b0010000: return 4'h9;
            7'b0001000: return 4'hA;
            7'b0000011: return 4'hB;
            7'b1000110: return 4'hC;
            7'b0100001: return 4'hD;
            7'b0000110: return 4'hE;
            7'b0001110: return 4'hF;
            default:    return 4'hX;
        endcase
    endfunction

    // Main test sequence
    initial begin
        // Initialize signals
        btnC = 0;
        sw = 16'h0000;

        $display("========================================");
        $display("Basys 3 PLL Top-Level Testbench");
        $display("========================================");

        // Wait for initial setup
        wait_cycles(10);

        // Test 1: Reset
        $display("\n[Test 1] Reset Test");
        press_reset();
        $display("  Reset complete");
        $display("  LED status: %b", led);
        assert(led[0] == 0) else $error("LED[0] should be 0 (filter disabled)");

        // Test 2: Enable filter at 1kHz (fastest for simulation)
        $display("\n[Test 2] Enable filter with 1kHz square wave");
        sw[0] = 1;      // Enable filter
        sw[3:1] = 3'b111;  // 1 kHz frequency
        sw[7:4] = 4'h4;    // Amplitude = 25
        wait_cycles(50);
        $display("  Filter enabled, LED[0]: %b", led[0]);
        assert(led[0] == 1) else $error("LED[0] should be 1 (filter enabled)");
        $display("  Amplitude LEDs [7:4]: %b", led[7:4]);
        $display("  Frequency LEDs [10:8]: %b", led[10:8]);

        // Test 3: Wait for square wave cycles and observe output
        $display("\n[Test 3] Observe filter response");
        $display("  rst_n=%b, test_div=%0d", dut.rst_n, dut.u_clk_divider.test_div);
        repeat(20) begin
            // Wait for tick_test with timeout
            fork
                begin
                    @(posedge dut.tick_test);
                end
                begin
                    wait_cycles(100);
                    $display("  WARNING: tick timeout, rst_n=%b, test_cnt=%0d",
                             dut.rst_n, dut.u_clk_divider.test_cnt);
                end
            join_any
            disable fork;
            $display("  tick: wave_state=%b, x_in=%0d, y_out=%0d, valid_out=%b",
                     dut.wave_state,
                     $signed(dut.x_in) >>> 16,
                     $signed(dut.y_out) >>> 16,
                     dut.valid_out);
        end

        // Test 4: Change amplitude
        $display("\n[Test 4] Change amplitude to 100");
        sw[7:4] = 4'h6;  // Amplitude = 100
        repeat(10) begin
            @(posedge dut.tick_test);
            $display("  x_in=%0d, y_out=%0d",
                     $signed(dut.x_in) >>> 16,
                     $signed(dut.y_out) >>> 16);
        end

        // Test 5: Test display slice selection
        $display("\n[Test 5] Test display slice selection");
        sw[11:9] = 3'b000;  // LSB
        wait_cycles(100);
        $display("  Slice 0 (LSB): display_value=0x%04h", dut.display_value);

        sw[11:9] = 3'b010;  // Integer LSB
        wait_cycles(100);
        $display("  Slice 2 (Int LSB): display_value=0x%04h", dut.display_value);

        sw[11:9] = 3'b011;  // MSB/Sign
        wait_cycles(100);
        $display("  Slice 3 (MSB): display_value=0x%04h", dut.display_value);

        // Test 6: Display mode toggle (input vs output)
        $display("\n[Test 6] Display mode toggle");
        sw[12] = 0;  // Show output
        wait_cycles(50);
        $display("  Output mode: display_value=0x%04h", dut.display_value);

        sw[12] = 1;  // Show input
        wait_cycles(50);
        $display("  Input mode: display_value=0x%04h", dut.display_value);

        // Test 7: Disable filter
        $display("\n[Test 7] Disable filter");
        sw[0] = 0;
        wait_cycles(100);
        $display("  Filter disabled, LED[0]: %b, valid_in: %b", led[0], dut.valid_in);
        assert(led[0] == 0) else $error("LED[0] should be 0 (filter disabled)");

        // Test 8: 7-segment display multiplexing
        $display("\n[Test 8] Seven-segment display multiplexing");
        sw[0] = 1;  // Re-enable
        sw[12] = 0; // Show output
        sw[11:9] = 3'b010;  // Integer portion
        repeat(8) begin
            @(posedge dut.clk_display);
            wait_cycles(2);  // Let registers update
            $display("  an=%b, seg=%b (hex=%h), dp=%b",
                     an, seg, seg_to_hex(seg), dp);
        end

        // Test 9: Different frequencies
        $display("\n[Test 9] Test different frequencies");
        sw[3:1] = 3'b000;  // 1 Hz (will be slow in simulation)
        wait_cycles(100);
        $display("  1 Hz selected, freq_sel LEDs: %b", led[10:8]);

        sw[3:1] = 3'b100;  // 50 Hz
        wait_cycles(100);
        $display("  50 Hz selected, freq_sel LEDs: %b", led[10:8]);

        // Test 10: Reset during operation
        $display("\n[Test 10] Reset during operation");
        press_reset();
        $display("  After reset: y_out=%0d, valid_out=%b",
                 $signed(dut.y_out), dut.valid_out);

        $display("\n========================================");
        $display("All tests completed!");
        $display("========================================");

        #1000;
        $finish;
    end

    // Waveform dump for GTKWave
    initial begin
        $dumpfile("tb_basys3_pll_top.vcd");
        $dumpvars(0, tb_basys3_pll_top);
    end

    // Timeout watchdog
    initial begin
        #100_000_000;
        $display("ERROR: Simulation timeout!");
        $finish;
    end

endmodule
