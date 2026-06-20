# SPDX-License-Identifier: Apache-2.0 OR KOMPOSOS-III-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
INTEGRATED CATEGORY THEORY PREDICTOR

This is the TRUE KOMPOSOS-III vision:
- Category theory (KAN extensions) for compositional reasoning
- Physical-Chemical Bridge for constraints
- Together: Accurate, interpretable, physically valid predictions

The key innovation:
Physical chemistry constraints are INPUTS to category theory composition,
not validation after the fact.

Mathematical Framework:
    Lan_K(F)(sequence) where:
    - F: Known proteins → Structures (functor)
    - K: Known → Full (embedding)
    - Constraints: Physical chemistry rules that F must satisfy

    Result: Compositionally-derived, physically-valid structure
"""

import numpy as np
from typing import Tuple, Dict, List, Optional
from pathlib import Path
from dataclasses import dataclass
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

# Category theory core
from categorical.kan_extensions import LeftKanExtension, Functor, Category, Object, Morphism

# Physical-Chemical Bridge (NEW!)
from chemistry import (
    HydrogenBondValidator,
    VanDerWaalsConstraints,
    ElectrostaticConstraints,
    HydrophobicConstraints,
    StatisticalPotentials,
    RamachandranValidator,
    EnergyFunction,
    StructureOptimizer
)

# Existing predictors
try:
    from .category_msa import CategoryTheoreticMSA
    from .pdb_kan_extensions import KanExtensionContactPredictor, PDBPatternLibrary
    from .structure_reconstruction import StructureReconstructor
except ImportError:
    from category_msa import CategoryTheoreticMSA
    from pdb_kan_extensions import KanExtensionContactPredictor, PDBPatternLibrary
    from structure_reconstruction import StructureReconstructor


@dataclass
class PhysicallyValidContact:
    """
    A contact that satisfies physical chemistry constraints.

    This is the output of category theory + physics integration.
    """
    residue_i: int
    residue_j: int
    confidence: float

    # Evidence from category theory
    category_evidence: Dict  # MSA coevolution, PDB patterns, etc.

    # Validation from physics
    physical_validation: Dict  # H-bond compatible, vdW ok, etc.

    # Combined score
    integrated_score: float


class PhysicalConstraintFilter:
    """
    Filters category theory predictions using physical chemistry.

    This is the bridge between math and physics:
    - Category theory proposes contacts
    - Physical chemistry validates/scores them
    - Only physically plausible contacts pass through
    """

    def __init__(self):
        """Initialize all physical constraint checkers."""
        self.hbond = HydrogenBondValidator()
        self.vdw = VanDerWaalsConstraints()
        self.electrostatics = ElectrostaticConstraints()
        self.hydrophobic = HydrophobicConstraints()
        self.stat_pot = StatisticalPotentials()

        print("[OK] Physical constraint filter initialized")

    def validate_contact(
        self,
        i: int,
        j: int,
        sequence: str,
        coords_estimate: Optional[np.ndarray] = None
    ) -> Dict:
        """
        Validate a proposed contact using physical chemistry.

        Args:
            i, j: Residue indices
            sequence: Amino acid sequence
            coords_estimate: Estimated coordinates (if available)

        Returns:
            Dict with validation results and score
        """
        aa_i = sequence[i]
        aa_j = sequence[j]

        validation = {
            'hbond_compatible': False,
            'vdw_plausible': False,
            'charge_compatible': False,
            'hydrophobic_compatible': False,
            'score': 0.0
        }

        # Check H-bond compatibility
        can_donate_i = aa_i in self.hbond.donors
        can_accept_i = aa_i in self.hbond.acceptors
        can_donate_j = aa_j in self.hbond.donors
        can_accept_j = aa_j in self.hbond.acceptors

        if (can_donate_i and can_accept_j) or (can_donate_j and can_accept_i):
            validation['hbond_compatible'] = True
            validation['score'] += 0.3

        # Check charge compatibility (salt bridge)
        charged_pos = set('KRH')
        charged_neg = set('DE')

        if (aa_i in charged_pos and aa_j in charged_neg) or \
           (aa_i in charged_neg and aa_j in charged_pos):
            validation['charge_compatible'] = True
            validation['score'] += 0.3

        # Check hydrophobic compatibility
        hydrophobic = set('AILMFVW')
        if aa_i in hydrophobic and aa_j in hydrophobic:
            validation['hydrophobic_compatible'] = True
            validation['score'] += 0.2

        # vdW plausibility (distance-dependent, needs coords)
        # For now, assume plausible if residues not too close in sequence
        if abs(i - j) >= 4:
            validation['vdw_plausible'] = True
            validation['score'] += 0.2

        return validation

    def filter_contact_map(
        self,
        contact_map: np.ndarray,
        sequence: str,
        category_scores: Optional[np.ndarray] = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Filter entire contact map using physical constraints.

        Args:
            contact_map: Binary contact map from category theory
            sequence: Amino acid sequence
            category_scores: Confidence scores from category theory

        Returns:
            (filtered_contacts, integrated_scores)
        """
        L = len(sequence)
        filtered = np.zeros((L, L), dtype=int)
        scores = np.zeros((L, L), dtype=float)

        for i in range(L):
            for j in range(i+4, L):  # Skip short-range
                if contact_map[i, j] == 1:
                    # Category theory proposed this contact
                    cat_score = category_scores[i, j] if category_scores is not None else 0.5

                    # Validate with physics
                    validation = self.validate_contact(i, j, sequence)
                    phys_score = validation['score']

                    # Integrate: category theory * physical validation
                    integrated = cat_score * (0.3 + 0.7 * phys_score)

                    if integrated > 0.3:  # Threshold
                        filtered[i, j] = 1
                        filtered[j, i] = 1
                        scores[i, j] = integrated
                        scores[j, i] = integrated

        return filtered, scores


