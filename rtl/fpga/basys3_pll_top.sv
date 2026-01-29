// Simplified Basys 3 Top-Level Wrapper for PLL IIR Filter Testing
// Target: Xilinx Artix-7 (XC7A35T-1CPG236C)
module basys3_pll_top #(
    parameter DATA_WIDTH = 32,
    parameter COEFF_WIDTH = 32,
    parameter CLK_DIV = 1048576         // Clock divider: 100MHz / 4 = 25MHz for filter
) (
    input  logic        clk,       // 100 MHz oscillator
    input  logic        btnC,      // Center button - reset
    input  logic [15:0] sw,        // SW[0]: enable, SW[1]: toggle input value
    output logic [15:0] led,       // Status LEDs
    output logic [6:0]  seg,       // 7-seg (directly show lower bits)
    output logic        dp,
    output logic [3:0]  an
);

    // =========================================================================
    // Reset synchronizer (simple 2-FF synchronizer)
    // =========================================================================
    logic rst_n, rst_sync1, rst_sync2;

    always_ff @(posedge clk) begin
        rst_sync1 <= ~btnC;  // btnC is active-high, convert to active-low
        rst_sync2 <= rst_sync1;
    end
    assign rst_n = rst_sync2;

    // =========================================================================
    // Clock Divider for IIR Filter (reduces timing pressure)
    // =========================================================================
    logic [$clog2(CLK_DIV)-1:0] clk_div_cnt;
    logic clk_slow;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            clk_div_cnt <= '0;
            clk_slow <= 1'b0;
        end else begin
            if (clk_div_cnt == CLK_DIV - 1) begin
                clk_div_cnt <= '0;
                clk_slow <= ~clk_slow;
            end else begin
                clk_div_cnt <= clk_div_cnt + 1;
            end
        end
    end

    // =========================================================================
    // Simple Test Pattern Generator (runs on slow clock)
    // =========================================================================
    // Alternates between two fixed values on each clock when enabled
    logic signed [DATA_WIDTH-1:0] x_in;
    logic signed [DATA_WIDTH-1:0] y_out;
    logic valid_in;
    logic valid_out;
    logic toggle_state;

    // Synchronize sw[0] to slow clock domain
    logic sw0_sync1, sw0_sync2;
    always_ff @(posedge clk_slow or negedge rst_n) begin
        if (!rst_n) begin
            sw0_sync1 <= 1'b0;
            sw0_sync2 <= 1'b0;
        end else begin
            sw0_sync1 <= sw[0];
            sw0_sync2 <= sw0_sync1;
        end
    end

    // Input values (same as original testbench)
    localparam logic signed [DATA_WIDTH-1:0] VAL_A = 32'sd25;
    localparam logic signed [DATA_WIDTH-1:0] VAL_B = 32'sd50;
	localparam logic [31:0] input_period = 32'd0100;
	logic [31:0] input_counter;

    always_ff @(posedge clk_slow or negedge rst_n) begin
        if (!rst_n) begin
            toggle_state <= 1'b0;
			input_counter <= 32'd0;
        end else if (sw0_sync2) begin
			if (input_counter < input_period - 1) begin
				input_counter <= input_counter + 1;
			end else begin
				input_counter <= 32'd0;
				toggle_state <= ~toggle_state;
			end
        end
    end

    assign x_in = toggle_state ? VAL_B : VAL_A;
    assign valid_in = sw0_sync2;  // SW[0] enables filter input

    // =========================================================================
    // PLL IIR Filter (DUT) - runs on divided clock
    // =========================================================================
    pll_foa #(
        .DATA_WIDTH(DATA_WIDTH),
        .COEFF_WIDTH(COEFF_WIDTH)
    ) u_pll_foa (
        .clk(clk_slow),
        .rst_n(rst_n),
        .valid_in(valid_in),
        .x_in(x_in),
        .valid_out(valid_out),
        .y_out(y_out)
    );

    // =========================================================================
    // Simple LED Status
    // =========================================================================
    // LED[0]: Filter enabled (SW[0])
    // LED[1]: Valid output
    // LED[2]: Toggle state (shows alternating input)
    // LED[3]: Reset active (inverted)
    // LED[15:4]: Lower 12 bits of y_out

    assign led[0] = sw[0];
    assign led[1] = valid_out;
    assign led[2] = toggle_state;
    assign led[3] = ~rst_n;
    assign led[15:4] = y_out[11:0];

    // =========================================================================
    // Simple 7-Segment Display (directly show y_out bits)
    // =========================================================================
    // Display the integer part of y_out (bits [31:16])
    logic [15:0] display_val;
    assign display_val = {x_in[7:0], y_out[7:0]};  // Show lower 16 bits

    // Simple hex decoder for one digit
    function automatic logic [6:0] hex_to_seg(input logic [3:0] hex);
        case (hex)
            4'h0: return 7'b1000000;
            4'h1: return 7'b1111001;
            4'h2: return 7'b0100100;
            4'h3: return 7'b0110000;
            4'h4: return 7'b0011001;
            4'h5: return 7'b0010010;
            4'h6: return 7'b0000010;
            4'h7: return 7'b1111000;
            4'h8: return 7'b0000000;
            4'h9: return 7'b0010000;
            4'hA: return 7'b0001000;
            4'hB: return 7'b0000011;
            4'hC: return 7'b1000110;
            4'hD: return 7'b0100001;
            4'hE: return 7'b0000110;
            4'hF: return 7'b0001110;
            default: return 7'b1111111;
        endcase
    endfunction

    // Simple digit multiplexing counter
    logic [1:0] digit_sel;
    logic [17:0] refresh_counter;  // Reduced from 20 to 18 bits for faster refresh (~400 Hz)

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            refresh_counter <= '0;
            digit_sel <= '0;
        end else begin
            refresh_counter <= refresh_counter + 1;
            if (refresh_counter == 0)
                digit_sel <= digit_sel + 1;
        end
    end

    // Select digit and display (registered output to reduce glitches)
    logic [3:0] an_next;
    logic [6:0] seg_next;
    
    always_comb begin
        case (digit_sel)
            2'b00: begin an_next = 4'b1110; seg_next = hex_to_seg(display_val[3:0]);   end
            2'b01: begin an_next = 4'b1101; seg_next = hex_to_seg(display_val[7:4]);   end
            2'b10: begin an_next = 4'b1011; seg_next = hex_to_seg(display_val[11:8]);  end
            2'b11: begin an_next = 4'b0111; seg_next = hex_to_seg(display_val[15:12]); end
        endcase
    end
    
    // Register outputs to avoid glitches during transitions
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            an <= 4'b1111;
            seg <= 7'b1111111;
        end else begin
            an <= an_next;
            seg <= seg_next;
        end
    end

    assign dp = 1'b1;  // Decimal point off

endmodule
