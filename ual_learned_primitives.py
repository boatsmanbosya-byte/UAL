# Auto-generated UAL primitives (L_t state)
import math


def solve_quadratic(a, b, c):
    d = b*b - 4*a*c
    if d < 0: return None
    if d == 0: return (-b)/(2*a)
    s = math.sqrt(d)
    return ((-b+s)/(2*a), (-b-s)/(2*a))

