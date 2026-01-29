#include "Fixed.hpp"
#include <string>
#include <sstream>
#include <iostream>
const double x_coff[] = {0.0742, -0.0614, -0.0737, 0.0620};
const double y_coff[] = {2.7448, -2.5169, 0.7710};
const int frac_size = 16;

// Change this to switch between long and int for Fixed point type
typedef long FixedType;
// typedef int FixedType;

int test1(void);
int pll_comparison(int frac_size);
std::string fixed_to_string(Fixed<FixedType> const &n);
void print_cofficients(int frac_size);

int main(void)
{
	// return test1();
	for (int i = 8; i <= 33; i += 1)
		pll_comparison(i);
	// print_cofficients(frac_size);
	return 0;
}

int test1(void)
{
	Fixed<FixedType>	a, b;
	float	perc_error, perc_error_1;
	double	inputf = -0.0737;
	// double	inputf = 1;
	double	mul = 50;
	double result = inputf * mul;
	FixedType one = 1;
	

	for (FixedType i = 0; i <= 24; ++i)
	{
		a.setFixedBits(i);
		b.setFixedBits(i);
		std::cout << "Fixed bits used: " << a.getFixedBits() << std::endl;
		a = Fixed<FixedType>( inputf, i );
		b = a * Fixed<FixedType>( mul, i );
		// std::cout << ((long) roundf(inputf * (one << i))) << std::endl;
		std::cout << a * Fixed<FixedType>( mul, i ) << std::endl;
		if (one << i <= one << (i-1))
			std::cerr << " Bitshift overflow " <<std::endl;
		std::cout << "a is " << a << " " << a.toDouble() << std::endl;
		std::cout << "b is " << b << " " << b.toDouble() << std::endl;
		perc_error = (abs((inputf - a.toDouble()) / inputf)) * 100;
		perc_error_1 = (abs((result - b.toDouble()) / result)) * 100;
		std::cout << "Double result is " << result << " vs Fixed result " << b.toDouble() << std::endl;
		std::cout << "Percentage error for a is " << perc_error << 
						" and for b is " << perc_error_1 << " %" << std::endl;
		std::cout << "-------------------------------------\n";
	}
	
	return 0;
}

int pll_comparison(int frac_size)
{
	FixedType zero = 0;
	int loop_count = 200;
	double perc_err_avg = 0;
	// double x_coff[] = {0.0742, 0, 0, 0};
	// double y_coff[] = {0, 0, 0};
	int len_x_coff = sizeof(x_coff)/sizeof(x_coff[0]);
	int len_y_coff = sizeof(y_coff)/sizeof(y_coff[0]);

	Fixed<FixedType> x_coff_fixed[len_x_coff]; 
	Fixed<FixedType> y_coff_fixed[len_y_coff];
	for (int i = 0; i < len_x_coff; ++i)
		x_coff_fixed[i] = Fixed<FixedType>(x_coff[i], frac_size);
	for (int i = 0; i < len_y_coff; ++i)
		y_coff_fixed[i] = Fixed<FixedType>(y_coff[i], frac_size);
	
	int input_period = 25;
	double inputx[] = {25, 50};
	double x_delay[4] = {0, 0, 0, 0};
	double y_delay[3] = {0, 0, 0};
	Fixed<FixedType> x_delay_fixed[4] = {Fixed<FixedType>(zero, frac_size), Fixed<FixedType>(zero, frac_size), Fixed<FixedType>(zero, frac_size), Fixed<FixedType>(zero, frac_size)};
	Fixed<FixedType> y_delay_fixed[3] = {Fixed<FixedType>(zero, frac_size), Fixed<FixedType>(zero, frac_size), Fixed<FixedType>(zero, frac_size)};
		
	for (int n = 0; n < loop_count; ++n)
	{
		// double x_n_clean = (n % input_period < input_period / 2) ? inputx[0] : inputx[1];
		// double x_n_noisy = x_n_clean + ((rand() % 200) - 100) / 100.0; // Adding noise between -1 to 1
		// double x_n = x_n_noisy;
		double x_n = (n % input_period < input_period / 2) ? inputx[0] : inputx[1];
		Fixed<FixedType> x_n_fixed = Fixed<FixedType>(x_n, frac_size);
		
		// double y_n;
		double y_n = x_coff[0] * x_n + x_coff[1] * x_delay[0] + x_coff[2] 
		* x_delay[1] + x_coff[3] * x_delay[2]
		+ y_coff[0] * y_delay[0] + y_coff[1] * y_delay[1] 
		+ y_coff[2] * y_delay[2];
		
		// Fixed point y_n;
		Fixed<FixedType> y_n_fixed = x_coff_fixed[0] * x_n_fixed + x_coff_fixed[1] * x_delay_fixed[0] + x_coff_fixed[2] 
		* x_delay_fixed[1] + x_coff_fixed[3] * x_delay_fixed[2]
		+ y_coff_fixed[0] * y_delay_fixed[0] + y_coff_fixed[1] * y_delay_fixed[1] 
		+ y_coff_fixed[2] * y_delay_fixed[2];

		// Update delays
		x_delay[2] = x_delay[1];
		x_delay[1] = x_delay[0];
		x_delay[0] = x_n;
		x_delay_fixed[2] = x_delay_fixed[1];
		x_delay_fixed[1] = x_delay_fixed[0];
		x_delay_fixed[0] = x_n_fixed;


		y_delay[2] = y_delay[1];
		y_delay[1] = y_delay[0];
		y_delay[0] = y_n;
		y_delay_fixed[2] = y_delay_fixed[1];
		y_delay_fixed[1] = y_delay_fixed[0];
		y_delay_fixed[0] = y_n_fixed;

		double perc_error = abs((y_n - y_n_fixed.toDouble()) / y_n) * 100;
		perc_err_avg += perc_error;		
		// std::cout << "n: " << n << " Input: " << x_n << " Output Double: "
		//  << y_n << " Output Fixed: " << y_n_fixed << " Percentage Error: " << perc_error << " %" << std::endl;
	}
	perc_err_avg /=  (1.0 * loop_count);
	std::cout << "Average Percentage Error for frac size " << frac_size << " is " << perc_err_avg << " %" << std::endl;
	return 0;
}

