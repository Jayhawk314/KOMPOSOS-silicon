# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Categorical Cryptography - Vulnerability Detection via Category Theory

Foundation: Category theory reveals vulnerabilities through morphism patterns,
not through direct factorization.

Mathematical Structure:
- Objects: Cryptographic keys
- Morphisms: Relationships (divisibility, shared factors, etc.)
- Hom-functor: Hom(-, K) determines key K (Yoneda lemma)
- Limits: GCD as pullback, shared structure detection
- Anomalies: Keys with unusual Hom-functor structure are vulnerable

Key Insight: Don't factor keys individually. Build the category, find anomalies.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional
import math
from collections import defaultdict
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.category import Category, Object, Morphism


@dataclass
class CryptoKey:
    """
    A cryptographic key as an object in the crypto category.

    The key is determined by its morphisms (Yoneda).
    """
    modulus: int
    exponent: int = 65537
    key_size: int = 0
    source: str = "unknown"

    def __post_init__(self):
        if self.key_size == 0:
            self.key_size = self.modulus.bit_length()

    def __hash__(self):
        return hash(self.modulus)

    def __eq__(self, other):
        return isinstance(other, CryptoKey) and self.modulus == other.modulus


@dataclass
class SharedStructureMorphism:
    """
    Morphism representing shared mathematical structure between keys.

    Examples:
    - Shared factor: gcd(n1, n2) > 1
    - Divisibility: n1 | n2
    - Proximity: |n1 - n2| small
    """
    structure_type: str  # "shared_factor", "divisibility", "proximity"
    strength: float  # How strong the relationship is
    data: Dict = field(default_factory=dict)


class CryptoCategoryBuilder:
    """
    Build category of cryptographic keys.

    Use categorical structure to find vulnerabilities,
    not direct factorization.
    """

    def __init__(self):
        self.category = Category(name="CryptoKeys")
        self.keys: Dict[int, CryptoKey] = {}

    def add_key(self, key: CryptoKey) -> Object:
        """Add key as object in category."""
        obj = Object(name=f"Key_{key.modulus}", type_info={
            "modulus": key.modulus,
            "key_size": key.key_size,
            "source": key.source
        })
        self.category.add_object(obj)
        self.keys[key.modulus] = key
        return obj

    def build_morphisms(self):
        """
        Build morphisms between keys based on mathematical relationships.

        This is where category theory reveals structure.
        """
        keys = list(self.keys.values())
        n = len(keys)

        print(f"Building categorical structure for {n} keys...")

        # Find shared factors (categorical limits)
        for i in range(n):
            for j in range(i+1, min(i+50, n)):  # Check local neighborhood
                self._check_shared_structure(keys[i], keys[j])

    def _check_shared_structure(self, key1: CryptoKey, key2: CryptoKey):
        """
        Check for shared mathematical structure between keys.

        Categorical view: GCD is the pullback (categorical limit).
        Non-trivial GCD = morphism exists.
        """
        g = math.gcd(key1.modulus, key2.modulus)

        if g > 1 and g != key1.modulus and g != key2.modulus:
            # Found shared factor - create morphism
            obj1 = self.category.objects[f"Key_{key1.modulus}"]
            obj2 = self.category.objects[f"Key_{key2.modulus}"]

            mor = Morphism(
                name=f"shared_{g}",
                source=obj1,
                target=obj2,
                data={
                    "type": "shared_factor",
                    "factor": g,
                    "strength": math.log(g) / key1.key_size  # Normalized
                }
            )
            self.category.add_morphism(mor)

    def compute_hom_functor(self, key_modulus: int) -> Dict[str, List[Morphism]]:
        """
        Compute Hom(-, K) for key K.

        Yoneda Lemma: Key is determined by its Hom-functor.
        Anomalous Hom-functor = vulnerability.
        """
        obj_name = f"Key_{key_modulus}"
        if obj_name not in self.category.objects:
            return {}

        obj = self.category.objects[obj_name]

        # Collect all non-identity morphisms to and from this key
        incoming = []
        outgoing = []

        for mor in self.category.morphisms.values():
            if mor.data.get("is_identity"):
                continue
            if mor.target == obj:
                incoming.append(mor)
            if mor.source == obj:
                outgoing.append(mor)

        return {
            "incoming": incoming,
            "outgoing": outgoing,
            "total": len(incoming) + len(outgoing)
        }

    def find_vulnerable_keys(self) -> List[Tuple[CryptoKey, str, float]]:
        """
        Find vulnerable keys via categorical anomaly detection.

        Vulnerabilities appear as:
        - High degree in morphism graph (many relationships)
        - Non-trivial Hom-functor (connected to many keys)
        - Membership in small subcategory
        """
        vulnerable = []

        for modulus, key in self.keys.items():
            hom = self.compute_hom_functor(modulus)

            # Anomaly: Key with many morphisms is suspicious
            if hom["total"] > 0:
                severity = min(1.0, hom["total"] / 10)
                vulnerable.append((
                    key,
                    f"Anomalous Hom-functor: {hom['total']} morphisms",
                    severity
                ))

        return vulnerable


