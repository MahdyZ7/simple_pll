// Clock Divider Module for Basys 3
// Generates variable frequency ticks for square wave and display refresh
module clk_divider #(
    parameter CLK_FREQ = 100_000_000,  // 100 MHz input clock
	parameter real JITTER_VARIANCE = 10.0   // Jitter variance in time units²
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

	// jittered clock generation for testing
	// Gaussian random generator using Box-Muller transform
	function automatic real gaussian_rand(real mean, real stddev);                                                                                  
		real u1, u2, z0;                                                                                                                            
		u1 = $urandom() / 4294967296.0;  // Uniform [0,1)                                                                                           
		u2 = $urandom() / 4294967296.0;                                                                                                             
		if (u1 < 1e-10) u1 = 1e-10;      // Avoid log(0)                                                                                            
		z0 = $sqrt(-2.0 * $ln(u1)) * $cos(2.0 * 3.14159265 * u2);                                                                                   
		return mean + stddev * z0;                                                                                                                  
	endfunction                                                                                                            

	// jittered clock output
	logic [27:0] jittered_target;
	logic [27:0] jittered_cnt;
	real jitter_delay;
	assign jittered_target = slow_div;
	always_ff @(posedge clk or negedge rst_n) begin
		if (!rst_n) begin
			jittered_cnt <= '0;
			clk_slow_jittered <= 1'b0;
			// jittered_target <= slow_div;
		end else begin
			if (jittered_cnt >= jittered_target - 1 + $rtoi( gaussian_rand(0.0, $sqrt(JITTER_VARIANCE)))) begin
				jittered_cnt <= '0;
				clk_slow_jittered <= ~clk_slow_jittered;
				// calculate new jittered target
				// jitter_delay =  gaussian_rand(0.0, $sqrt(JITTER_VARIANCE));
				// if (jitter_delay < - (slow_div / 2.0)) begin
				// 	jitter_delay = - (slow_div / 2.0);
				// end else if (jitter_delay > (slow_div / 2.0)) begin
				// 	jitter_delay = (slow_div / 2.0);
				// end
				// jittered_target <= slow_div ;//+ $rtoi(jitter_delay);
			end else begin
				jittered_cnt <= jittered_cnt + 1;
			end
		end
	end

endmodule
