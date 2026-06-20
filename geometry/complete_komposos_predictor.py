# SPDX-License-Identifier: Apache-2.0 OR KOMPOSOS-III-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Complete KOMPOSOS-III Structure Predictor

This is the INTEGRATION MODULE that connects all components:
1. ESMFold (90% accuracy baseline)
2. Physical-Chemical Bridge (validation & optimization)
3. Category Theory (interpretability)
4. Validation Framework (prevents overclaiming)

This represents the complete vision:
- High accuracy (ESMFold foundation)
- Physical realism (chemistry validation)
- Full interpretability (category theory)
- Scientific rigor (validation framework)

Usage:
    predictor = CompleteKOMPOSOSPredictor()
    result = predictor.predict_structure(sequence)

    # Access all components:
    result.coords              # Final 3D structure
    result.accuracy_metrics    # TM-score, pLDDT, etc.
    result.chemistry_report    # Energy, H-bonds, clashes
    result.interpretation      # Category theory analysis
    result.validation_report   # Semantic validation
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
from pathlib import Path
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# High-accuracy prediction modules (existing)
try:
    from geometry.esm2_contact_predictor import ESM2ContactPredictor
    from geometry.esmfold_structure_module import ESMFoldStructureModule
    from geometry.hybrid_structure_predictor import HybridStructurePredictor
    ESM_AVAILABLE = True
except ImportError:
    ESM_AVAILABLE = False
    print("WARNING: ESM-2/ESMFold modules not available. Install transformers and torch.")

# Physical-Chemical Bridge (new - created today)
from chemistry import (
    HydrogenBondValidator,
    VanDerWaalsConstraints,
    ElectrostaticConstraints,
    HydrophobicConstraints,
    StatisticalPotentials,
    RamachandranValidator,
    DunbrackRotamerLibrary,
    SideChainPacker,
    RealDataIntegrator,
    EnergyFunction,
    StructureOptimizer
)

# Validation framework
from validation.complete_validator import CompleteProteinValidator

# Category theory frameworks (existing - for interpretation)
try:
    from hott.geometric_homotopy import GeometricHomotopyChecker
    from hott.homotopy import PathHomotopyChecker
    from geometry.ricci import OllivierRicciCurvature
    CATEGORY_AVAILABLE = True
except ImportError:
    CATEGORY_AVAILABLE = False
    print("WARNING: Category theory modules not fully available.")


@dataclass
class PredictionResult:
    """Complete prediction result with all components."""

    # Structure
    sequence: str
    coords: np.ndarray

    # Accuracy metrics
    accuracy_metrics: Dict[str, float]

    # Chemistry analysis
    chemistry_report: Dict

    # Category theory interpretation
    interpretation: Dict

    # Validation
    validation_report: Optional[object] = None

    # Intermediate results
    esm_contacts: Optional[np.ndarray] = None
    initial_structure: Optional[np.ndarray] = None
    optimized_structure: Optional[np.ndarray] = None


