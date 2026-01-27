// Seven Segment Controller Module
// Multiplexed 4-digit hex display driver for Basys 3
// Active-low segments and anodes
module seven_seg_controller (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        refresh_tick,   // ~1 kHz refresh pulse
    input  logic [15:0] display_value,  // 16-bit hex value to display
    input  logic        show_negative,  // Display decimal point on digit 3
    output logic [6:0]  seg,            // Segment outputs (active low)
    output logic        dp,             // Decimal point (active low)
    output logic [3:0]  an              // Anode outputs (active low)
);

    // Digit counter (0-3)
    logic [1:0] digit_sel;

    // Current nibble to display
    logic [3:0] current_nibble;

    // Hex to 7-segment decoder (active low output)
    function automatic logic [6:0] hex_to_seg(input logic [3:0] hex);
        // Segment order: seg[6:0] = {g, f, e, d, c, b, a}
        case (hex)
            4'h0: return 7'b1000000;  // 0
            4'h1: return 7'b1111001;  // 1
            4'h2: return 7'b0100100;  // 2
            4'h3: return 7'b0110000;  // 3
            4'h4: return 7'b0011001;  // 4
            4'h5: return 7'b0010010;  // 5
            4'h6: return 7'b0000010;  // 6
            4'h7: return 7'b1111000;  // 7
            4'h8: return 7'b0000000;  // 8
            4'h9: return 7'b0010000;  // 9
            4'hA: return 7'b0001000;  // A
            4'hB: return 7'b0000011;  // b
            4'hC: return 7'b1000110;  // C
            4'hD: return 7'b0100001;  // d
            4'hE: return 7'b0000110;  // E
            4'hF: return 7'b0001110;  // F
            default: return 7'b1111111;  // All off
        endcase
    endfunction

    // Cycle through digits on each refresh tick
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            digit_sel <= 2'b00;
        end else if (refresh_tick) begin
            digit_sel <= digit_sel + 1;
        end
    end

    // Select nibble based on current digit
    always_comb begin
        case (digit_sel)
            2'b00: current_nibble = display_value[3:0];   // Rightmost digit
            2'b01: current_nibble = display_value[7:4];
            2'b10: current_nibble = display_value[11:8];
            2'b11: current_nibble = display_value[15:12]; // Leftmost digit
            default: current_nibble = 4'h0;
        endcase
    end

    // Generate segment pattern
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            seg <= 7'b1111111;  // All off
        end else begin
            seg <= hex_to_seg(current_nibble);
        end
    end

    // Generate anode pattern (one-hot, active low)
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            an <= 4'b1111;  // All off
        end else begin
            case (digit_sel)
                2'b00: an <= 4'b1110;  // Rightmost digit active
                2'b01: an <= 4'b1101;
                2'b10: an <= 4'b1011;
                2'b11: an <= 4'b0111;  // Leftmost digit active
                default: an <= 4'b1111;
            endcase
        end
    end

    // Decimal point - show on leftmost digit if negative
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            dp <= 1'b1;  // Off
        end else begin
            dp <= ~(show_negative && (digit_sel == 2'b11));
        end
    end

endmodule