class YonedaCryptoAnalyzer:
    """
    Analyze cryptographic keys using Yoneda lemma.

    Key insight: Key is determined by Hom(-, Key).
    Find vulnerabilities by examining morphism patterns.
    """

    def __init__(self):
        self.builder = CryptoCategoryBuilder()

    def analyze_key_collection(self, keys: List[CryptoKey]) -> Dict:
        """
        Analyze collection of keys using categorical structure.

        Returns:
            Analysis with vulnerable keys and categorical insights
        """
        print("=" * 80)
        print("CATEGORICAL CRYPTO ANALYSIS")
        print("=" * 80)

        # Build category
        print(f"\nAdding {len(keys)} keys to category...")
        for key in keys:
            self.builder.add_key(key)

        # Build morphisms (relationships)
        self.builder.build_morphisms()

        # Find categorical anomalies
        vulnerable = self.builder.find_vulnerable_keys()

        # Categorical insights
        total_morphisms = len(self.builder.category.morphisms)
        avg_degree = (2 * total_morphisms) / len(keys) if len(keys) > 0 else 0

        return {
            "total_keys": len(keys),
            "total_morphisms": total_morphisms,
            "average_degree": avg_degree,
            "vulnerable_keys": vulnerable,
            "category": self.builder.category
        }

    def detect_subcategory_vulnerability(self, keys: List[CryptoKey],
                                         known_weak_size: int = 32768) -> Dict:
        """
        Detect if keys belong to small subcategory (like Debian weak keys).

        Categorical view: Debian vulnerability = keyspace forms small
        subcategory (32,768 objects) within full category of RSA keys.
        """
        # Estimate subcategory size via morphism density
        # Dense interconnections = small subcategory

        self.builder = CryptoCategoryBuilder()
        for key in keys:
            self.builder.add_key(key)

        self.builder.build_morphisms()

        morphism_count = sum(1 for m in self.builder.category.morphisms.values()
                             if not m.data.get("is_identity"))
        key_count = len(keys)

        # Dense graph = potential subcategory
        density = morphism_count / (key_count * (key_count - 1) / 2) if key_count > 1 else 0

        is_subcategory = density > 0.01  # Threshold for "too connected"

        return {
            "is_small_subcategory": is_subcategory,
            "morphism_density": density,
            "estimated_subcategory_size": key_count if is_subcategory else None,
            "vulnerability": "Keyspace exhaustion" if is_subcategory else None
        }


# Demo
if __name__ == "__main__":
    print("Categorical Cryptography - Yoneda Analysis")
    print("=" * 80)

    # Example: Create sample keys with shared factors
    keys = [
        CryptoKey(modulus=1009 * 1013, source="close_primes"),
        CryptoKey(modulus=1009 * 1019, source="shared_factor"),  # Shares 1009
        CryptoKey(modulus=1013 * 1021, source="shared_factor"),  # Shares 1013
        CryptoKey(modulus=104729 * 104743, source="strong"),
    ]

    analyzer = YonedaCryptoAnalyzer()
    result = analyzer.analyze_key_collection(keys)

    print("\n" + "=" * 80)
    print("CATEGORICAL ANALYSIS RESULTS")
    print("=" * 80)
    print(f"Total keys: {result['total_keys']}")
    print(f"Total morphisms: {result['total_morphisms']}")
    print(f"Average degree: {result['average_degree']:.2f}")

    print(f"\nVulnerable keys found: {len(result['vulnerable_keys'])}")
    for key, reason, severity in result['vulnerable_keys']:
        print(f"  - Key {key.modulus} ({key.source})")
        print(f"    Reason: {reason}")
        print(f"    Severity: {severity:.2f}")

    print("\n" + "=" * 80)
    print("KEY INSIGHT: Vulnerabilities emerge from categorical structure,")
    print("not from factoring individual keys!")
    print("=" * 80)
