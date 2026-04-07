"""Generate fixed-point coefficient files for RTL and C++ from PLL parameters.

Reads parameters from a JSON config, computes IIR filter coefficients for all
4 El-Khazali approximation types, and writes:
  - .svh files for RTL modules (localparam declarations)
  - .h file for C++ fixed-point validation
"""

import argparse
import contextlib
import io
import json
import os
import warnings
from pathlib import Path

import control
import numpy as np
import sympy

from .transfer_functions import (
	s,
	first_order_tf,
	second_order_tf,
	complex_first_order_tf,
	complex_second_order_tf,
)


def compute_coefficients(params: dict) -> dict:
	"""Compute IIR filter coefficients for all 4 approximation types.

	Returns dict mapping approx type to {num, den} arrays where:
	  num = numerator coefficients (x_coff)
	  den = negated denominator coefficients excluding leading 1 (y_coff)
	"""
	warnings.filterwarnings("ignore", message="An ill-conditioned matrix")
	warnings.filterwarnings("ignore", message=".*states have been removed")

	alpha_f = params["alpha_f"]
	alpha_v = params["alpha_v"]
	beta_f = params["beta_f"]
	beta_v = params["beta_v"]
	tau = params["tau"]
	wc = params["wc"]
	w = params["w"] if "w" in params else 2 * np.pi * wc
	kf = params["kf"]
	kv = params["kv"]
	T = params["T"]
	print(f"  alpha_f={alpha_f}, alpha_v={alpha_v}, beta_f={beta_f}, beta_v={beta_v} \
        tau={tau}, wc={wc}, w={w}, kf={kf}, kv={kv}, T={T}")
 

	# Symbolic transfer functions
	filter_sys = kf / (tau * s**alpha_f + 1)
	vco_sys = kv / (s**alpha_v)

	# Integrator
	Gi_ct = control.tf([1], [1, 0])

	# Complex-order symbolic TFs
	complex_filter_sys = kf / (tau * s ** (alpha_f + 1j * beta_f) + 1)
	complex_vco_sys = kv / (s ** (alpha_v + 1j * beta_v))

	# Build approximations
	approx_builders = {
		"foa": lambda: _build_pll_coeffs(
			first_order_tf(filter_sys, alpha_f, wc),
			first_order_tf(vco_sys, alpha_v, wc),
			Gi_ct, T,
		),
		"soa": lambda: _build_pll_coeffs(
			second_order_tf(filter_sys, alpha_f, wc),
			second_order_tf(vco_sys, alpha_v, wc),
			Gi_ct, T,
		),
		"cfoa": lambda: _build_pll_coeffs(
			complex_first_order_tf(complex_filter_sys, alpha_f, beta_f, w, wc),
			complex_first_order_tf(complex_vco_sys, alpha_v, beta_v, w, wc),
			Gi_ct, T,
		),
		"csoa": lambda: _build_pll_coeffs(
			complex_second_order_tf(complex_filter_sys, alpha_f, beta_f, w, wc),
			complex_second_order_tf(complex_vco_sys, alpha_v, beta_v, w, wc),
			Gi_ct, T,
		),
		"foa_noIntegrator": lambda: _build_pll_coeffs(
			first_order_tf(filter_sys, alpha_f, wc),
			first_order_tf(vco_sys, alpha_v, wc),
			control.tf([1],[1]), T,
		),
		"soa_noIntegrator": lambda: _build_pll_coeffs(
			second_order_tf(filter_sys, alpha_f, wc),
			second_order_tf(vco_sys, alpha_v, wc),
			control.tf([1],[1]), T,
		),
		"cfoa_noIntegrator": lambda: _build_pll_coeffs(
			complex_first_order_tf(complex_filter_sys, alpha_f, beta_f, w, wc),
			complex_first_order_tf(complex_vco_sys, alpha_v, beta_v, w, wc),
			control.tf([1],[1]), T,
		),
		"csoa_noIntegrator": lambda: _build_pll_coeffs(
			complex_second_order_tf(complex_filter_sys, alpha_f, beta_f, w, wc),
			complex_second_order_tf(complex_vco_sys, alpha_v, beta_v, w, wc),
			control.tf([1],[1]), T,
		),
	}

	result = {}
	for name, builder in approx_builders.items():
		num, den = builder()
		result[name] = {"num": num, "den": den}

	return result


def _build_pll_coeffs(Gf, Gvco, Gi, T):
	"""Cascade filter+integrator+VCO, close loop, discretize, extract coefficients."""
	Gc = Gf * Gi * Gvco
	Gpll = control.feedback(Gc, 1)
	Gpll_dis = control.c2d(Gpll, T, method="tustin")
	with contextlib.redirect_stdout(io.StringIO()):
		Gpll_min = control.minreal(Gpll_dis)
	num = np.array(Gpll_min.num[0][0])
	den = np.array(Gpll_min.den[0][0])
	y_coff = -1.0 * den[1:]
	return num, y_coff