std::string fixed_to_string(Fixed<FixedType> const &n)
{
	FixedType raw = n.getRawBits();
	std::ostringstream raw_ss;
	raw_ss << abs(raw);
	std::string str = "";
	if (raw < 0)
		str += "-";
	else
		str += "+";
	str += "32'sd" + raw_ss.str();
	return str;
}

void print_cofficients(int frac_size)
{
	int len_x_coff = sizeof(x_coff)/sizeof(x_coff[0]);
	int len_y_coff = sizeof(y_coff)/sizeof(y_coff[0]);

	Fixed<FixedType> x_coff_fixed[len_x_coff]; 
	Fixed<FixedType> y_coff_fixed[len_y_coff];
	for (int i = 0; i < len_x_coff; ++i)
		x_coff_fixed[i] = Fixed<FixedType>(x_coff[i], frac_size);
	for (int i = 0; i < len_y_coff; ++i)
		y_coff_fixed[i] = Fixed<FixedType>(y_coff[i], frac_size);
	
	std::cout << "\t// Fixed point coefficients with frac size " << frac_size << " :" << std::endl;
	std::cout << "\t// X coefficients: \n";
	for (int i = 0; i < len_x_coff; ++i)
	{
		std::cout << "\tlocalparam signed [COEFF_WIDTH-1:0] c"<< i << " =  " << fixed_to_string(x_coff_fixed[i])
					<< ";  // " << x_coff[i] << " * " << (1u << frac_size) << " ≈ " << x_coff_fixed[i].getRawBits() << std::endl;
	}
	std::cout << std::endl;
	std::cout << "\t// Y coefficients: \n";
	for (int i = 0; i < len_y_coff; ++i)
	{
		std::cout << "\tlocalparam signed [COEFF_WIDTH-1:0] cy"<< i+1 << " =  " << fixed_to_string(y_coff_fixed[i])
					<< ";  // " << y_coff[i] << " * " << (1u << frac_size) << " ≈ " << y_coff_fixed[i].getRawBits() << std::endl;
	}
	std::cout << std::endl;
}
/*
    // Fixed-point coefficients (assuming Q15 format: 1 sign bit + 15 fractional bits)
    // Scale coefficients by 2^15 = 32768 for fixed-point representation
	// y[n] = 0.0742*x[n-0] - 0.0614*x[n-1] - 0.0737*x[n-2] + 0.0620*x[n-3] ../
	// + 2.7448*y[n-1] - 2.5169*y[n-2] + 0.7710*y[n-3]
    localparam signed [COEFF_WIDTH-1:0] c0  =  32'sd2431;  // 0.0742  * 32768 ≈ 2431
    localparam signed [COEFF_WIDTH-1:0] c1  = -32'sd2012;  // -0.0614 * 32768 ≈ -2012
    localparam signed [COEFF_WIDTH-1:0] c2  = -32'sd2415;  // -0.0737 * 32768 ≈ -2415
    localparam signed [COEFF_WIDTH-1:0] c3  =  32'sd2031;  // 0.0620  * 32768 ≈ 2031
    localparam signed [COEFF_WIDTH-1:0] cy1 = 32'sd89941;  // 2.7448 * 32768 ≈ 89941
    localparam signed [COEFF_WIDTH-1:0] cy2 = -32'sd82474; // -2.5169 * 32768 ≈ -82474
    localparam signed [COEFF_WIDTH-1:0] cy3 =  32'sd25264; // 0.7710 * 32768 ≈ 25264
*/