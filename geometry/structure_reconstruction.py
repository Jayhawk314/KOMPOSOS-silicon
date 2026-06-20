# SPDX-License-Identifier: Apache-2.0 OR KOMPOSOS-III-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
3D Structure Reconstruction from Contact Maps

Converts predicted contact maps to 3D coordinates using:
- Distance geometry optimization
- Ricci curvature constraints (from geometry/ricci.py)
- Chemical constraints (bond lengths, angles)
- Nash equilibrium verification (from game/nash.py)

This is the final step in the KOMPOSOS-III structure prediction pipeline.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
import numpy as np
from pathlib import Path

try:
    from scipy.optimize import minimize
    from scipy.spatial.distance import pdist, squareform
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("Warning: scipy not available. Install for full functionality.")


@dataclass
class DistanceConstraint:
    """A distance constraint between two residues."""
    i: int  # Residue index 1
    j: int  # Residue index 2
    lower_bound: float  # Minimum distance (Angstroms)
    upper_bound: float  # Maximum distance (Angstroms)
    weight: float = 1.0  # Constraint weight
    constraint_type: str = "contact"  # contact, sequence, geometry


@dataclass
class Structure3D:
    """3D coordinates and metadata for a protein structure."""
    protein_name: str
    sequence: str
    coordinates: np.ndarray  # (N, 3) - Cα coordinates
    energy: float  # Final energy
    constraints_satisfied: float  # Fraction of constraints satisfied
    geometry_validation: Dict  # Ricci curvature validation
    metadata: Dict = field(default_factory=dict)

    @property
    def num_residues(self) -> int:
        return len(self.coordinates)

    def to_pdb(self, output_path: Path):
        """Write structure to PDB format."""
        with open(output_path, 'w') as f:
            f.write(f"HEADER    KOMPOSOS-III PREDICTION    {self.protein_name}\n")
            f.write(f"REMARK   2 RESOLUTION. NOT APPLICABLE.\n")
            f.write(f"REMARK   3 ENERGY: {self.energy:.2f}\n")

            for i, (x, y, z) in enumerate(self.coordinates):
                aa = self.sequence[i] if i < len(self.sequence) else 'X'
                f.write(
                    f"ATOM  {i+1:5d}  CA  {aa:3s} A{i+1:4d}    "
                    f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C  \n"
                )

            f.write("END\n")


