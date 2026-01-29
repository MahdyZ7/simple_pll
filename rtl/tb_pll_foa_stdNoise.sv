module tb_pll_foa_stdNoise;
    logic clk, rst_n, valid_in;
    logic [31:0] x_in, y_out;
    logic valid_out;


    pll_foa #(.DATA_WIDTH(32)) dut (
        .clk, .rst_n, .valid_in, .x_in, .valid_out, .y_out
    );
	// Noise parameters                                                                                                                             
	localparam real SNR_DB = 10.0;           // Signal-to-noise ratio in dB                                                                         
	localparam real JITTER_VARIANCE = 10.0;   // Jitter variance in time units²                                                                      
	localparam real SIGNAL_AMPLITUDE = 25.0; // Peak signal (half of 50-25 swing)                                                                   
	localparam real NOMINAL_PERIOD = 100.0; // Nominal clock half-period                                                                           
																																					
	// Derived parameters                                                                                                                           
	localparam real NOISE_STDDEV = SIGNAL_AMPLITUDE / (10.0 ** (SNR_DB / 20.0));                                                                    
	localparam real JITTER_STDDEV = $sqrt(JITTER_VARIANCE);                                                                                         
																																					
	// Gaussian random generator using Box-Muller transform                                                                                         
	function automatic real gaussian_rand(real mean, real stddev);                                                                                  
		real u1, u2, z0;                                                                                                                            
		u1 = $urandom() / 4294967296.0;  // Uniform [0,1)                                                                                           
		u2 = $urandom() / 4294967296.0;                                                                                                             
		if (u1 < 1e-10) u1 = 1e-10;      // Avoid log(0)                                                                                            
		z0 = $sqrt(-2.0 * $ln(u1)) * $cos(2.0 * 3.14159265 * u2);                                                                                   
		return mean + stddev * z0;                                                                                                                  
	endfunction                                                                                                                                     
																																					
	// Generate amplitude noise (Gaussian, zero-mean)                                                                                             
	logic signed [31:0] amp_noise;                                                                                                                  
	always @(posedge clk or negedge rst_n) begin                                                                                                    
		if (!rst_n)                                                                                                                                 
			amp_noise <= 0;                                                                                                                         
		else                                                                                                                                        
			amp_noise <= $rtoi(gaussian_rand(0.0, NOISE_STDDEV));                                                                                   
	end                                                                                                                                             
																																					
	// Generate jittered clock toggle                                                                                                               
	logic toggle_jitter;
	logic signed [1:0] jitter_diff;                                                                                                                            
	real jitter_delay;                                                                                                                              
	initial toggle_jitter = 0;                                                                                                                      
	always begin                                                                                                                                    
		jitter_delay = gaussian_rand(0.0, JITTER_STDDEV);                                                                                           
		// Clamp to prevent negative delays                                                                                                         
		if (NOMINAL_PERIOD + jitter_delay < 1.0)                                                                                                    
			jitter_delay = 1.0 - NOMINAL_PERIOD;                                                                                                    
		#(NOMINAL_PERIOD + jitter_delay);                                                                                                           
		toggle_jitter = ~toggle_jitter;                                                                                                             
	end                                                                                                                                             
																																					
	// Clean reference toggle                                                                                                                       
	logic toggle;                                                                                                                                   
	initial toggle = 0;                                                                                                                             
	always #(NOMINAL_PERIOD) toggle = ~toggle;                                                                                                      
																																					
	// Input with SNR-controlled noise                                                                                                              
	assign x_in = (toggle ? 32'd25 : 32'd50) + amp_noise;     
    always #1 clk = ~clk;  //  clock
	assign jitter_diff = toggle - toggle_jitter;


    initial begin
		$dumpvars;
        clk = 0; rst_n = 0; valid_in = 0;
		toggle = 0; toggle_jitter = 0;
		amp_noise = 0;
        #20 rst_n = 1;
		valid_in = 1;
		repeat(10000) @(posedge clk);
    	$stop;
    end
	
endmodule