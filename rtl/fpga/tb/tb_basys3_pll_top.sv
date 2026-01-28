// Simplified Testbench for Basys 3 PLL Top-Level Wrapper
`timescale 1ns / 1ps

module tb_basys3_pll_top;

    localparam CLK_PERIOD = 10;  // 100 MHz

    // DUT Signals
    logic        clk;
    logic        btnC;
    logic [15:0] sw;
    logic [15:0] led;
    logic [6:0]  seg;
    logic        dp;
    logic [3:0]  an;

    // Instantiate DUT
    basys3_pll_top dut (
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

    // Main test sequence
    initial begin
        // Initialize
        btnC = 1;  // Start in reset
        sw = 16'h0000;

        $display("=== Simplified Basys 3 PLL Testbench ===");

        // Release reset after a few cycles
        repeat(10) @(posedge clk);
        btnC = 0;
        repeat(5) @(posedge clk);
        $display("Reset released, rst_n=%b", dut.rst_n);

        // Enable filter
        $display("\nEnabling filter (SW[0]=1)");
        sw[0] = 1;

        // Run for several cycles and observe output
        repeat(20) begin
            @(posedge clk);
            $display("  x_in=%0d, y_out=%0d, valid=%b, toggle=%b",
                     $signed(dut.x_in) >>> 24,
                     $signed(dut.y_out) >>> 24,
                     dut.valid_out,
                     dut.toggle_state);
        end

        // Disable filter
        $display("\nDisabling filter (SW[0]=0)");
        sw[0] = 0;
        repeat(5) @(posedge clk);
        $display("  valid_in=%b, valid_out=%b", dut.valid_in, dut.valid_out);

        // Re-enable and observe more
        $display("\nRe-enabling filter");
        sw[0] = 1;
        repeat(10) begin
            @(posedge clk);
            $display("  y_out=%0d", $signed(dut.y_out) >>> 24);
        end

        $display("\n=== Test Complete ===");
        #100;
        $finish;
    end

    // Waveform dump
    initial begin
        $dumpfile("tb_basys3_pll_top.vcd");
        $dumpvars(0, tb_basys3_pll_top);
    end

    // Timeout
    initial begin
        #100_000;
        $display("Timeout!");
        $finish;
    end

endmodule