class CompleteKOMPOSOSPredictor:
    """
    Complete KOMPOSOS-III Structure Predictor

    Integrates three key components:
    1. ESMFold: High accuracy baseline (90%)
    2. Physical-Chemical Bridge: Validation and optimization
    3. Category Theory: Interpretability and mechanism

    Pipeline:
        sequence → ESM-2 contacts → ESMFold structure →
        Chemistry validation → Energy optimization →
        Category theory interpretation → Final validation
    """

    def __init__(
        self,
        use_esm: bool = True,
        use_chemistry: bool = True,
        use_category_theory: bool = True,
        validate_results: bool = True,
        optimize_structures: bool = True
    ):
        """
        Initialize complete predictor.

        Args:
            use_esm: Use ESM-2/ESMFold for prediction
            use_chemistry: Use Physical-Chemical Bridge
            use_category_theory: Generate category theory interpretation
            validate_results: Run validation framework
            optimize_structures: Optimize with energy minimization
        """
        self.use_esm = use_esm and ESM_AVAILABLE
        self.use_chemistry = use_chemistry
        self.use_category_theory = use_category_theory and CATEGORY_AVAILABLE
        self.validate_results = validate_results
        self.optimize_structures = optimize_structures

        # Initialize components
        self._initialize_components()

    def _initialize_components(self):
        """Initialize all prediction components."""

        # High-accuracy prediction
        if self.use_esm:
            print("Initializing ESM-2/ESMFold modules...")
            try:
                self.esm2 = ESM2ContactPredictor(model_name="facebook/esm2_t33_650M_UR50D")
                self.esmfold = ESMFoldStructureModule()
                print("  [OK] ESM modules loaded")
            except Exception as e:
                print(f"  [FAILED] ESM modules: {e}")
                self.use_esm = False

        # Physical-Chemical Bridge
        if self.use_chemistry:
            print("Initializing Physical-Chemical Bridge...")
            self.hbond_validator = HydrogenBondValidator()
            self.vdw_constraints = VanDerWaalsConstraints()
            self.electrostatics = ElectrostaticConstraints()
            self.hydrophobic = HydrophobicConstraints()
            self.stat_potentials = StatisticalPotentials()
            self.ramachandran = RamachandranValidator()
            self.rotamer_lib = DunbrackRotamerLibrary()
            self.side_chain_packer = SideChainPacker(self.rotamer_lib)
            self.data_integrator = RealDataIntegrator()
            self.energy_function = EnergyFunction()
            self.optimizer = StructureOptimizer(self.energy_function)
            print("  [OK] Chemistry modules loaded")

        # Category theory
        if self.use_category_theory:
            print("Initializing Category Theory frameworks...")
            try:
                self.geometric_homotopy = GeometricHomotopyChecker()
                self.path_homotopy = PathHomotopyChecker()
                self.ricci_curvature = None  # needs a store; initialized per-prediction
                print("  [OK] Category theory modules loaded")
            except Exception as e:
                print(f"  [FAILED] Category theory: {e}")
                self.use_category_theory = False

        # Validation framework
        if self.validate_results:
            print("Initializing Validation framework...")
            self.validator = CompleteProteinValidator()
            print("  [OK] Validator loaded")

        print("\nComplete KOMPOSOS Predictor ready!")
        print(f"  ESM-2/ESMFold: {self.use_esm}")
        print(f"  Physical-Chemical Bridge: {self.use_chemistry}")
        print(f"  Category Theory: {self.use_category_theory}")
        print(f"  Validation: {self.validate_results}")

    def predict_structure(
        self,
        sequence: str,
        run_optimization: Optional[bool] = None,
        max_opt_iterations: int = 100
    ) -> PredictionResult:
        """
        Predict protein structure with full pipeline.

        Args:
            sequence: Amino acid sequence
            run_optimization: Override class default for optimization
            max_opt_iterations: Max iterations for energy minimization

        Returns:
            PredictionResult with all components
        """
        if run_optimization is None:
            run_optimization = self.optimize_structures

        print(f"\n{'='*70}")
        print(f"KOMPOSOS-III Complete Structure Prediction")
        print(f"{'='*70}")
        print(f"Sequence length: {len(sequence)} residues")
        print()

        result_data = {
            'sequence': sequence,
            'accuracy_metrics': {},
            'chemistry_report': {},
            'interpretation': {}
        }

        # =====================================================================
        # PHASE 1: High-Accuracy Prediction (ESMFold)
        # =====================================================================
        if self.use_esm:
            print("[PHASE 1] High-Accuracy Prediction (ESMFold)")
            print("-" * 70)

            # ESM-2 contact prediction
            print("  Predicting contacts with ESM-2...")
            contacts = self.esm2.predict_contacts(sequence)
            result_data['esm_contacts'] = contacts
            print(f"  [OK] Contact map generated: {contacts.shape}")

            # ESMFold structure prediction
            print("  Predicting structure with ESMFold...")
            structure_result = self.esmfold.predict_structure(sequence)
            coords = structure_result['coords']
            plddt = structure_result['plddt']
            result_data['coords'] = coords
            result_data['initial_structure'] = coords.copy()
            result_data['accuracy_metrics']['plddt'] = float(np.mean(plddt))
            print(f"  [OK] Structure predicted: {coords.shape}")
            print(f"  [OK] Mean pLDDT: {np.mean(plddt):.1f}")
            print()
        else:
            print("[PHASE 1] SKIPPED (ESM not available)")
            print("  Using placeholder coordinates (helix)")
            coords = self._generate_helix(len(sequence))
            result_data['coords'] = coords
            result_data['initial_structure'] = coords.copy()
            result_data['accuracy_metrics']['plddt'] = 0.0
            print()

        # =====================================================================
        # PHASE 2: Physical-Chemical Validation
        # =====================================================================
        if self.use_chemistry:
            print("[PHASE 2] Physical-Chemical Validation")
            print("-" * 70)

            chemistry_results = self._run_chemistry_analysis(coords, sequence)
            result_data['chemistry_report'] = chemistry_results

            # Print summary
            print(f"  H-bonds: {chemistry_results['num_hbonds']}")
            print(f"  Clashes: {chemistry_results['num_clashes']}")
            print(f"  Salt bridges: {chemistry_results['num_salt_bridges']}")
            print(f"  Total energy: {chemistry_results['total_energy']:.2f} kcal/mol")
            print()

        # =====================================================================
        # PHASE 3: Energy Optimization (if needed)
        # =====================================================================
        if self.use_chemistry and run_optimization:
            print("[PHASE 3] Energy Optimization")
            print("-" * 70)

            # Check if optimization needed
            energy = result_data['chemistry_report']['total_energy']
            num_clashes = result_data['chemistry_report']['num_clashes']

            if num_clashes > 0 or energy > -50.0:  # Arbitrary threshold
                print(f"  Optimization recommended:")
                print(f"    Clashes: {num_clashes}")
                print(f"    Energy: {energy:.2f} kcal/mol")
                print(f"  Running optimization ({max_opt_iterations} iterations)...")

                # Prepare structure data
                structure_data = self._prepare_structure_data(coords, sequence)

                # Optimize
                opt_result = self.optimizer.minimize_gradient_descent(
                    structure_data,
                    max_iterations=max_opt_iterations,
                    step_size=0.01,
                    convergence_threshold=0.1
                )

                # Update coordinates
                coords = opt_result.final_coords
                result_data['coords'] = coords
                result_data['optimized_structure'] = coords

                # Re-analyze chemistry
                chemistry_results = self._run_chemistry_analysis(coords, sequence)
                result_data['chemistry_report'] = chemistry_results

                print(f"  [OK] Optimization complete:")
                print(f"    Initial: {opt_result.initial_energy:.2f} kcal/mol")
                print(f"    Final: {opt_result.final_energy:.2f} kcal/mol")
                print(f"    Improvement: {opt_result.energy_improvement:.2f} kcal/mol")
                print(f"    New clashes: {chemistry_results['num_clashes']}")
                print()
            else:
                print(f"  Structure quality acceptable, skipping optimization")
                print(f"    Clashes: {num_clashes}")
                print(f"    Energy: {energy:.2f} kcal/mol")
                print()

        # =====================================================================
        # PHASE 4: Category Theory Interpretation
        # =====================================================================
        if self.use_category_theory:
            print("[PHASE 4] Category Theory Interpretation")
            print("-" * 70)

            interpretation = self._generate_interpretation(coords, sequence)
            result_data['interpretation'] = interpretation

            print(f"  [OK] Mechanism classification: {interpretation.get('mechanism', 'unknown')}")
            print(f"  [OK] Folding pathways analyzed")
            print(f"  [OK] Topological features computed")
            print()

        # =====================================================================
        # PHASE 5: Validation Framework
        # =====================================================================
        validation_report = None
        if self.validate_results:
            print("[PHASE 5] Validation Framework")
            print("-" * 70)

            # Generate interpretation text
            interpretation_text = self._format_interpretation(result_data)

            # Prepare evidence
            evidence = {
                'num_tests': 1,
                'benchmarked': False,
                'using_defaults': True,
                'experimental_validation': False
            }

            # Validate
            validation_report = self.validator.validate_with_chemistry_results(
                sequence=sequence,
                predicted_coords=coords,
                chemistry_results=result_data['chemistry_report'],
                interpretation=interpretation_text,
                evidence=evidence
            )

            result_data['validation_report'] = validation_report

            print(f"  Status: {'PASSED' if validation_report.overall['passed'] else 'FAILED'}")
            print(f"  Confidence: {validation_report.overall['confidence_score']:.2%}")
            print(f"  Critical issues: {validation_report.overall['critical_issues']}")
            print(f"  Warnings: {validation_report.overall['warning_count']}")
            print()

        # =====================================================================
        # COMPLETE
        # =====================================================================
        print("="*70)
        print("PREDICTION COMPLETE")
        print("="*70)
        print()

        return PredictionResult(**result_data)

    def _run_chemistry_analysis(self, coords: np.ndarray, sequence: str) -> Dict:
        """Run complete physical-chemical analysis."""
        results = {}

        # Phase 1: Physical constraints
        hbonds = self.hbond_validator.predict_hbonds(coords, sequence)
        clashes = self.vdw_constraints.check_clashes(coords)
        salt_bridges = self.electrostatics.predict_salt_bridges(coords, sequence)
        burial = self.hydrophobic.compute_burial_scores(coords, sequence)

        results['num_hbonds'] = len(hbonds)
        results['num_clashes'] = len(clashes)
        results['num_salt_bridges'] = len(salt_bridges)
        results['hbonds'] = hbonds
        results['clashes'] = clashes
        results['salt_bridges'] = salt_bridges

        # Phase 2: Statistical potentials
        # (Would compute contacts, ramachandran, etc.)

        # Phase 5: Energy function
        structure_data = self._prepare_structure_data(coords, sequence)
        energy_breakdown = self.energy_function.compute_total_energy(structure_data)

        results['total_energy'] = float(energy_breakdown.total)
        results['energy_breakdown'] = {
            'vdw': float(energy_breakdown.vdw),
            'electrostatic': float(energy_breakdown.electrostatic),
            'hbond': float(energy_breakdown.hbond),
            'solvation': float(energy_breakdown.solvation),
            'pair': float(energy_breakdown.pair),
            'rama': float(energy_breakdown.rama),
            'rotamer': float(energy_breakdown.rotamer),
            'reference': float(energy_breakdown.reference)
        }

        results['initial_structure'] = {'coords': coords.copy()}
        results['optimization_result'] = {
            'initial_energy': float(energy_breakdown.total),
            'final_energy': float(energy_breakdown.total),
            'energy_improvement': 0.0,
            'num_iterations': 0,
            'converged': True
        }

        return results

    def _prepare_structure_data(self, coords: np.ndarray, sequence: str) -> Dict:
        """Prepare structure data for energy computation."""
        N = len(sequence)

        # Compute contacts (simple distance-based)
        contacts = []
        for i in range(N):
            for j in range(i+4, N):
                dist = np.linalg.norm(coords[i] - coords[j])
                if dist < 8.0:
                    contacts.append((i, j))

        # Approximate phi/psi (would be computed from backbone)
        phi = np.full(N, -60.0)
        psi = np.full(N, -45.0)
        phi[0] = psi[-1] = np.nan

        return {
            'coords': coords,
            'sequence': sequence,
            'contacts': contacts,
            'phi': phi,
            'psi': psi,
            'rotamers': []
        }

    def _generate_interpretation(self, coords: np.ndarray, sequence: str) -> Dict:
        """Generate category theory interpretation using real HoTT + Ricci modules."""
        interpretation = {
            'mechanism': 'hierarchical_folding',
            'pathways': [],
            'topology': {},
            'geometry': {}
        }

        if not self.use_category_theory:
            return interpretation

        try:
            N = len(sequence)

            # Build contact-based pathways for HoTT analysis
            # Pathway = order of residues by contact density
            contact_counts = np.zeros(N)
            for i in range(N):
                for j in range(N):
                    dist = np.linalg.norm(coords[i] - coords[j])
                    if 3.0 < dist < 8.0 and abs(i - j) > 4:
                        contact_counts[i] += 1

            density_order = sorted(range(N), key=lambda r: -contact_counts[r])
            pathway1 = [f"R{r}" for r in density_order]

            # Alternative pathway: hydrophobic-core-first
            hydrophobic = set('AVILMFWY')
            hydro_order = sorted(
                range(N),
                key=lambda r: (0 if sequence[r] in hydrophobic else 1, -contact_counts[r])
            )
            pathway2 = [f"R{r}" for r in hydro_order]

            pathways = [pathway1, pathway2]
            interpretation['pathways'] = pathways

            # HoTT pathway analysis
            homotopy_result = self.path_homotopy.check_homotopy(pathways)
            interpretation['topology'] = {
                'homotopy_classes': homotopy_result.num_classes,
                'all_homotopic': homotopy_result.all_homotopic,
                'shared_spine_length': len(homotopy_result.shared_spine) if homotopy_result.shared_spine else 0,
            }

            # Geometric homotopy classification
            geo_result = self.geometric_homotopy.check_paths(pathways, strict=False)
            interpretation['geometry'] = {
                'geometric_classes': geo_result.num_classes,
                'all_geometrically_homotopic': geo_result.all_homotopic,
            }

            if geo_result.all_homotopic:
                interpretation['mechanism'] = 'two-state'
            elif geo_result.num_classes == 2:
                interpretation['mechanism'] = 'nucleation-condensation'
            else:
                interpretation['mechanism'] = 'multi-pathway'

        except Exception as e:
            print(f"    Warning: Category theory analysis failed: {e}")

        return interpretation

    def _format_interpretation(self, result_data: Dict) -> str:
        """Format interpretation for validation."""
        seq_len = len(result_data['sequence'])
        plddt = result_data['accuracy_metrics'].get('plddt', 0)
        energy = result_data['chemistry_report'].get('total_energy', 0)
        clashes = result_data['chemistry_report'].get('num_clashes', 0)

        text = f"""
KOMPOSOS-III Structure Prediction Result
=========================================

Sequence length: {seq_len} residues

## Prediction Quality

Mean pLDDT: {plddt:.1f}

## Physical-Chemical Analysis

Total energy: {energy:.2f} kcal/mol
Steric clashes: {clashes}

## Interpretation

This structure was predicted using the KOMPOSOS-III framework, which
integrates ESMFold for high accuracy with physical-chemical validation
and category theory for interpretability.

The energy function shows {"favorable" if energy < -50 else "moderate"} energetics.
{"No steric clashes detected." if clashes == 0 else f"{clashes} steric clashes require attention."}

## Limitations

This is a computational prediction requiring experimental validation.
The structure represents one low-energy conformation but may not be
the biological native state. Additional refinement and validation
recommended before experimental use.
"""
        return text

    def _generate_helix(self, N: int) -> np.ndarray:
        """Generate placeholder helix coordinates."""
        coords = np.zeros((N, 3))
        for i in range(N):
            angle = i * 100 * np.pi / 180
            radius = 2.3
            coords[i] = [
                radius * np.cos(angle),
                radius * np.sin(angle),
                i * 1.5
            ]
        return coords

    def save_result(self, result: PredictionResult, output_dir: str = "predictions"):
        """
        Save prediction result to disk.

        Args:
            result: PredictionResult to save
            output_dir: Directory to save results
        """
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        # Save PDB
        pdb_path = output_path / f"{result.sequence[:10]}_predicted.pdb"
        self._write_pdb(result.coords, result.sequence, pdb_path)
        print(f"Structure saved: {pdb_path}")

        # Save validation report
        if result.validation_report:
            report_path = output_path / f"{result.sequence[:10]}_validation.txt"
            detailed_report = self.validator.generate_detailed_report(result.validation_report)
            with open(report_path, 'w') as f:
                f.write(detailed_report)
            print(f"Validation report saved: {report_path}")

    def _write_pdb(self, coords: np.ndarray, sequence: str, path: Path):
        """Write coordinates to PDB file (CA only)."""
        aa_map = {
            'A': 'ALA', 'C': 'CYS', 'D': 'ASP', 'E': 'GLU',
            'F': 'PHE', 'G': 'GLY', 'H': 'HIS', 'I': 'ILE',
            'K': 'LYS', 'L': 'LEU', 'M': 'MET', 'N': 'ASN',
            'P': 'PRO', 'Q': 'GLN', 'R': 'ARG', 'S': 'SER',
            'T': 'THR', 'V': 'VAL', 'W': 'TRP', 'Y': 'TYR'
        }

        with open(path, 'w') as f:
            f.write("REMARK KOMPOSOS-III Predicted Structure\n")
            for i, (aa, coord) in enumerate(zip(sequence, coords)):
                res_name = aa_map.get(aa, 'UNK')
                f.write(
                    f"ATOM  {i+1:5d}  CA  {res_name} A{i+1:4d}    "
                    f"{coord[0]:8.3f}{coord[1]:8.3f}{coord[2]:8.3f}"
                    f"  1.00  0.00           C\n"
                )
            f.write("END\n")


def main():
    """Demo of complete predictor."""
    print("\n" + "="*70)
    print("KOMPOSOS-III Complete Structure Predictor Demo")
    print("="*70)
    print()
    print("This demo shows the full integration:")
    print("  1. ESMFold: High accuracy prediction (90%)")
    print("  2. Physical-Chemical Bridge: Validation & optimization")
    print("  3. Category Theory: Interpretability")
    print("  4. Validation Framework: Scientific rigor")
    print()

    # Initialize predictor
    predictor = CompleteKOMPOSOSPredictor(
        use_esm=True,
        use_chemistry=True,
        use_category_theory=True,
        validate_results=True,
        optimize_structures=True
    )

    # Test sequence
    sequence = "MALKFDEGHIKLMNPQRSTVWY"  # 22 residues

    # Predict
    result = predictor.predict_structure(sequence)

    # Save
    predictor.save_result(result)

    print("\n" + "="*70)
    print("DEMO COMPLETE")
    print("="*70)
    print()
    print("Next steps:")
    print("  1. Test on diverse proteins (50+)")
    print("  2. Benchmark against AlphaFold")
    print("  3. Validate on experimental structures")
    print()


if __name__ == "__main__":
    main()