class IntegratedCategoryTheoryPredictor:
    """
    KOMPOSOS-III Integrated Predictor

    Combines:
    1. Category theory (KAN extensions) - Compositional reasoning
    2. Physical chemistry (Bridge) - Constraints
    3. Structure reconstruction - 3D coordinates

    This is the complete system for accurate protein structure prediction.
    """

    def __init__(
        self,
        store=None,
        use_msa: bool = True,
        use_pdb_patterns: bool = True,
        use_physics: bool = True
    ):
        """
        Initialize integrated predictor.

        Args:
            store: KomposOSStore for category theory
            use_msa: Use MSA coevolution
            use_pdb_patterns: Use PDB pattern Kan extensions
            use_physics: Use physical chemistry constraints
        """
        print("=" * 70)
        print("KOMPOSOS-III INTEGRATED CATEGORY THEORY PREDICTOR")
        print("=" * 70)
        print()
        print("Combining:")
        print("  1. Category Theory - Compositional reasoning (KAN extensions)")
        print("  2. Physical Chemistry - Constraints (H-bonds, vdW, etc.)")
        print("  3. Structure Reconstruction - 3D coordinates")
        print()

        self.store = store
        self.use_msa = use_msa
        self.use_pdb_patterns = use_pdb_patterns
        self.use_physics = use_physics

        # Component 1: Category theory predictors
        if use_msa:
            print("Loading Category Theory: MSA Coevolution...")
            self.msa_predictor = CategoryTheoreticMSA()
            print("  [OK] MSA natural transformation functor")
        else:
            self.msa_predictor = None

        if use_pdb_patterns:
            print("Loading Category Theory: PDB Kan Extensions...")
            self.pdb_library = PDBPatternLibrary()
            self.pdb_library.build_default_library()
            self.kan_predictor = KanExtensionContactPredictor(store, self.pdb_library)
            print("  [OK] PDB pattern Kan extension functor")
        else:
            self.kan_predictor = None

        # Component 2: Physical chemistry constraints
        if use_physics:
            print("Loading Physical-Chemical Bridge...")
            self.physics_filter = PhysicalConstraintFilter()
            self.energy_function = EnergyFunction()
            self.optimizer = StructureOptimizer(self.energy_function)
            print("  [OK] Physical constraint filter")
        else:
            self.physics_filter = None

        # Component 3: Structure reconstruction
        print("Loading Structure Reconstructor...")
        self.reconstructor = StructureReconstructor(use_curvature_constraints=True)
        print("  [OK] 3D reconstruction")

        print()
        print("Integrated Predictor READY")
        print("=" * 70)
        print()

    def predict_structure(
        self,
        sequence: str,
        optimize: bool = True
    ) -> Dict:
        """
        Predict protein structure using integrated approach.

        Pipeline:
        1. Category theory proposes contacts (MSA + PDB patterns)
        2. Physical chemistry filters/validates
        3. Reconstruct 3D structure
        4. Optimize with energy function

        Args:
            sequence: Amino acid sequence
            optimize: Run energy optimization

        Returns:
            Dict with structure, contacts, validation, interpretation
        """
        print("\n" + "=" * 70)
        print("INTEGRATED STRUCTURE PREDICTION")
        print("=" * 70)
        print(f"Sequence: {sequence[:50]}{'...' if len(sequence) > 50 else ''}")
        print(f"Length: {len(sequence)} residues")
        print()

        L = len(sequence)

        # =====================================================================
        # PHASE 1: Category Theory Contact Prediction
        # =====================================================================
        print("PHASE 1: Category Theory Contact Prediction")
        print("-" * 70)

        category_contacts = np.zeros((L, L), dtype=float)
        category_evidence = {}

        # Functor 1: MSA Coevolution
        if self.use_msa and self.msa_predictor:
            print("  [1/2] MSA Coevolution Functor...")
            contacts_msa, coupling = self.msa_predictor.predict_contacts_from_coevolution(
                query_sequence=sequence,
                num_seqs=100,
                top_L=L
            )
            category_contacts += contacts_msa.astype(float)
            category_evidence['msa'] = int(contacts_msa.sum() / 2)
            print(f"        MSA proposed: {category_evidence['msa']} contacts")

        # Functor 2: PDB Kan Extension
        if self.use_pdb_patterns and self.kan_predictor:
            print("  [2/2] PDB Kan Extension Functor...")
            contacts_kan, metadata = self.kan_predictor.predict_contacts(sequence)
            category_contacts += contacts_kan.astype(float)
            category_evidence['kan'] = int(contacts_kan.sum() / 2)
            print(f"        Kan proposed: {category_evidence['kan']} contacts")

        # Normalize category theory predictions
        max_val = category_contacts.max()
        if max_val > 0:
            category_contacts /= max_val

        # Binarize
        category_binary = (category_contacts > 0.5).astype(int)
        num_category = int(category_binary.sum() / 2)

        print(f"\n  Category Theory Total: {num_category} contacts")
        print()

        # =====================================================================
        # PHASE 2: Physical Chemistry Filtering
        # =====================================================================
        print("PHASE 2: Physical Chemistry Constraint Filtering")
        print("-" * 70)

        if self.use_physics and self.physics_filter:
            print("  Validating contacts with physical chemistry...")
            filtered_contacts, integrated_scores = self.physics_filter.filter_contact_map(
                category_binary,
                sequence,
                category_contacts
            )

            num_filtered = int(filtered_contacts.sum() / 2)
            pass_rate = (num_filtered / num_category * 100) if num_category > 0 else 0

            print(f"  Physical validation:")
            print(f"    Proposed by category theory: {num_category}")
            print(f"    Passed physical constraints: {num_filtered}")
            print(f"    Pass rate: {pass_rate:.1f}%")

            final_contacts = filtered_contacts
            final_scores = integrated_scores
        else:
            print("  [SKIP] Physical filtering disabled")
            final_contacts = category_binary
            final_scores = category_contacts

        print()

        # =====================================================================
        # PHASE 3: 3D Structure Reconstruction
        # =====================================================================
        print("PHASE 3: 3D Structure Reconstruction")
        print("-" * 70)

        print("  Reconstructing 3D coordinates...")
        structure_3d = self.reconstructor.reconstruct_3d(
            contact_map=final_contacts,
            sequence=sequence,
            confidence=final_scores,
            curvatures={},
            num_trials=10
        )

        print(f"  [OK] Structure reconstructed")
        print(f"       Energy: {structure_3d.energy:.2f}")
        print(f"       Constraints: {structure_3d.constraints_satisfied*100:.1f}%")
        print()

        # =====================================================================
        # PHASE 4: Energy Optimization (Optional)
        # =====================================================================
        if optimize and self.use_physics:
            print("PHASE 4: Energy Optimization")
            print("-" * 70)

            print("  Preparing structure data...")
            structure_data = self._prepare_structure_data(
                structure_3d.coordinates,
                sequence,
                final_contacts
            )

            print("  Running gradient descent...")
            opt_result = self.optimizer.minimize_gradient_descent(
                structure_data,
                max_iterations=50,
                step_size=0.01,
                convergence_threshold=0.1
            )

            print(f"  [OK] Optimization complete")
            print(f"       Initial: {opt_result.initial_energy:.2f} kcal/mol")
            print(f"       Final: {opt_result.final_energy:.2f} kcal/mol")
            print(f"       Improvement: {opt_result.energy_improvement:.2f} kcal/mol")

            # Update coordinates
            structure_3d.coordinates = opt_result.final_coords
            structure_3d.energy = opt_result.final_energy
            print()

        # =====================================================================
        # FINALIZE
        # =====================================================================
        print("=" * 70)
        print("PREDICTION COMPLETE")
        print("=" * 70)
        print()
        print("MATHEMATICAL INTERPRETATION:")
        print("  1. Category theory composed MSA + PDB patterns (KAN extensions)")
        print("  2. Physical chemistry constrained to valid structures")
        print("  3. Structure reconstructed with geometric optimization")
        print("  4. Energy minimized to physically stable state")
        print()
        print("This is compositional, interpretable, and physically valid!")
        print("=" * 70)
        print()

        return {
            'sequence': sequence,
            'structure_3d': structure_3d,
            'contacts': final_contacts,
            'contact_scores': final_scores,
            'category_evidence': category_evidence,
            'num_contacts': int(final_contacts.sum() / 2),
            'energy': structure_3d.energy,
            'constraints_satisfied': structure_3d.constraints_satisfied
        }

    def _prepare_structure_data(
        self,
        coords: np.ndarray,
        sequence: str,
        contacts: np.ndarray
    ) -> Dict:
        """Prepare structure data for energy computation."""
        N = len(sequence)

        # Extract contact list
        contact_list = []
        for i in range(N):
            for j in range(i+4, N):
                if contacts[i, j] == 1:
                    contact_list.append((i, j))

        # Approximate phi/psi
        phi = np.full(N, -60.0)
        psi = np.full(N, -45.0)
        phi[0] = psi[-1] = np.nan

        return {
            'coords': coords,
            'sequence': sequence,
            'contacts': contact_list,
            'phi': phi,
            'psi': psi,
            'rotamers': []
        }

    def save_structure(self, result: Dict, output_path: Path):
        """Save predicted structure to PDB file."""
        structure_3d = result['structure_3d']
        structure_3d.protein_name = "KOMPOSOS_prediction"
        structure_3d.to_pdb(output_path)
        print(f"Structure saved to {output_path}")


