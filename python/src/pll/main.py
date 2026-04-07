"""Fractional-Order PLL System Analysis using El-Khazali Approximations.

Port of ROA.m lines 1-206: defines system parameters, applies 4 types of
El-Khazali approximations, builds filter/VCO transfer functions, discretizes
them, forms PLL feedback systems, and generates time-difference equations.
"""

import contextlib
import io
import warnings

import numpy as np
import control
import sympy

from .transfer_functions import (
	s,
	first_order_tf,
	second_order_tf,
	complex_first_order_tf,
	complex_second_order_tf,
)


def main() -> None:
	# Suppress ill-conditioned matrix warnings from scipy c2d conversions
	warnings.filterwarnings("ignore", message="An ill-conditioned matrix")
	# Suppress minreal "states removed" messages
	warnings.filterwarnings("ignore", message=".*states have been removed")

	# ── Define System Parameters ──────────────────────────────────────
	alpha_f = 0.5	   # Filter fractional order
	alpha_v = 0.5	   # VCO fractional order
	beta_f = 0.2		# Filter complex-order imaginary part
	beta_v = 0.2		# VCO complex-order imaginary part

	tau = 0.01	  # Time constant
	wc = 10_000			# Corner/characteristic frequency (rad/s)
	w = 2 * np.pi * wc  # Carrier frequency (rad/s)

	# Validate parameters
	assert 0 < alpha_f < 1, "alpha_f must be in range (0, 1)"
	assert 0 < alpha_v < 1, "alpha_v must be in range (0, 1)"
	assert 0 <= beta_f < 1, "beta_f must be in range [0, 1)"
	assert 0 <= beta_v < 1, "beta_v must be in range [0, 1)"

	# Gain parameters
	k = 1			   # General gain
	kf = 100			 # Filter gain
	kv = 100			 # VCO gain

	# Sampling parameters
	T = 3.7e-05				# Sampling period
	T_2 = T**2				  # T squared
	C = 2 / (wc * T)			# Tustin bilinear transformation constant
		
	print("=== System Parameters ===")
	print(f"alpha_f: {alpha_f}, alpha_v: {alpha_v}")
	print(f"beta_f: {beta_f}, beta_v: {beta_v}")
	print(f"tau: {tau:.2e}, wc: {wc:.2g}, w: {w:.2g}")
	print(f"k: {k}, kf: {kf}, kv: {kv}")
	print(f"Sampling period T: {T:.2e}")

	# ── Define filter and VCO transfer functions (symbolic) ───────────
	filter_sys = kf / (tau * s**alpha_f + 1)
	vco_sys = kv / (s**alpha_v)

	# Integrator transfer function: G = 1/s
	Gi_ct = control.tf([1], [1, 0])
	num_dis_integrator_1st, den_dis_integrator_1st = control.tfdata(
		control.c2d(Gi_ct, T, method="tustin")
	)

	# ── First-Order El-Khazali Approximation (Real) ───────────────────
	Gf_ct_foa = first_order_tf(filter_sys, alpha_f, wc)
	Gvco_ct_foa = first_order_tf(vco_sys, alpha_v, wc)

	# Cascaded filter, integrator, and VCO
	Gc_ct_foa = Gf_ct_foa * Gi_ct * Gvco_ct_foa
	Gc_dis_foa = control.c2d(Gc_ct_foa, T, method="tustin")

	# PLL with feedback
	Gpll_ct_foa = control.feedback(Gc_ct_foa, 1)

	# ── Second-Order El-Khazali Approximation (Real) ──────────────────
	Gf_ct_soa = second_order_tf(filter_sys, alpha_f, wc)
	Gvco_ct_soa = second_order_tf(vco_sys, alpha_v, wc)

	# Cascaded filter, integrator, and VCO
	Gc_ct_soa = Gf_ct_soa * Gi_ct * Gvco_ct_soa
	Gc_dis_soa = control.c2d(Gc_ct_soa, T, method="tustin")

	# PLL with feedback
	Gpll_ct_soa = control.feedback(Gc_ct_soa, 1)

	# ── Complex Fractional-Order Approximations ───────────────────────
	# Define complex fractional-order symbolic transfer functions
	complex_filter_sys = kf / (tau * s ** (alpha_f + 1j * beta_f) + 1)
	complex_vco_sys = kv / (s ** (alpha_v + 1j * beta_v))

	# Complex first-order
	Gf_ct_cfoa = complex_first_order_tf(complex_filter_sys, alpha_f, beta_f, w, wc)
	Gvco_ct_cfoa = complex_first_order_tf(complex_vco_sys, alpha_v, beta_v, w, wc)

	Gc_ct_cfoa = Gf_ct_cfoa * Gi_ct * Gvco_ct_cfoa
	Gc_dis_cfoa = control.c2d(Gc_ct_cfoa, T, method="tustin")

	Gpll_ct_cfoa = control.feedback(Gc_ct_cfoa, 1)

	# Complex second-order
	Gf_ct_csoa = complex_second_order_tf(complex_filter_sys, alpha_f, beta_f, w, wc)
	Gvco_ct_csoa = complex_second_order_tf(complex_vco_sys, alpha_v, beta_v, w, wc)

	Gc_ct_csoa = Gvco_ct_csoa * Gi_ct * Gf_ct_csoa   # Note: VCO first (matches MATLAB line 137)
	Gc_dis_csoa = control.c2d(Gc_ct_csoa, T, method="tustin")

	Gpll_ct_csoa = control.feedback(Gc_ct_csoa, 1)

	# ── Collect into lists ────────────────────────────────────────────
	order_types = ["1st-order", "2nd-order", "Complex 1st-order", "Complex 2nd-order"]

	filters = [Gf_ct_foa, Gf_ct_soa, Gf_ct_cfoa, Gf_ct_csoa]
	vcos = [Gvco_ct_foa, Gvco_ct_soa, Gvco_ct_cfoa, Gvco_ct_csoa]
	cascaded_systems = [Gc_ct_foa, Gc_ct_soa, Gc_ct_cfoa, Gc_ct_csoa]
	pll_systems = [Gpll_ct_foa, Gpll_ct_soa, Gpll_ct_cfoa, Gpll_ct_csoa]
	dis_pll_systems = [
		control.c2d(G, T, method="tustin") for G in pll_systems
	]

	# ── Time difference equations from discrete transfer functions ────
	time_diff_eqs = []
	time_diff_strs = []

	for i, name in enumerate(order_types):
		with contextlib.redirect_stdout(io.StringIO()):
			minreal_dis_pll = control.minreal(dis_pll_systems[i])
		num = np.array(minreal_dis_pll.num[0][0])
		den = np.array(minreal_dis_pll.den[0][0])

		print(f"\n=== Time Difference Equation for {name} ===")

		# Build equation string
		time_diff_str = "y[n] = "
		for j in range(len(num)):
			if j > 0 and num[j] >= 0:
				time_diff_str += " + "
			elif j > 0 and num[j] < 0:
				time_diff_str += " - "
			elif num[j] < 0:
				time_diff_str += "-"
			time_diff_str += f"{abs(num[j]):.4f}*x[n-{j}]"

		for j in range(1, len(den)):
			if den[j] >= 0:
				time_diff_str += f" - {den[j]:.4f}*y[n-{j}]"
			else:
				time_diff_str += f" + {abs(den[j]):.4f}*y[n-{j}]"

		print(time_diff_str)
		print(f"const double x_coff[] = {{{', '.join(f'{coef:.6e}' for coef in num)}}};")
		print(f"const double y_coff[] = {{{', '.join(f'{coef:.6e}' for coef in -1.0 * den[1:])}}};")

		# Store the equation coefficients
		time_diff_eqs.append({"num": num, "den": -1.0 * den[1:]})
		time_diff_strs.append(time_diff_str)


if __name__ == "__main__":
	main()