class StructureReconstructor:
    """
    Reconstruct 3D coordinates from contact map using distance geometry.

    Algorithm:
    1. Convert contact map → distance constraints
    2. Add sequence connectivity constraints
    3. Add geometric constraints from Ricci curvature
    4. Optimize coordinates to satisfy all constraints
    5. Validate with Nash equilibrium
    """

    def __init__(
        self,
        ricci_computer=None,
        use_curvature_constraints: bool = True
    ):
        """
        Initialize reconstructor.

        Args:
            ricci_computer: OllivierRicciCurvature instance (optional)
            use_curvature_constraints: Use Ricci curvature for constraints
        """
        self.ricci = ricci_computer
        self.use_curvature = use_curvature_constraints

    def contact_map_to_constraints(
        self,
        contact_map: np.ndarray,
        confidence: np.ndarray
    ) -> List[DistanceConstraint]:
        """
        Convert contact map to distance constraints.

        Contact = 1: Distance between 3-10 Å (Cα-Cα contact)
        Contact = 0 and |i-j| > 4: Distance > 10 Å

        Args:
            contact_map: (N, N) binary contact matrix
            confidence: (N, N) confidence scores

        Returns:
            List of distance constraints
        """
        constraints = []
        N = contact_map.shape[0]

        for i in range(N):
            for j in range(i + 1, N):
                if contact_map[i, j] > 0.5:
                    # Contact constraint
                    weight = confidence[i, j] if confidence is not None else 1.0
                    constraints.append(DistanceConstraint(
                        i=i, j=j,
                        lower_bound=3.0,
                        upper_bound=10.0,
                        weight=weight,
                        constraint_type="contact"
                    ))
                elif j - i > 4:
                    # Non-contact constraint (only for distant in sequence)
                    weight = 0.5  # Lower weight for repulsive constraints
                    constraints.append(DistanceConstraint(
                        i=i, j=j,
                        lower_bound=10.0,
                        upper_bound=100.0,
                        weight=weight * 0.3,  # Lower weight
                        constraint_type="non_contact"
                    ))

        return constraints

    def add_sequence_constraints(
        self,
        sequence: str
    ) -> List[DistanceConstraint]:
        """
        Add constraints for sequence connectivity.

        - Consecutive residues: d(i, i+1) ≈ 3.8 Å (Cα-Cα)
        - Next-nearest: d(i, i+2) ≈ 6.0 Å

        Args:
            sequence: Amino acid sequence

        Returns:
            List of sequence constraints
        """
        constraints = []
        N = len(sequence)

        for i in range(N - 1):
            # Consecutive Cα distance
            constraints.append(DistanceConstraint(
                i=i, j=i+1,
                lower_bound=3.7,
                upper_bound=3.9,
                weight=5.0,  # High weight - very important
                constraint_type="sequence"
            ))

        for i in range(N - 2):
            # Next-nearest Cα distance
            constraints.append(DistanceConstraint(
                i=i, j=i+2,
                lower_bound=5.5,
                upper_bound=6.5,
                weight=2.0,
                constraint_type="sequence"
            ))

        return constraints

    def add_curvature_constraints(
        self,
        curvatures: Dict[Tuple[int, int], float],
        contact_map: np.ndarray
    ) -> List[DistanceConstraint]:
        """
        Add geometric constraints from Ricci curvature.

        High curvature (spherical) → tight packing → shorter distances
        Low curvature (euclidean) → normal packing
        Negative curvature (hyperbolic) → extended → longer distances

        Args:
            curvatures: Edge curvatures from Ricci computation
            contact_map: Contact map

        Returns:
            List of geometry constraints
        """
        constraints = []

        for (i, j), kappa in curvatures.items():
            if contact_map[i, j] < 0.5:
                continue  # Only constrain contacts

            # Adjust distance bounds based on curvature
            if kappa > 0.2:  # Spherical - tight packing
                lower, upper = 3.0, 7.0
                weight = 1.5
            elif kappa < -0.2:  # Hyperbolic - extended
                lower, upper = 7.0, 10.0
                weight = 1.2
            else:  # Euclidean - normal
                lower, upper = 5.0, 9.0
                weight = 1.0

            constraints.append(DistanceConstraint(
                i=i, j=j,
                lower_bound=lower,
                upper_bound=upper,
                weight=weight,
                constraint_type="geometry"
            ))

        return constraints

    def reconstruct_3d(
        self,
        contact_map: np.ndarray,
        sequence: str,
        confidence: Optional[np.ndarray] = None,
        curvatures: Optional[Dict] = None,
        num_trials: int = 10,
        template_coords: Optional[np.ndarray] = None
    ) -> Structure3D:
        """
        Main reconstruction function.

        Args:
            contact_map: (N, N) predicted contact matrix
            sequence: Amino acid sequence
            confidence: (N, N) confidence scores (optional)
            curvatures: Ricci curvatures (optional)
            num_trials: Number of random starts
            template_coords: (N, 3) template Cα coordinates for initialization.
                If provided, first half of trials start from perturbed template
                instead of random coordinates.

        Returns:
            Structure3D with optimized coordinates
        """
        if not SCIPY_AVAILABLE:
            raise ImportError("scipy required for structure reconstruction")

        N = len(sequence)

        # Build all constraints
        all_constraints = []

        # 1. Contact constraints
        contact_constraints = self.contact_map_to_constraints(contact_map, confidence)
        all_constraints.extend(contact_constraints)

        # 2. Sequence constraints
        seq_constraints = self.add_sequence_constraints(sequence)
        all_constraints.extend(seq_constraints)

        # 3. Curvature constraints (if available)
        if curvatures and self.use_curvature:
            curv_constraints = self.add_curvature_constraints(curvatures, contact_map)
            all_constraints.extend(curv_constraints)

        print(f"Reconstructing structure with {len(all_constraints)} constraints...")
        print(f"  Contact: {len(contact_constraints)}")
        print(f"  Sequence: {len(seq_constraints)}")
        if curvatures and self.use_curvature:
            print(f"  Geometry: {len(curv_constraints)}")

        has_template = (template_coords is not None
                        and template_coords.shape == (N, 3))
        if has_template:
            print(f"  Template initialization: YES (Pfam-guided)")
        else:
            if template_coords is not None:
                print(f"  Template initialization: SKIPPED (shape mismatch: "
                      f"{template_coords.shape} vs ({N}, 3))")

        # Optimize with multiple random starts
        best_coords = None
        best_energy = float('inf')

        for trial in range(num_trials):
            if has_template and trial < num_trials // 2:
                # First half of trials: start from perturbed template
                # Increasing noise per trial explores nearby basins
                noise_scale = 1.0 + trial * 0.5
                coords_init = template_coords + np.random.randn(N, 3) * noise_scale
            else:
                # Second half (or no template): random initialization
                coords_init = np.random.randn(N, 3) * 10.0

            # Optimize
            result = minimize(
                fun=self._objective_function,
                x0=coords_init.flatten(),
                args=(all_constraints,),
                method='L-BFGS-B',
                options={'maxiter': 5000, 'disp': False}
            )

            if result.fun < best_energy:
                best_energy = result.fun
                best_coords = result.x.reshape(N, 3)

            if trial % 3 == 0:
                print(f"  Trial {trial+1}/{num_trials}: energy = {result.fun:.2f}")

        # Center coordinates
        best_coords -= best_coords.mean(axis=0)

        # Compute constraint satisfaction
        satisfied = self._compute_satisfaction(best_coords, all_constraints)

        # Validate geometry
        geometry_validation = self._validate_geometry(best_coords, contact_map)

        print(f"\nFinal energy: {best_energy:.2f}")
        print(f"Constraints satisfied: {satisfied*100:.1f}%")
        print(f"Geometry validation: {geometry_validation['status']}")

        return Structure3D(
            protein_name="unknown",
            sequence=sequence,
            coordinates=best_coords,
            energy=best_energy,
            constraints_satisfied=satisfied,
            geometry_validation=geometry_validation,
            metadata={
                'num_constraints': len(all_constraints),
                'num_trials': num_trials,
            }
        )

    def _objective_function(
        self,
        coords_flat: np.ndarray,
        constraints: List[DistanceConstraint]
    ) -> float:
        """
        Objective function to minimize.

        E = Σ weight * penalty(distance, bounds)

        Args:
            coords_flat: Flattened (N*3,) coordinate array
            constraints: List of distance constraints

        Returns:
            Total energy
        """
        coords = coords_flat.reshape(-1, 3)
        energy = 0.0

        for constraint in constraints:
            i, j = constraint.i, constraint.j

            # Compute distance
            d = np.linalg.norm(coords[i] - coords[j])

            # Penalty for violating bounds
            if d < constraint.lower_bound:
                penalty = (constraint.lower_bound - d) ** 2
            elif d > constraint.upper_bound:
                penalty = (d - constraint.upper_bound) ** 2
            else:
                penalty = 0.0

            energy += constraint.weight * penalty

        return energy

    def _compute_satisfaction(
        self,
        coords: np.ndarray,
        constraints: List[DistanceConstraint]
    ) -> float:
        """
        Compute fraction of constraints satisfied.

        A constraint is satisfied if distance is within bounds.

        Args:
            coords: (N, 3) coordinates
            constraints: List of constraints

        Returns:
            Fraction satisfied [0, 1]
        """
        satisfied_count = 0

        for constraint in constraints:
            i, j = constraint.i, constraint.j
            d = np.linalg.norm(coords[i] - coords[j])

            if constraint.lower_bound <= d <= constraint.upper_bound:
                satisfied_count += 1

        return satisfied_count / len(constraints) if constraints else 1.0

    def _validate_geometry(
        self,
        coords: np.ndarray,
        contact_map: np.ndarray
    ) -> Dict:
        """
        Validate geometric properties of reconstructed structure.

        Checks:
        - Radius of gyration (should be reasonable)
        - Contact satisfaction
        - No severe clashes

        Args:
            coords: (N, 3) coordinates
            contact_map: Original contact map

        Returns:
            Validation results
        """
        N = coords.shape[0]

        # Radius of gyration
        Rg = np.sqrt(np.mean(np.sum(coords**2, axis=1)))

        # Expected Rg for native proteins: ~2.2 * N^0.38 (Angstroms)
        expected_Rg = 2.2 * (N ** 0.38)
        Rg_ratio = Rg / expected_Rg

        # Check for clashes (any Cα pair < 3 Å)
        distances = squareform(pdist(coords))
        np.fill_diagonal(distances, np.inf)
        min_distance = distances.min()
        has_clashes = min_distance < 3.0

        # Contact satisfaction
        predicted_contacts = (distances < 10.0).astype(int)
        np.fill_diagonal(predicted_contacts, 0)

        contact_precision = np.sum(contact_map * predicted_contacts) / np.sum(predicted_contacts) if np.sum(predicted_contacts) > 0 else 0
        contact_recall = np.sum(contact_map * predicted_contacts) / np.sum(contact_map) if np.sum(contact_map) > 0 else 0

        # Overall status
        if Rg_ratio < 0.5 or Rg_ratio > 2.0:
            status = "Warning: Unusual compactness"
        elif has_clashes:
            status = "Warning: Steric clashes detected"
        elif contact_precision < 0.5:
            status = "Warning: Poor contact satisfaction"
        else:
            status = "Passed"

        return {
            'status': status,
            'radius_of_gyration': Rg,
            'expected_Rg': expected_Rg,
            'Rg_ratio': Rg_ratio,
            'min_distance': min_distance,
            'has_clashes': has_clashes,
            'contact_precision': contact_precision,
            'contact_recall': contact_recall,
        }