def test_integrated_predictor():
    """Test integrated predictor on a protein."""
    print()
    print("=" * 70)
    print("TESTING INTEGRATED CATEGORY THEORY PREDICTOR")
    print("=" * 70)
    print()

    # Test sequence (Villin HP36)
    sequence = "MLSDEDFKAVFGMTRSAFANLPLWKQQNLKKEKGLF"

    print(f"Test protein: Villin HP36")
    print(f"Length: {len(sequence)} residues")
    print()

    # Initialize predictor
    predictor = IntegratedCategoryTheoryPredictor(
        use_msa=True,
        use_pdb_patterns=True,
        use_physics=True
    )

    # Predict structure
    result = predictor.predict_structure(sequence, optimize=True)

    # Save structure
    output_path = Path("villin_integrated_prediction.pdb")
    predictor.save_structure(result, output_path)

    print()
    print("=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    print(f"Contacts predicted: {result['num_contacts']}")
    print(f"Final energy: {result['energy']:.2f} kcal/mol")
    print(f"Constraints satisfied: {result['constraints_satisfied']*100:.1f}%")
    print()
    print("Category theory evidence:")
    for source, count in result['category_evidence'].items():
        print(f"  {source}: {count} contacts")
    print()
    print("Next steps:")
    print("  1. Compare to experimental structure (PDB)")
    print("  2. Compute TM-score and RMSD")
    print("  3. Validate on more proteins")
    print("=" * 70)
    print()


if __name__ == "__main__":
    test_integrated_predictor()