def to_fixed(value: float, frac_bits: int) -> int:
	"""Convert floating-point value to fixed-point integer."""
	return round(value * (2 ** frac_bits))


_MIN_COEFFS = {
	"foa":                 (4, 3),
	"soa":                 (6, 5),
	"cfoa":                (6, 5),
	"csoa":                (10, 9),
	"foa_noIntegrator":    (3, 2),
	"soa_noIntegrator":    (5, 4),
	"cfoa_noIntegrator":   (6, 5),
	"csoa_noIntegrator":   (10, 9),
}


def write_svh(coeffs: dict, approx_type: str, frac_width: int, coeff_width: int, output_dir: Path) -> None:
	"""Write a .svh file with localparam declarations for one approximation type.

	Coefficients are zero-padded to the minimum count expected by the
	corresponding RTL module so that compilation never fails due to
	undefined parameters.
	"""
	num = coeffs["num"]
	den = coeffs["den"]

	min_x, min_y = _MIN_COEFFS.get(approx_type, (len(num), len(den)))
	num_count = max(len(num), min_x)
	den_count = max(len(den), min_y)

	lines = [f"// Auto-generated — do not edit. Source: params.json ({approx_type})"]
	lines.append(f"// X coefficients:")
	for i in range(num_count):
		val = num[i] if i < len(num) else 0.0
		fixed_val = to_fixed(val, frac_width)
		sign = "+" if fixed_val >= 0 else "-"
		lines.append(
			f"localparam signed [COEFF_WIDTH-1:0] c{i} = "
			f" {sign}{coeff_width}'sd{abs(fixed_val)};  "
			f"// {val:.6g} * 2^{frac_width}"
		)

	lines.append("")
	lines.append(f"// Y coefficients:")
	for i in range(den_count):
		val = den[i] if i < len(den) else 0.0
		fixed_val = to_fixed(val, frac_width)
		sign = "+" if fixed_val >= 0 else "-"
		lines.append(
			f"localparam signed [COEFF_WIDTH-1:0] cy{i + 1} = "
			f" {sign}{coeff_width}'sd{abs(fixed_val)};  "
			f"// {val:.6g} * 2^{frac_width}"
		)
	lines.append("")

	svh_name = f"pll_{approx_type}_coeffs.svh"
	out_path = output_dir / svh_name
	out_path.write_text("\n".join(lines))
	print(f"  wrote {out_path}")


def write_cpp_header(coeffs: dict, output_dir: Path) -> None:
	"""Write coefficients.h with FOA double arrays for C++ validation."""
	num = coeffs["num"]
	den = coeffs["den"]

	x_vals = ", ".join(f"{v:.15e}" for v in num)
	y_vals = ", ".join(f"{v:.15e}" for v in den)

	content = (
		"// Auto-generated — do not edit. Source: params.json\n"
		"#ifndef PLL_COEFFICIENTS_H\n"
		"#define PLL_COEFFICIENTS_H\n"
		f"const double x_coff[] = {{{x_vals}}};\n"
		f"const double y_coff[] = {{{y_vals}}};\n"
		"#endif\n"
	)

	out_path = output_dir / "coefficients.h"
	out_path.write_text(content)
	print(f"  wrote {out_path}")


def main() -> None:
	parser = argparse.ArgumentParser(description="Generate PLL coefficient files")
	parser.add_argument(
		"--params", default="params.json",
		help="Path to params.json (default: params.json)",
	)
	parser.add_argument(
		"--output", default="generated",
		help="Output directory (default: generated)",
	)
	args = parser.parse_args()

	with open(args.params) as f:
		params = json.load(f)

	frac_width = params["frac_width"]
	coeff_width = params["coeff_width"]

	print("Computing coefficients...")
	coeffs = compute_coefficients(params)

	# Create output directories
	rtl_dir = Path(args.output) / "rtl"
	cpp_dir = Path(args.output) / "cpp"
	rtl_dir.mkdir(parents=True, exist_ok=True)
	cpp_dir.mkdir(parents=True, exist_ok=True)

	# Write SVH files
	print("Writing SVH files...")
	for approx_type, coeff_data in coeffs.items():
		write_svh(coeff_data, approx_type, frac_width, coeff_width, rtl_dir)

	# Write C++ header (FOA by default)
	print("Writing C++ header...")
	write_cpp_header(coeffs["foa"], cpp_dir)

	print("Done.")


if __name__ == "__main__":
	main()
