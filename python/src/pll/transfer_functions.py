"""Transfer function wrappers and symbolic substitution.

Ports of SubstituteFractionalOrder.m, FirstOrderTF.m, SecondOrderTF.m,
ComplexFirstOrderTF.m, ComplexSecondOrderTF.m.
"""

import contextlib
import io
import warnings

import numpy as np
import sympy
import control

from .approximations import (
    first_order_approx,
    second_order_approx,
    complex_first_order_approx,
    complex_second_order_approx,
)

# Shared symbolic variable
s = sympy.Symbol("s")


def substitute_fractional_order(
    sys_expr: sympy.Expr,
    term_to_replace: sympy.Expr,
    num: np.ndarray,
    den: np.ndarray,
) -> control.TransferFunction:
    """Substitute a fractional-order term with its rational approximation.

    Args:
        sys_expr: Symbolic transfer function expression (in terms of s).
        term_to_replace: The exact symbolic term to substitute (e.g. s**0.5).
        num: Numerator polynomial coefficients of the approximation.
        den: Denominator polynomial coefficients of the approximation.

    Returns:
        Approximated transfer function (python-control TransferFunction).
    """
    # Use a temporary symbolic variable as a clean stand-in for the
    # fractional-order term. This avoids sympy issues with complex/float
    # exponents persisting after substitution.
    _u = sympy.Symbol("_u", positive=True)

    # Build rational approximation from coefficients
    approx_num = sympy.Poly(list(num), s).as_expr()
    approx_den = sympy.Poly(list(den), s).as_expr()
    approx = approx_num / approx_den

    # Replace s^exponent → _u AND s^(-exponent) → 1/_u in the expression.
    # This handles both filter (contains s^alpha in denominator polynomial)
    # and VCO (contains 1/s^alpha = s^(-alpha)) cases.
    tf_temp = sys_expr.subs(term_to_replace, _u)

    # Also substitute the inverse: if s^alpha → _u, then s^(-alpha) → 1/_u
    if term_to_replace.is_Pow:
        _, exponent = term_to_replace.as_base_exp()
        inverse_term = s ** (-exponent)
        tf_temp = tf_temp.subs(inverse_term, 1 / _u)

    # Now substitute _u → approximation
    tf_temp = tf_temp.subs(_u, approx)

    # Rationalize and cancel
    tf_temp = sympy.nsimplify(tf_temp, rational=False)
    tf_temp = sympy.cancel(tf_temp)

    # Convert to transfer function
    num_sys, den_sys = sympy.fraction(tf_temp)
    num_coeff = [float(c) for c in sympy.Poly(num_sys, s).all_coeffs()]
    den_coeff = [float(c) for c in sympy.Poly(den_sys, s).all_coeffs()]
    with contextlib.redirect_stdout(io.StringIO()):
        return control.minreal(control.tf(num_coeff, den_coeff))


def first_order_tf(
    sys_expr: sympy.Expr, alpha: float, wc: float
) -> control.TransferFunction:
    """First-order El-Khazali approximation for a fractional-order TF.

    Args:
        sys_expr: Symbolic TF expression containing s**alpha.
        alpha: Fractional order (0 < alpha < 1).
        wc: Characteristic frequency (rad/s).
    """
    if alpha <= 0 or alpha >= 1:
        raise ValueError("alpha must be in range (0, 1)")
    if wc <= 0:
        raise ValueError("wc must be positive")

    term_to_replace = s**alpha
    num, den = first_order_approx(alpha, wc)
    return substitute_fractional_order(sys_expr, term_to_replace, num, den)


def second_order_tf(
    sys_expr: sympy.Expr, alpha: float, wc: float
) -> control.TransferFunction:
    """Second-order El-Khazali approximation for a fractional-order TF.

    Args:
        sys_expr: Symbolic TF expression containing s**alpha.
        alpha: Fractional order (0 < alpha < 1).
        wc: Characteristic frequency (rad/s).
    """
    if alpha <= 0 or alpha >= 1:
        raise ValueError("alpha must be in range (0, 1)")
    if wc <= 0:
        raise ValueError("wc must be positive")

    term_to_replace = s**alpha
    num, den = second_order_approx(alpha, wc)
    return substitute_fractional_order(sys_expr, term_to_replace, num, den)


def complex_first_order_tf(
    sys_expr: sympy.Expr,
    alpha: float,
    beta: float,
    w: float,
    wc: float,
) -> control.TransferFunction:
    """Complex first-order El-Khazali approximation.

    Args:
        sys_expr: Symbolic TF containing s**(alpha + j*beta).
        alpha: Fractional order real part (0 < alpha < 1).
        beta: Imaginary part (0 <= beta < 1).
        w: Carrier frequency (rad/s).
        wc: Characteristic frequency (rad/s).
    """
    if alpha <= 0 or alpha >= 1:
        raise ValueError("alpha must be in range (0, 1)")
    if beta < 0 or beta >= 1:
        raise ValueError("beta must be in range [0, 1)")
    if w <= 0 or wc <= 0:
        raise ValueError("w and wc must be positive")

    exponent = alpha + 1j * beta
    term_to_replace = s**exponent
    num, den = complex_first_order_approx(alpha, beta, w, wc)
    return substitute_fractional_order(sys_expr, term_to_replace, num, den)


def complex_second_order_tf(
    sys_expr: sympy.Expr,
    alpha: float,
    beta: float,
    w: float,
    wc: float,
) -> control.TransferFunction:
    """Complex second-order El-Khazali approximation.

    Args:
        sys_expr: Symbolic TF containing s**(alpha + j*beta).
        alpha: Fractional order real part (0 < alpha < 1).
        beta: Imaginary part (0 <= beta < 1).
        w: Carrier frequency (rad/s).
        wc: Characteristic frequency (rad/s).
    """
    if alpha <= 0 or alpha >= 1:
        raise ValueError("alpha must be in range (0, 1)")
    if beta < 0 or beta >= 1:
        raise ValueError("beta must be in range [0, 1)")
    if w <= 0 or wc <= 0:
        raise ValueError("w and wc must be positive")

    exponent = alpha + 1j * beta
    term_to_replace = s**exponent
    num, den = complex_second_order_approx(alpha, beta, w, wc)
    return substitute_fractional_order(sys_expr, term_to_replace, num, den)