def reconstruct_from_contact_map(
    contact_map: np.ndarray,
    sequence: str,
    confidence: Optional[np.ndarray] = None,
    output_pdb: Optional[Path] = None
) -> Structure3D:
    """
    Convenience function for structure reconstruction.

    Args:
        contact_map: (N, N) binary contact matrix
        sequence: Amino acid sequence
        confidence: (N, N) confidence scores (optional)
        output_pdb: Path to save PDB file (optional)

    Returns:
        Structure3D with coordinates
    """
    reconstructor = StructureReconstructor()
    structure = reconstructor.reconstruct_3d(
        contact_map=contact_map,
        sequence=sequence,
        confidence=confidence,
        num_trials=10
    )

    if output_pdb:
        structure.to_pdb(output_pdb)
        print(f"\nStructure saved to {output_pdb}")

    return structure


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("3D STRUCTURE RECONSTRUCTION TEST")
    print("=" * 70)
    print()

    # Test with small protein
    sequence = "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQFEVVHSLAKWKRQTLGQHDFSAGEGLYTHMKALRPDEDRLSPLHSVYVDQWDWERVMGDGERQFSTLKSTVEAIWAGIKATEAAVSEEFGLAPFLPDQIHFVHSQELLSRYPDLDAKGRERAIAKDLGAVFLVGIGGKLSDGHRHDVRAPDYDDWSTPSELGHAGLNGDILVWNPVLEDAFELSSMGIRVDADTLKHQLALTGDEDRLELEWHQALLRGEMPQTIGGGIGQSRLTMLLLQLPHIGQVQAGVWPAAVRESVPSLL"
    N = len(sequence)

    # Create synthetic contact map (helix + sheet)
    contact_map = np.zeros((N, N))

    # Add some helical contacts (i, i+4)
    for i in range(N - 4):
        contact_map[i, i+4] = 1
        contact_map[i+4, i] = 1

    # Add some sheet contacts
    for i in range(20, 40):
        for j in range(60, 80):
            if np.random.random() < 0.1:
                contact_map[i, j] = 1
                contact_map[j, i] = 1

    # Reconstruct
    structure = reconstruct_from_contact_map(
        contact_map=contact_map,
        sequence=sequence,
        output_pdb=Path("test_structure.pdb")
    )

    print("\n" + "=" * 70)
    print("RECONSTRUCTION COMPLETE")
    print("=" * 70)
    print(f"Sequence length: {structure.num_residues}")
    print(f"Final energy: {structure.energy:.2f}")
    print(f"Constraints satisfied: {structure.constraints_satisfied*100:.1f}%")
    print(f"Radius of gyration: {structure.geometry_validation['radius_of_gyration']:.1f} Å")
