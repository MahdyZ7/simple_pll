// Clock Divider Module for Basys 3
// Generates variable frequency ticks for square wave and display refresh
module clk_divider #(
    parameter CLK_FREQ = 100_000_000,  // 100 MHz input clock
	parameter int JITTER_BITS = 6      // Jitter magnitude in bits (±2^JITTER_BITS cycles)
) (
    input  logic        clk,
    input  logic        rst_n,
    input  logic [2:0]  freq_sel,		// Frequency selection
    output logic        clk_slow,		// Output clock
	output logic		clk_slow_jittered // Jittered output clock
);
    // Frequency divider values for test pattern
    function automatic int get_divider(input logic [2:0] sel);
        case (sel)
            3'b000:  return CLK_FREQ / 1;			// 1 Hz
            3'b001:  return CLK_FREQ / 100;			// 100 Hz
            3'b010:  return CLK_FREQ / 1_000;		// 1 kHz
            3'b011:  return CLK_FREQ / 10_000;		// 10 kHz
            3'b100:  return CLK_FREQ / 100_000;		// 100 kHz
            3'b101:  return CLK_FREQ / 1_000_000;	// 1 MHz
            3'b110:  return CLK_FREQ / 10_000_000;	// 10 MHz
            3'b111:  return CLK_FREQ / 100_000_000;	// 100 MHz
            default: return CLK_FREQ / 1;
        endcase
    endfunction

    // Slow clock counter
    logic [27:0] slow_cnt;
    logic [27:0] slow_div;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            slow_div <= get_divider(3'b000);
        end else begin
            slow_div <= get_divider(freq_sel);
        end
    end

    // Slow clock divider
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            slow_cnt <= '0;
            clk_slow <= 1'b0;
        end else begin
            if (slow_cnt >= slow_div - 1) begin
                slow_cnt <= '0;
                clk_slow <= ~clk_slow;
            end else begin
                slow_cnt <= slow_cnt + 1;
            end
        end
    end

	// =========================================================================
	// LFSR-based pseudo-random jitter generation (synthesizable)
	// =========================================================================

	// 16-bit LFSR with maximal-length polynomial: x^16 + x^14 + x^13 + x^11 + 1
	logic [15:0] lfsr;

	always_ff @(posedge clk or negedge rst_n) begin
		if (!rst_n)
			lfsr <= 16'hACE1;  // Non-zero seed required
		else
			lfsr <= {lfsr[14:0], lfsr[15] ^ lfsr[13] ^ lfsr[12] ^ lfsr[10]};
	end

	// Extract signed jitter offset from LFSR bits
	// Range: -(2^JITTER_BITS) to +(2^JITTER_BITS - 1)
	logic signed [JITTER_BITS:0] jitter_offset;
	assign jitter_offset = lfsr[JITTER_BITS:0];

	// Jittered clock output
	logic [27:0] jittered_cnt;
	logic [27:0] jittered_target;

	// Compute jittered target, clamping to valid range
	always_comb begin
		if (slow_div > (1 << JITTER_BITS))
			jittered_target = slow_div + {{(28-JITTER_BITS-1){jitter_offset[JITTER_BITS]}}, jitter_offset};
		else
			jittered_target = slow_div;  // No jitter if divider too small
	end

	always_ff @(posedge clk or negedge rst_n) begin
		if (!rst_n) begin
			jittered_cnt <= '0;
			clk_slow_jittered <= 1'b0;
		end else begin
			if (jittered_cnt >= jittered_target - 1) begin
				jittered_cnt <= '0;
				clk_slow_jittered <= ~clk_slow_jittered;
			end else begin
				jittered_cnt <= jittered_cnt + 1;
			end
		end
	end

endmodule
