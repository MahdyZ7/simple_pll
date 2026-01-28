// Basys 3 Top-Level Wrapper for PLL IIR Filter Testing
// Target: Xilinx Artix-7 (XC7A35T-1CPG236C)
module basys3_pll_top #(
    parameter CLK_FREQ = 100_000_000,  // 100 MHz Basys 3 clock
    parameter DATA_WIDTH = 32,
    parameter COEFF_WIDTH = 32
) (
    // Clock and Reset
    input  logic        clk,           // 100 MHz oscillator
    input  logic        btnC,          // Center button (active high) - system reset

    // Switches
    input  logic [15:0] sw,

    // LEDs
    output logic [15:0] led,

    // Seven Segment Display
    output logic [6:0]  seg,           // Segments a-g (active low)
    output logic        dp,            // Decimal point (active low)
    output logic [3:0]  an             // Anodes (active low)
);

    // =========================================================================
    // Switch Assignments
    // =========================================================================
    // SW[0]     : Filter enable (gates valid_in)
    // SW[3:1]   : Frequency select (000=1Hz to 111=1kHz)
    // SW[7:4]   : Amplitude select (16 levels)
    // SW[8]     : Input source (0=internal, 1=reserved)
    // SW[11:9]  : Display slice select (which 16 bits of 64-bit output)
    // SW[12]    : Display mode (0=output y_out, 1=input x_in)
    // SW[15:13] : Reserved

    logic        filter_en;
    logic [2:0]  freq_sel;
    logic [3:0]  amplitude_sel;
    logic        input_source;
    logic [2:0]  display_slice;
    logic        display_mode;

    assign filter_en     = sw[0];
    assign freq_sel      = sw[3:1];
    assign amplitude_sel = sw[7:4];
    assign input_source  = sw[8];
    assign display_slice = sw[11:9];
    assign display_mode  = sw[12];

    // =========================================================================
    // Internal Signals
    // =========================================================================
    logic rst_n;                           // Active-low reset (from debounced button)
    logic rst_pulse;                       // Reset pulse (unused but available)
    logic tick_test;                       // Test pattern tick
    logic clk_display;                     // Display refresh tick

    logic signed [DATA_WIDTH-1:0] x_in;    // Filter input
    logic signed [DATA_WIDTH-1:0] y_out;   // Filter output
    logic valid_in;                        // Filter input valid
    logic valid_out;                       // Filter output valid

    logic signed [DATA_WIDTH-1:0] wave_out; // Square wave generator output
    logic wave_state;                       // Square wave high/low state

    logic [15:0] display_value;            // Value to show on 7-seg
    logic        show_negative;            // Show negative indicator

    // =========================================================================
    // Power-On Reset Generator
    // =========================================================================
    // Generate a brief reset pulse at power-on for simulation compatibility
    logic [7:0] por_counter = 8'hFF;  // Initialize to max for POR
    logic por_rst_n;

    always_ff @(posedge clk) begin
        if (por_counter > 0)
            por_counter <= por_counter - 1;
    end

    assign por_rst_n = (por_counter == 0);

    // =========================================================================
    // Reset Debouncer
    // =========================================================================
    // btnC is active-high on Basys 3, convert to active-low rst_n
    logic btn_debounced;

    debounce #(
        .CLK_FREQ(CLK_FREQ),
        .DEBOUNCE_MS(20)
    ) u_debounce (
        .clk(clk),
        .rst_n(por_rst_n),         // Use POR to initialize debouncer
        .btn_in(btnC),
        .btn_out(btn_debounced),
        .btn_pulse(rst_pulse)
    );

    assign rst_n = por_rst_n & ~btn_debounced;

    // =========================================================================
    // Clock Divider
    // =========================================================================
    clk_divider #(
        .CLK_FREQ(CLK_FREQ)
    ) u_clk_divider (
        .clk(clk),
        .rst_n(rst_n),
        .freq_sel(freq_sel),
        .tick_test(tick_test),
        .clk_display(clk_display)
    );

    // =========================================================================
    // Square Wave Generator
    // =========================================================================
    square_wave_gen #(
        .DATA_WIDTH(DATA_WIDTH)
    ) u_square_wave_gen (
        .clk(clk),
        .rst_n(rst_n),
        .tick(tick_test),
        .amplitude_sel(amplitude_sel),
        .wave_out(wave_out),
        .wave_state(wave_state)
    );

    // =========================================================================
    // Input Selection and Valid Generation
    // =========================================================================
    // Currently only internal source is implemented
    // input_source (SW[8]) reserved for future external input
    assign x_in = wave_out;
    assign valid_in = filter_en & tick_test;

    // =========================================================================
    // PLL IIR Filter (DUT)
    // =========================================================================
    pll_foa #(
        .DATA_WIDTH(DATA_WIDTH),
        .COEFF_WIDTH(COEFF_WIDTH)
    ) u_pll_foa (
        .clk(clk),
        .rst_n(rst_n),
        .valid_in(valid_in),
        .x_in(x_in),
        .valid_out(valid_out),
        .y_out(y_out)
    );

    // =========================================================================
    // Display Slice Selection
    // =========================================================================
    logic signed [DATA_WIDTH-1:0] display_source;

    // Select between input and output
    assign display_source = display_mode ? x_in : y_out;

    // Select which 16-bit slice to display
    always_comb begin
        case (display_slice)
            3'b000: display_value = display_source[15:0];    // Integer LSB
            3'b001: display_value = display_source[31:16];   // Integer MSB
            default: display_value = display_source[15:0];
        endcase
    end

    // Show negative indicator for MSB slice
    assign show_negative = display_source[DATA_WIDTH-1];

    // =========================================================================
    // Seven Segment Controller
    // =========================================================================
    seven_seg_controller u_seven_seg_ctrl (
        .clk(clk),
        .rst_n(rst_n),
        .refresh_tick(clk_display),
        .display_value(display_value),
        .show_negative(show_negative),
        .seg(seg),
        .dp(dp),
        .an(an)
    );

    // =========================================================================
    // LED Status
    // =========================================================================
    led_status #(
        .DATA_WIDTH(DATA_WIDTH)
    ) u_led_status (
        .clk(clk),
        .rst_n(rst_n),
        .filter_en(filter_en),
        .valid_in(valid_in),
        .valid_out(valid_out),
        .y_out(y_out),
        .amplitude_sel(amplitude_sel),
        .freq_sel(freq_sel),
        .wave_state(wave_state),
        .led(led)
    );

endmodule
