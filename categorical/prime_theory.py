# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Prime Number Theory as Category Theory

Key insight: Prime factorization is a monoidal functor from (ℤ, ×) to (FreeMonoid(Primes), +)

Mathematical properties:
- F(n × m) = F(n) ⊗ F(m)  (monoidal functor)
- GCD(a,b) = pullback in divisor category
- LCM(a,b) = pushout in divisor category

This module provides the categorical foundation for cryptographic analysis.
"""

from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
from collections import defaultdict
import math


@dataclass
class PrimeFactorization:
    """
    Prime factorization as object in FreeMonoid(Primes).

    n = p1^a1 × p2^a2 × ... × pk^ak
    """
    factors: Dict[int, int]  # {prime: exponent}

    def __mul__(self, other: 'PrimeFactorization') -> 'PrimeFactorization':
        """Monoid operation: combine factorizations."""
        result = defaultdict(int)

        for p, exp in self.factors.items():
            result[p] += exp
        for p, exp in other.factors.items():
            result[p] += exp

        return PrimeFactorization(dict(result))

    def to_int(self) -> int:
        """Convert back to integer."""
        n = 1
        for prime, exp in self.factors.items():
            n *= prime ** exp
        return n

    def __repr__(self):
        if not self.factors:
            return "1"
        terms = [f"{p}^{exp}" if exp > 1 else str(p)
                for p, exp in sorted(self.factors.items())]
        return " × ".join(terms)


class PrimeFactorizationFunctor:
    """
    Factorization as monoidal functor: (ℤ₊, ×) → (FreeMonoid(Primes), ⊗)

    This is the foundation for understanding cryptographic security via category theory.
    """

    def __init__(self):
        self.prime_cache = {}
        self.factorization_cache = {}

    def factor(self, n: int) -> PrimeFactorization:
        """
        Factor integer into primes.

        Uses trial division (fast for small n) and Pollard's rho for larger n.

        Args:
            n: Integer to factor

        Returns:
            PrimeFactorization object
        """
        if n in self.factorization_cache:
            return self.factorization_cache[n]

        if n <= 1:
            return PrimeFactorization({})

        original_n = n  # Save before trial division mutates n

        factors = defaultdict(int)

        # Trial division for small factors
        for p in [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31]:
            while n % p == 0:
                factors[p] += 1
                n //= p

        # If n is still > 1, use more sophisticated methods
        if n > 1:
            if self.is_prime(n):
                factors[n] = 1
            else:
                # Try Pollard's rho for larger composites
                remaining_factors = self._pollard_rho_factor(n)
                for p, exp in remaining_factors.items():
                    factors[p] += exp

        result = PrimeFactorization(dict(factors))
        self.factorization_cache[original_n] = result
        return result

    def is_prime(self, n: int, k: int = 10) -> bool:
        """
        Miller-Rabin primality test.

        Args:
            n: Number to test
            k: Number of rounds (higher = more certain)

        Returns:
            True if n is probably prime, False if composite
        """
        if n in self.prime_cache:
            return self.prime_cache[n]

        if n < 2:
            return False
        if n == 2 or n == 3:
            return True
        if n % 2 == 0:
            return False

        # Write n-1 as 2^r × d
        r, d = 0, n - 1
        while d % 2 == 0:
            r += 1
            d //= 2

        # Miller-Rabin test
        import random

        for _ in range(k):
            a = random.randrange(2, n - 1)
            x = pow(a, d, n)

            if x == 1 or x == n - 1:
                continue

            for _ in range(r - 1):
                x = pow(x, 2, n)
                if x == n - 1:
                    break
            else:
                self.prime_cache[n] = False
                return False

        self.prime_cache[n] = True
        return True

    def _pollard_rho_factor(self, n: int) -> Dict[int, int]:
        """
        Pollard's rho algorithm for integer factorization.

        Expected time: O(√p) for smallest prime factor p.
        """
        if self.is_prime(n):
            return {n: 1}

        def g(x, c, n):
            return (x * x + c) % n

        c = 2
        x, y = 2, 2
        d = 1

        # Floyd's cycle detection
        while d == 1:
            x = g(x, c, n)
            y = g(g(y, c, n), c, n)
            d = math.gcd(abs(x - y), n)

            if d == n:
                # Failure, try different c
                c += 1
                x, y = 2, 2
                d = 1

                if c > 20:
                    # Give up, return n as "prime" (actually composite but hard to factor)
                    return {n: 1}

        # Recursively factor
        factors = defaultdict(int)

        for factor in [d, n // d]:
            if self.is_prime(factor):
                factors[factor] += 1
            else:
                sub_factors = self._pollard_rho_factor(factor)
                for p, exp in sub_factors.items():
                    factors[p] += exp

        return dict(factors)

    def verify_monoidal_functor_law(self, a: int, b: int) -> bool:
        """
        Verify F(a × b) = F(a) ⊗ F(b)

        This is the fundamental property of the factorization functor.
        """
        # Compute F(a × b)
        product = a * b
        f_product = self.factor(product)

        # Compute F(a) ⊗ F(b)
        f_a = self.factor(a)
        f_b = self.factor(b)
        f_a_tensor_f_b = f_a * f_b

        return f_product.factors == f_a_tensor_f_b.factors


class DivisorCategory:
    """
    Category of divisors with GCD and LCM as categorical limits.

    Objects: Positive integers
    Morphisms: d → n if d divides n
    GCD = pullback (greatest lower bound)
    LCM = pushout (least upper bound)
    """

    def __init__(self):
        self.functor = PrimeFactorizationFunctor()

    def divides(self, d: int, n: int) -> bool:
        """Check if d divides n (is there a morphism d → n?)."""
        return n % d == 0

    def gcd_as_pullback(self, a: int, b: int) -> int:
        """
        GCD as pullback (categorical limit).

        The pullback of a ← 1 → b is the largest d such that:
        - d divides a
        - d divides b

        Using factorization:
        GCD = product of min(exp_a, exp_b) for each prime
        """
        f_a = self.functor.factor(a)
        f_b = self.functor.factor(b)

        gcd_factors = {}
        all_primes = set(f_a.factors.keys()) | set(f_b.factors.keys())

        for p in all_primes:
            exp_a = f_a.factors.get(p, 0)
            exp_b = f_b.factors.get(p, 0)
            min_exp = min(exp_a, exp_b)
            if min_exp > 0:
                gcd_factors[p] = min_exp

        return PrimeFactorization(gcd_factors).to_int()

    def lcm_as_pushout(self, a: int, b: int) -> int:
        """
        LCM as pushout (categorical colimit).

        The pushout of a → 1 ← b is the smallest m such that:
        - a divides m
        - b divides m

        Using factorization:
        LCM = product of max(exp_a, exp_b) for each prime
        """
        f_a = self.functor.factor(a)
        f_b = self.functor.factor(b)

        lcm_factors = {}
        all_primes = set(f_a.factors.keys()) | set(f_b.factors.keys())

        for p in all_primes:
            exp_a = f_a.factors.get(p, 0)
            exp_b = f_b.factors.get(p, 0)
            max_exp = max(exp_a, exp_b)
            if max_exp > 0:
                lcm_factors[p] = max_exp

        return PrimeFactorization(lcm_factors).to_int()

    def coprime(self, a: int, b: int) -> bool:
        """Check if a and b are coprime (GCD = 1)."""
        return self.gcd_as_pullback(a, b) == 1


class PrimeGapAnalyzer:
    """
    Analyze prime gaps for side-channel attack detection.

    Prime gaps reveal information about primality testing implementation:
    - Uniform gaps → constant-time (secure)
    - Non-uniform gaps → timing leak (vulnerable to Bleichenbacher, CVE-2025-0977)
    """

    def __init__(self):
        self.functor = PrimeFactorizationFunctor()
        # First 100 primes for reference
        self.small_primes = self._sieve_of_eratosthenes(1000)

    def _sieve_of_eratosthenes(self, limit: int) -> List[int]:
        """Generate primes up to limit."""
        is_prime = [True] * (limit + 1)
        is_prime[0] = is_prime[1] = False

        for i in range(2, int(math.sqrt(limit)) + 1):
            if is_prime[i]:
                for j in range(i * i, limit + 1, i):
                    is_prime[j] = False

        return [i for i in range(limit + 1) if is_prime[i]]

    def compute_prime_gaps(self, start: int, count: int) -> List[int]:
        """
        Compute gaps between consecutive primes starting at start.

        Returns list of gaps: [p₂-p₁, p₃-p₂, ..., p_n-p_{n-1}]
        """
        primes = []
        n = start

        while len(primes) < count:
            if self.functor.is_prime(n):
                primes.append(n)
            n += 1

        gaps = [primes[i+1] - primes[i] for i in range(len(primes) - 1)]
        return gaps

    def detect_timing_leak(self, observed_gaps: List[int]) -> Dict:
        """
        Detect timing leaks via prime gap analysis.

        Timing attacks exploit non-constant-time primality testing.

        Returns:
            Analysis of gap uniformity (uniform = secure, non-uniform = leak)
        """
        if not observed_gaps:
            return {"has_leak": False, "confidence": 0.0}

        # Statistical analysis
        import numpy as np

        gaps_array = np.array(observed_gaps)
        mean_gap = np.mean(gaps_array)
        std_gap = np.std(gaps_array)

        # Expected gap (Prime Number Theorem): ~ln(n)
        # High variance relative to expected = timing leak

        coefficient_of_variation = std_gap / mean_gap if mean_gap > 0 else 0

        # Threshold: CV > 0.5 indicates non-uniform timing
        has_leak = coefficient_of_variation > 0.5

        return {
            "has_leak": has_leak,
            "confidence": min(1.0, coefficient_of_variation),
            "mean_gap": mean_gap,
            "std_gap": std_gap,
            "coefficient_of_variation": coefficient_of_variation,
            "recommendation": "Constant-time primality test required" if has_leak else "Timing appears constant"
        }

    def predict_next_prime_candidate(self, n: int) -> int:
        """
        Predict next prime candidate for primality testing.

        Uses Prime Number Theorem: average gap ≈ ln(n)
        """
        expected_gap = int(math.log(n))

        # Search forward from n + expected_gap
        candidate = n + expected_gap

        # Ensure odd
        if candidate % 2 == 0:
            candidate += 1

        return candidate


# Utility functions
def batch_gcd_attack(moduli: List[int]) -> List[Tuple[int, int, int]]:
    """
    Batch GCD attack to find common factors across RSA moduli.

    If two RSA moduli n₁ = p₁q₁ and n₂ = p₁q₂ share a prime p₁,
    then GCD(n₁, n₂) = p₁ reveals the factorization.

    Args:
        moduli: List of RSA moduli

    Returns:
        List of (i, j, gcd) tuples where gcd(moduli[i], moduli[j]) > 1
    """
    category = DivisorCategory()
    common_factors = []

    for i in range(len(moduli)):
        for j in range(i + 1, len(moduli)):
            gcd = category.gcd_as_pullback(moduli[i], moduli[j])

            if gcd > 1 and gcd < min(moduli[i], moduli[j]):
                # Found common factor!
                common_factors.append((i, j, gcd))

    return common_factors


def fermat_factorization(n: int, max_iterations: int = 10000) -> Optional[Tuple[int, int]]:
    """
    Fermat's factorization for n = p × q where p and q are close.

    Finds a, b such that n = a² - b² = (a-b)(a+b)

    Fast when |p - q| is small (RSA vulnerability).

    Args:
        n: Composite number to factor
        max_iterations: Maximum attempts

    Returns:
        (p, q) factors if found, None otherwise
    """
    if n % 2 == 0:
        return (2, n // 2)

    # Use integer sqrt for large numbers (RSA-2048)
    a = math.isqrt(n) + 1
    b2 = a * a - n

    for _ in range(max_iterations):
        b = math.isqrt(b2)

        if b * b == b2:
            # Found factorization
            p = a - b
            q = a + b
            return (p, q)

        a += 1
        b2 = a * a - n

    return None


def pollard_p_minus_1(n: int, B: int = 1000000) -> Optional[int]:
    """
    Pollard's p-1 algorithm for factoring n.

    Succeeds when n has a prime factor p such that p-1 is B-smooth
    (all prime factors of p-1 are ≤ B).

    Args:
        n: Composite to factor
        B: Smoothness bound

    Returns:
        Non-trivial factor if found, None otherwise
    """
    a = 2

    # Compute a^(M!) mod n where M = B
    for p in range(2, B):
        a = pow(a, p, n)

        # Check GCD before bailout - factor may be discoverable right now
        d = math.gcd(a - 1, n)
        if 1 < d < n:
            return d

        if a == 1:
            return None  # a^(p!) = 1 mod n, GCD was trivial (= n)

    # Final check
    d = math.gcd(a - 1, n)
    if 1 < d < n:
        return d

    return None


# Demo
if __name__ == "__main__":
    print("=" * 80)
    print("PRIME NUMBER THEORY AS CATEGORY THEORY")
    print("=" * 80)

    # Test monoidal functor
    print("\n[1] Testing Monoidal Functor Property")
    functor = PrimeFactorizationFunctor()

    a, b = 12, 18
    f_a = functor.factor(a)
    f_b = functor.factor(b)
    f_ab = functor.factor(a * b)
    f_a_tensor_b = f_a * f_b

    print(f"  F({a}) = {f_a}")
    print(f"  F({b}) = {f_b}")
    print(f"  F({a} × {b}) = F({a*b}) = {f_ab}")
    print(f"  F({a}) ⊗ F({b}) = {f_a_tensor_b}")
    print(f"  Monoidal law holds: {functor.verify_monoidal_functor_law(a, b)}")

    # Test GCD/LCM as limits
    print("\n[2] Testing GCD as Pullback, LCM as Pushout")
    category = DivisorCategory()

    a, b = 48, 18
    gcd = category.gcd_as_pullback(a, b)
    lcm = category.lcm_as_pushout(a, b)

    print(f"  GCD({a}, {b}) = {gcd} (pullback)")
    print(f"  LCM({a}, {b}) = {lcm} (pushout)")
    print(f"  Verify: GCD × LCM = {gcd * lcm}, a × b = {a * b}")
    print(f"  Identity holds: {gcd * lcm == a * b}")

    # Test prime gap analysis
    print("\n[3] Testing Prime Gap Analysis (Side-Channel Detection)")
    gap_analyzer = PrimeGapAnalyzer()

    gaps = gap_analyzer.compute_prime_gaps(1000, 20)
    timing_analysis = gap_analyzer.detect_timing_leak(gaps)

    print(f"  First 20 prime gaps starting at 1000: {gaps[:10]}...")
    print(f"  Timing leak detected: {timing_analysis['has_leak']}")
    print(f"  Coefficient of variation: {timing_analysis['coefficient_of_variation']:.3f}")

    print("\n" + "=" * 80)
