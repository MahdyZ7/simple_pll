"""El-Khazali approximation functions for fractional-order operators.

Ports of FirstOrderApprox.m, SecondOrderApprox.m,
ComplexFirstOrderApprox.m, ComplexSecondOrderApprox.m.
"""

import numpy as np
import control


def first_order_approx(alpha: float, wc: float) -> tuple[np.ndarray, np.ndarray]:
    """First-order El-Khazali approximation for s^alpha.

    Args:
        alpha: Fractional order (0 < alpha < 1).
        wc: Characteristic frequency (rad/s).

    Returns:
        (num, den) polynomial coefficient arrays (descending powers of s).
    """
    zeta = np.tan(alpha * np.pi / 2) + 1 / np.cos(alpha * np.pi / 2)

    num = np.array([zeta / wc, 1.0])
    den = np.array([1.0 / wc, zeta])
    return num, den


def second_order_approx(alpha: float, wc: float) -> tuple[np.ndarray, np.ndarray]:
    """Second-order El-Khazali approximation for s^alpha.

    Args:
        alpha: Fractional order (0 < alpha < 1).
        wc: Characteristic frequency (rad/s).

    Returns:
        (num, den) polynomial coefficient arrays (descending powers of s).
    """
    a0 = alpha**alpha + 2 * alpha + 1
    a2 = alpha**alpha - 2 * alpha + 1
    a1 = (a0 - a2) * np.tan((2 - alpha) * np.pi / 4)

    num = np.array([a0, a1 * wc, a2 * wc**2])
    den = np.array([a2, a1 * wc, a0 * wc**2])
    return num, den


def complex_first_order_approx(
    alpha: float, beta: float, w: float, wc: float
) -> tuple[np.ndarray, np.ndarray]:
    """Complex first-order El-Khazali approximation for s^(alpha + j*beta).

    Args:
        alpha: Fractional order real part (0 < alpha < 1).
        beta: Fractional order imaginary part (0 <= beta < 1).
        w: Carrier frequency (rad/s).
        wc: Characteristic frequency (rad/s).

    Returns:
        (num, den) polynomial coefficient arrays (descending powers of s).
    """
    omega = w / wc
    upsilon = (alpha + 1) / 2
    theta = beta * np.log(omega)

    A1 = np.exp(-beta * np.pi / 2) * np.cos(theta)
    A2 = np.exp(-beta * np.pi / 2) * np.sin(theta) / omega

    G1_num, G1_den = first_order_approx(alpha, wc)
    G2_num, G2_den = first_order_approx(upsilon, wc)

    G1 = control.tf(G1_num, G1_den)
    G2 = control.tf(G2_num, G2_den)

    G_temp = A1 * G1 + A2 * G2 * G2
    num = np.array(G_temp.num[0][0])
    den = np.array(G_temp.den[0][0])
    return num, den


def complex_second_order_approx(
    alpha: float, beta: float, w: float, wc: float
) -> tuple[np.ndarray, np.ndarray]:
    """Complex second-order El-Khazali approximation for s^(alpha + j*beta).

    Args:
        alpha: Fractional order real part (0 < alpha < 1).
        beta: Fractional order imaginary part (0 <= beta < 1).
        w: Carrier frequency (rad/s).
        wc: Characteristic frequency (rad/s).

    Returns:
        (num, den) polynomial coefficient arrays (descending powers of s).
    """
    omega = w / wc
    upsilon = (alpha + 1) / 2
    theta = beta * np.log(omega)

    A1 = np.exp(-beta * np.pi / 2) * np.cos(theta)
    A2 = np.exp(-beta * np.pi / 2) * np.sin(theta) / omega

    G1_num, G1_den = second_order_approx(alpha, wc)
    G2_num, G2_den = second_order_approx(upsilon, wc)

    G1 = control.tf(G1_num, G1_den)
    G2 = control.tf(G2_num, G2_den)

    G_temp = A1 * G1 + A2 * G2 * G2
    num = np.array(G_temp.num[0][0])
    den = np.array(G_temp.den[0][0])
    return num, den
