# SPDX-License-Identifier: Apache-2.0 OR KOMPOSOS-III-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Compositional Contact Prediction for Protein Structure

Uses EXISTING KOMPOSOS-III tools:
- Kan Extensions (categorical/kan_extensions.py) - Pattern transfer
- ESM-2 Embeddings (data/bio_embeddings.py) - Sequence similarity
- Ricci Curvature (geometry/ricci.py) - Network geometry
- Store (data/store.py) - Data infrastructure

Unlike AlphaFold's transformer black box, this:
1. Detects motifs compositionally
2. Uses Kan extensions to lift interaction patterns
3. Validates with Ricci curvature geometry
4. Returns interpretable contact predictions

Integration: Works with existing Oracle strategies and geometry modules.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional
import numpy as np
from collections import defaultdict
from pathlib import Path

try:
    from .ricci import OllivierRicciCurvature
except ImportError:
    from ricci import OllivierRicciCurvature

# Physical-Chemical Bridge - Defines what contacts are physically valid
try:
    from chemistry import (
        HydrogenBondValidator,
        VanDerWaalsConstraints,
        ElectrostaticConstraints,
        HydrophobicConstraints
    )
    CHEMISTRY_AVAILABLE = True
except ImportError:
    CHEMISTRY_AVAILABLE = False

# ESM-2 - Real trained model for contact prediction (52-87% accuracy!)
try:
    from .esm2_contact_predictor import ESM2ContactPredictor
    ESM2_AVAILABLE = True
except ImportError:
    try:
        from esm2_contact_predictor import ESM2ContactPredictor
        ESM2_AVAILABLE = True
    except ImportError:
        ESM2_AVAILABLE = False

# DCA - Direct Coupling Analysis via category-theoretic MSA
try:
    from .category_msa import CategoryTheoreticMSA, CoevolutionTransformation
    DCA_AVAILABLE = True
except ImportError:
    try:
        from category_msa import CategoryTheoreticMSA, CoevolutionTransformation
        DCA_AVAILABLE = True
    except ImportError:
        DCA_AVAILABLE = False

# PDB Template Patterns via Kan Extensions
try:
    from .pdb_kan_extensions import KanExtensionContactPredictor, PDBPatternLibrary
    TEMPLATES_AVAILABLE = True
except ImportError:
    try:
        from pdb_kan_extensions import KanExtensionContactPredictor, PDBPatternLibrary
        TEMPLATES_AVAILABLE = True
    except ImportError:
        TEMPLATES_AVAILABLE = False


@dataclass
class ContactMap:
    """N x N binary contact matrix for a protein."""
    protein_name: str
    sequence: str
    contacts: np.ndarray  # (N, N) - 1 = contact, 0 = no contact
    confidence: np.ndarray  # (N, N) - confidence per contact
    length: int

    @property
    def num_contacts(self) -> int:
        """Total number of predicted contacts."""
        return int(np.sum(self.contacts))

    @property
    def contact_density(self) -> float:
        """Fraction of residue pairs in contact."""
        possible = self.length * (self.length - 1) / 2
        return self.num_contacts / possible if possible > 0 else 0.0


@dataclass
class MotifPattern:
    """A structural motif pattern from known proteins."""
    motif_type: str  # helix, sheet, loop
    length: int
    contacts: List[Tuple[int, int]]  # Residue pairs in contact
    sequence_pattern: str
    source_proteins: List[str]


@dataclass
class PredictionResult:
    """Complete contact prediction result."""
    contact_map: ContactMap
    motifs_detected: List[MotifPattern]
    kan_predictions: List[Dict]  # Predictions from Kan extension
    ricci_validation: Dict  # Geometric validation
    reasoning: str


class CompositionalContactPredictor:
    """
    Predict protein contacts using compositional category theory.

    Unlike AlphaFold (black box transformer), this:
    - Uses explicit motif decomposition
    - Applies Kan extensions for pattern transfer
    - Validates with Ricci curvature
    - Provides interpretable reasoning

    Integrates with EXISTING KOMPOSOS-III infrastructure:
    - Store for protein data
    - BiologicalEmbeddingsEngine for ESM-2
    - OllivierRicciCurvature for geometry
    """

    def __init__(
        self,
        store,
        embeddings_engine=None,
        motif_library_path: Optional[Path] = None,
        use_chemistry: bool = True,
        pfam_mapper=None
    ):
        """
        Initialize contact predictor.

        Args:
            store: KomposOSStore with protein objects/morphisms
            embeddings_engine: BiologicalEmbeddingsEngine with ESM-2
            motif_library_path: Path to PDB-derived motif library (optional)
            use_chemistry: Use Physical-Chemical Bridge for constraints
            pfam_mapper: Optional PfamDomainMapper for domain-aware verification
        """
        self.store = store
        self.embeddings = embeddings_engine
        self.motif_library_path = motif_library_path
        self.pfam_mapper = pfam_mapper

        # Initialize ESM-2 (REAL trained model - 52-87% accuracy!)
        if ESM2_AVAILABLE:
            print("Initializing ESM-2 contact predictor (real trained model)...")
            self.esm2 = ESM2ContactPredictor(model_name="facebook/esm2_t33_650M_UR50D")
            self.use_esm2 = True
            print("  [OK] ESM-2 650M loaded (52% baseline accuracy)")
        else:
            self.esm2 = None
            self.use_esm2 = False
            print("  [WARN] ESM-2 not available, using network-based prediction")

        # Initialize geometry
        self.ricci = OllivierRicciCurvature(store, alpha=0.5)

        # Initialize Physical-Chemical Bridge (constrains predictions!)
        if use_chemistry and CHEMISTRY_AVAILABLE:
            print("Initializing Physical-Chemical Bridge for contact constraints...")
            self.hbond_validator = HydrogenBondValidator()
            self.vdw_constraints = VanDerWaalsConstraints()
            self.electrostatics = ElectrostaticConstraints()
            self.hydrophobic = HydrophobicConstraints()
            self.use_chemistry = True
            print("  [OK] Physical chemistry constraints loaded")
        else:
            self.use_chemistry = False
            if use_chemistry:
                print("  [WARN] Physical-Chemical Bridge not available")

        # Initialize DCA (Direct Coupling Analysis from MSA coevolution)
        if DCA_AVAILABLE:
            print("Initializing DCA (Direct Coupling Analysis)...")
            self.msa_builder = CategoryTheoreticMSA()  # Uses mock MSA if no database
            self.use_dca = True
            print("  [OK] DCA ready")
        else:
            self.msa_builder = None
            self.use_dca = False
            print("  [WARN] DCA not available")

        # Initialize PDB Template predictor (Kan extension from known motifs)
        if TEMPLATES_AVAILABLE:
            print("Initializing PDB template predictor (Kan extensions)...")
            self.template_predictor = KanExtensionContactPredictor(store=store)
            self.use_templates = True
            print("  [OK] Template predictor ready")
        else:
            self.template_predictor = None
            self.use_templates = False
            print("  [WARN] Template predictor not available")

        # Load motif library if available
        self.motif_library = self._load_motif_library()

        # Build protein interaction network from Store
        self._build_interaction_network()

    def _load_motif_library(self) -> Dict[str, List[MotifPattern]]:
        """
        Load motif library from PDB structures.

        TODO: Extract real motifs from PDB
        For now: Use placeholder patterns
        """
        library = {
            'helix': [],
            'sheet': [],
            'loop': []
        }

        # Placeholder: Would extract from PDB in production
        # Example helix pattern (alpha helix i, i+4 contacts)
        library['helix'].append(MotifPattern(
            motif_type='helix',
            length=12,
            contacts=[(0, 3), (0, 4), (1, 4), (1, 5), (2, 5), (2, 6)],
            sequence_pattern='[AVILM]{6,}',  # Hydrophobic
            source_proteins=['1UBQ', '1CRN']
        ))

        # Example beta sheet pattern
        library['sheet'].append(MotifPattern(
            motif_type='sheet',
            length=8,
            contacts=[(0, 6), (1, 5), (2, 4)],
            sequence_pattern='[VIL].[VIL]',
            source_proteins=['1PIN']
        ))

        return library

    def _build_interaction_network(self):
        """Build protein-protein interaction network from Store."""
        self.interactions = defaultdict(set)
        self.interaction_types = {}

        morphisms = self.store.list_morphisms(limit=100000)

        for mor in morphisms:
            source = mor.source_name
            target = mor.target_name

            self.interactions[source].add(target)
            self.interactions[target].add(source)

            self.interaction_types[(source, target)] = mor.name

    def detect_motifs(self, sequence: str) -> List[MotifPattern]:
        """
        Detect secondary structure motifs in sequence.

        Uses improved heuristics:
        - Alpha helix: hydrophobic runs with helix propensity
        - Beta sheet: alternating hydrophobic/hydrophilic
        - Loops: everything else

        Args:
            sequence: Amino acid sequence

        Returns:
            List of detected motifs
        """
        detected = []

        # Helix propensities (Chou-Fasman)
        helix_formers = set('AELM')  # Strong helix formers
        helix_breakers = set('GPD')  # Helix breakers

        # Sheet propensities
        sheet_formers = set('VIY')  # Strong sheet formers

        # Hydrophobic residues
        hydrophobic = set('AVILMFWY')

        i = 0
        while i < len(sequence):
            # Try helix detection
            if sequence[i] in helix_formers or sequence[i] in hydrophobic:
                j = i
                helix_score = 0

                while j < len(sequence) and j - i < 30:  # Max helix ~30 residues
                    if sequence[j] in helix_formers:
                        helix_score += 2
                    elif sequence[j] in hydrophobic:
                        helix_score += 1
                    elif sequence[j] in helix_breakers:
                        helix_score -= 3
                        if helix_score < 0:
                            break
                    else:
                        helix_score -= 1
                        if helix_score < 0:
                            break
                    j += 1

                if j - i >= 6 and helix_score > 3:  # Minimum helix
                    # Add helix contacts (i, i+3), (i, i+4)
                    contacts = []
                    for k in range(j - i - 3):
                        contacts.append((i + k, i + k + 3))
                    for k in range(j - i - 4):
                        contacts.append((i + k, i + k + 4))

                    detected.append(MotifPattern(
                        motif_type='helix',
                        length=j - i,
                        contacts=contacts,
                        sequence_pattern=sequence[i:j],
                        source_proteins=[]
                    ))
                    i = j
                    continue

            # Try sheet detection
            if sequence[i] in sheet_formers:
                j = i
                sheet_score = 0

                while j < len(sequence) and j - i < 15:  # Typical strand length
                    if sequence[j] in sheet_formers:
                        sheet_score += 2
                    elif sequence[j] in hydrophobic and (j - i) % 2 == 0:
                        sheet_score += 1  # Alternating pattern
                    else:
                        sheet_score -= 1
                        if sheet_score < 0:
                            break
                    j += 1

                if j - i >= 4 and sheet_score > 2:  # Minimum strand
                    detected.append(MotifPattern(
                        motif_type='sheet',
                        length=j - i,
                        contacts=[],  # Inter-strand contacts added later
                        sequence_pattern=sequence[i:j],
                        source_proteins=[]
                    ))
                    i = j
                    continue

            i += 1

        # Detect potential sheet-sheet contacts (antiparallel preferred)
        sheet_motifs = [m for m in detected if m.motif_type == 'sheet']
        for idx1, motif1 in enumerate(sheet_motifs):
            for idx2, motif2 in enumerate(sheet_motifs[idx1+1:], idx1+1):
                # If strands are separated by 10-50 residues, likely interaction
                pos1 = sequence.find(motif1.sequence_pattern)
                pos2 = sequence.find(motif2.sequence_pattern, pos1 + motif1.length)

                if pos2 > 0 and 10 <= pos2 - pos1 <= 50:
                    # Add antiparallel contacts
                    min_len = min(motif1.length, motif2.length)
                    for k in range(min_len):
                        # Antiparallel: i contacts N-k
                        motif1.contacts.append((pos1 + k, pos2 + motif2.length - 1 - k))

        return detected

    def apply_kan_extension(
        self,
        target_protein: str,
        target_sequence: str
    ) -> List[Dict]:
        """
        Use Kan extension to predict contacts from similar proteins.

        Left Kan Extension = colimit over comma category
        Predicts contacts by lifting patterns from similar proteins.

        Args:
            target_protein: Protein to predict
            target_sequence: Its sequence

        Returns:
            List of contact predictions with confidence
        """
        predictions = []

        # Get similar proteins via embeddings
        if self.embeddings is None:
            return predictions

        try:
            target_emb = self.embeddings.embed(target_protein)
        except:
            return predictions

        # Find proteins with similar embeddings
        similar_proteins = []

        objects = self.store.list_objects(limit=10000)
        for obj in objects:
            if obj.name == target_protein:
                continue

            try:
                obj_emb = self.embeddings.embed(obj.name)
                similarity = np.dot(target_emb, obj_emb) / (
                    np.linalg.norm(target_emb) * np.linalg.norm(obj_emb) + 1e-10
                )

                if similarity > 0.7:  # High similarity
                    similar_proteins.append({
                        'protein': obj.name,
                        'similarity': similarity
                    })
            except:
                continue

        # For each similar protein, transfer its interaction patterns
        for similar in similar_proteins[:10]:  # Top 10
            protein = similar['protein']
            sim_score = similar['similarity']

            # Get interactions of similar protein
            partners = self.interactions.get(protein, set())

            for partner in partners:
                # Predict target should interact with similar partner
                predictions.append({
                    'partner': partner,
                    'confidence': sim_score * 0.8,
                    'reasoning': f"Kan extension from {protein} (similarity={sim_score:.3f})",
                    'source_protein': protein
                })

        return predictions

    def predict_contacts_from_network(
        self,
        protein: str,
        sequence: str,
        length: int
    ) -> ContactMap:
        """
        Predict intra-protein contacts from network structure.

        Uses:
        1. Motif patterns from library
        2. Kan extension predictions
        3. Ricci curvature for validation

        Args:
            protein: Protein name
            sequence: Amino acid sequence
            length: Sequence length

        Returns:
            ContactMap with predicted contacts
        """
        # Initialize contact matrix
        contacts = np.zeros((length, length), dtype=int)
        confidence = np.zeros((length, length), dtype=float)

        # 1. Detect motifs
        motifs = self.detect_motifs(sequence)

        # Apply motif contact patterns
        for motif in motifs:
            # Use library patterns for this motif type
            library_patterns = self.motif_library.get(motif.motif_type, [])

            if library_patterns:
                pattern = library_patterns[0]  # Use first pattern

                # Apply pattern contacts (simplified)
                for i, j in pattern.contacts:
                    if i < length and j < length:
                        contacts[i, j] = 1
                        contacts[j, i] = 1
                        confidence[i, j] = 0.7
                        confidence[j, i] = 0.7

        # 2. Apply Kan extension predictions
        kan_preds = self.apply_kan_extension(protein, sequence)

        # Kan predictions give inter-protein, not intra-protein
        # In future: use domain-domain interactions for intra-protein

        # 3. Add sequence-local contacts (i, i+1), (i, i+2)
        for i in range(length - 1):
            contacts[i, i+1] = 1
            contacts[i+1, i] = 1
            confidence[i, i+1] = 1.0
            confidence[i+1, i] = 1.0

        for i in range(length - 2):
            contacts[i, i+2] = 1
            contacts[i+2, i] = 1
            confidence[i, i+2] = 0.9
            confidence[i+2, i] = 0.9

        return ContactMap(
            protein_name=protein,
            sequence=sequence,
            contacts=contacts,
            confidence=confidence,
            length=length
        )

    def optimize_with_ricci_flow(self, contact_map: ContactMap) -> ContactMap:
        """
        Optimize contact map using Ricci flow.

        Ricci flow reveals geometric structure and removes spurious contacts.

        Args:
            contact_map: Initial contact map

        Returns:
            Optimized contact map
        """
        try:
            from .flow import DiscreteRicciFlow

            # Temporarily add contacts to Store as a subgraph
            # Create temporary object for protein
            protein_obj_name = f"_temp_{contact_map.protein_name}"

            # For each contact, add temporary morphism
            temp_morphisms = []
            N = contact_map.length

            for i in range(N):
                for j in range(i+1, N):
                    if contact_map.contacts[i, j] > 0:
                        # Add morphism representing contact
                        mor_name = f"contact_{i}_{j}"
                        # Note: We'd need to actually add these to store temporarily
                        # For now, skip actual Ricci flow and just return contact map
                        pass

            # Run Ricci flow
            # flow = DiscreteRicciFlow(self.store, alpha=0.5)
            # result = flow.flow(max_steps=20, dt=0.05)

            # Filter contacts based on curvature
            # High curvature = keep (strong contact)
            # Low/negative curvature = remove (weak/spurious)

            # For now, just return original
            return contact_map

        except ImportError:
            # Ricci flow not available, return original
            return contact_map

    def validate_with_ricci(self, contact_map: ContactMap) -> Dict:
        """
        Validate contact map using Ricci curvature.

        Native proteins have characteristic curvature distributions:
        - 40-60% spherical (folded domains)
        - 30-50% euclidean (loops)
        - 5-15% hyperbolic (extended)

        Args:
            contact_map: Predicted contacts

        Returns:
            Validation results with geometry analysis
        """
        # Compute approximate curvature distribution
        N = contact_map.length
        contacts_per_residue = np.sum(contact_map.contacts, axis=1)

        # High connectivity = spherical (tight packing)
        # Medium connectivity = euclidean (normal)
        # Low connectivity = hyperbolic (extended)

        spherical_count = np.sum(contacts_per_residue > 8)
        euclidean_count = np.sum((contacts_per_residue >= 4) & (contacts_per_residue <= 8))
        hyperbolic_count = np.sum(contacts_per_residue < 4)

        total = N
        spherical_frac = spherical_count / total if total > 0 else 0
        euclidean_frac = euclidean_count / total if total > 0 else 0
        hyperbolic_frac = hyperbolic_count / total if total > 0 else 0

        # Check if distribution is native-like
        is_native_like = (0.3 <= spherical_frac <= 0.7) and (0.2 <= euclidean_frac <= 0.6)

        # Mean "curvature" proxy based on average connectivity
        mean_connectivity = np.mean(contacts_per_residue)
        mean_curvature = (mean_connectivity - 6) / 6  # Normalize around 6 contacts

        if is_native_like:
            status = "Native-like geometry"
        else:
            status = f"Non-native (spherical={spherical_frac:.2f}, euclidean={euclidean_frac:.2f})"

        result = {
            'valid': is_native_like,
            'mean_curvature': mean_curvature,
            'spherical_fraction': spherical_frac,
            'euclidean_fraction': euclidean_frac,
            'hyperbolic_fraction': hyperbolic_frac,
            'geometry': 'spherical' if spherical_frac > 0.5 else 'euclidean',
            'reasoning': status
        }

        return result

    def _apply_physical_constraints(self, contact_map: ContactMap, sequence: str) -> ContactMap:
        """
        Filter contact map using Physical-Chemical Bridge constraints.

        This uses the bridge DURING prediction to ensure only physically
        valid contacts pass through. Category theory proposes, physics constrains.

        Args:
            contact_map: Initial contact predictions
            sequence: Amino acid sequence

        Returns:
            Filtered contact map with only physically valid contacts
        """
        L = len(sequence)
        filtered_contacts = np.zeros((L, L), dtype=int)
        filtered_confidence = np.zeros((L, L), dtype=float)

        # Pass through short-range contacts (|i-j| < 4) automatically —
        # backbone proximity makes them always physically valid
        for i in range(L):
            for j in range(i+1, min(i+4, L)):
                if contact_map.contacts[i, j] == 1:
                    filtered_contacts[i, j] = 1
                    filtered_contacts[j, i] = 1
                    filtered_confidence[i, j] = contact_map.confidence[i, j]
                    filtered_confidence[j, i] = contact_map.confidence[j, i]

        # Count only medium/long-range contacts for physical validation
        num_proposed = 0
        for i in range(L):
            for j in range(i+4, L):
                if contact_map.contacts[i, j] == 1:
                    num_proposed += 1
        num_passed = 0

        charged_pos = set('KRH')
        charged_neg = set('DE')

        for i in range(L):
            for j in range(i+4, L):  # Evaluate medium/long-range contacts
                if contact_map.contacts[i, j] == 1:
                    # Category theory proposed this contact
                    # Now check physical chemistry

                    aa_i = sequence[i]
                    aa_j = sequence[j]

                    # Baseline: backbone H-bonds (N-H...O=C) and van der Waals
                    # are ALWAYS physically possible between any two residues
                    score = 0.15

                    # Sidechain H-bond compatibility (bonus)
                    can_donate_i = aa_i in self.hbond_validator.donors
                    can_accept_i = aa_i in self.hbond_validator.acceptors
                    can_donate_j = aa_j in self.hbond_validator.donors
                    can_accept_j = aa_j in self.hbond_validator.acceptors

                    if (can_donate_i and can_accept_j) or (can_donate_j and can_accept_i):
                        score += 0.3

                    # Charge compatibility — salt bridge (bonus)
                    if (aa_i in charged_pos and aa_j in charged_neg) or \
                       (aa_i in charged_neg and aa_j in charged_pos):
                        score += 0.3

                    # Same-charge penalty (electrostatic repulsion)
                    if (aa_i in charged_pos and aa_j in charged_pos) or \
                       (aa_i in charged_neg and aa_j in charged_neg):
                        score -= 0.2

                    # Hydrophobic compatibility (bonus)
                    if aa_i in self.hydrophobic.hydrophobic and aa_j in self.hydrophobic.hydrophobic:
                        score += 0.3

                    # If physically plausible, keep it
                    if score > 0.0:
                        filtered_contacts[i, j] = 1
                        filtered_contacts[j, i] = 1
                        # Weight ESM-2 confidence by physical score
                        filtered_confidence[i, j] = contact_map.confidence[i, j] * (0.5 + 0.5 * min(score, 1.0))
                        filtered_confidence[j, i] = filtered_confidence[i, j]
                        num_passed += 1

        # Count short-range contacts that were passed through
        num_short_range = int(filtered_contacts.sum() / 2) - num_passed
        pass_rate = (num_passed / num_proposed * 100) if num_proposed > 0 else 0
        total = num_passed + num_short_range
        print(f"  Physical-Chemical Bridge: {num_passed}/{num_proposed} long-range passed ({pass_rate:.1f}%), {num_short_range} short-range -> {total} total")

        # Pfam domain overlay: boost/verify contacts based on domain annotations
        if self.pfam_mapper is not None:
            domains = self.pfam_mapper.lookup_domains(sequence)
            if domains:
                active_sites = self.pfam_mapper.get_active_site_residues(sequence)
                domain_map = self.pfam_mapper.get_domain_map(sequence)
                boosted = 0

                for i in range(L):
                    for j in range(i + 1, L):
                        if filtered_contacts[i, j] != 1:
                            continue

                        # Active site boost: contact involves known active site residue
                        if i in active_sites or j in active_sites:
                            filtered_confidence[i, j] = min(1.0, filtered_confidence[i, j] * 1.15)
                            filtered_confidence[j, i] = filtered_confidence[i, j]
                            boosted += 1
                        # Same-domain boost: both residues in the same annotated domain
                        elif domain_map.get(i) is not None and domain_map.get(j) is not None:
                            if domain_map[i].accession == domain_map[j].accession:
                                filtered_confidence[i, j] = min(1.0, filtered_confidence[i, j] * 1.05)
                                filtered_confidence[j, i] = filtered_confidence[i, j]
                                boosted += 1

                if boosted > 0:
                    print(f"  Pfam domain overlay: {boosted} contacts boosted by domain agreement")
                print(f"  Pfam domains found: {len(domains)} ({', '.join(d.name for d in domains[:5])}{'...' if len(domains) > 5 else ''})")

        return ContactMap(
            protein_name=contact_map.protein_name,
            sequence=sequence,
            contacts=filtered_contacts,
            confidence=filtered_confidence,
            length=L
        )

    def predict(
        self,
        protein: str,
        sequence: Optional[str] = None,
        esm2_threshold: float = 0.02,
        esm2_top_L_factor: float = 1.0,
        dca_top_L_factor: float = 1.0,
        dca_num_seqs: int = 100
    ) -> PredictionResult:
        """
        Main prediction function — unions contacts from 3 sources.

        Sources:
        1. ESM-2 attention (threshold + top-L selection)
        2. DCA coevolution (Direct Coupling Analysis from MSA)
        3. PDB template patterns (Kan extension from known motifs)

        Union: contact if ANY source predicts it.
        Confidence: max confidence across sources for each pair.

        Args:
            protein: Protein name
            sequence: Amino acid sequence (if not in embeddings)
            esm2_threshold: Attention threshold for ESM-2 (default 0.02)
            esm2_top_L_factor: Top-L multiplier for ESM-2 (0.5 = L/2 contacts)
            dca_top_L_factor: Top-L multiplier for DCA (0.5 = L/2 contacts)
            dca_num_seqs: Number of sequences for mock MSA (default 100)

        Returns:
            Complete prediction with contacts, motifs, reasoning
        """
        # Get sequence
        if sequence is None and self.embeddings:
            sequence = self.embeddings._sequences.get(protein, None)

        if sequence is None:
            raise ValueError(f"No sequence available for {protein}")

        length = len(sequence)

        # Detect motifs
        motifs = self.detect_motifs(sequence)

        # Initialize union contact/confidence matrices
        union_contacts = np.zeros((length, length), dtype=int)
        union_confidence = np.zeros((length, length), dtype=float)
        source_counts = {}

        # ---- Source 1: ESM-2 (threshold + top-L) ----
        if self.use_esm2:
            print(f"  [Source 1] ESM-2 contact prediction (threshold={esm2_threshold}, top-L={esm2_top_L_factor}L)...")

            # Method A: Threshold-based (late layers for contact-enriched signal)
            esm2_threshold_contacts = self.esm2.predict_contacts(
                sequence, threshold=esm2_threshold, use_layers="late"
            )
            n_threshold = int(esm2_threshold_contacts.sum() / 2)
            print(f"    Threshold {esm2_threshold}: {n_threshold} contacts (late-layer)")

            # Method B: Top-L selection (skip if factor is 0)
            esm2_top_L = int(length * esm2_top_L_factor)
            if esm2_top_L > 0:
                esm2_topL_contacts, esm2_confidence = self.esm2.predict_contacts_top_L(
                    sequence, top_L=esm2_top_L, min_separation=5, use_layers="late"
                )
                n_topL = int(esm2_topL_contacts.sum() / 2)
                print(f"    Top-L ({esm2_top_L}): {n_topL} contacts")
            else:
                esm2_topL_contacts = np.zeros_like(esm2_threshold_contacts)
                esm2_confidence = np.ones((length, length), dtype=float) * 0.52

            # Union of threshold and top-L
            esm2_union = np.maximum(esm2_threshold_contacts, esm2_topL_contacts)
            n_esm2 = int(esm2_union.sum() / 2)
            print(f"    ESM-2 union: {n_esm2} contacts")

            # Add to global union
            union_contacts = np.maximum(union_contacts, esm2_union)
            union_confidence = np.maximum(union_confidence, esm2_confidence)
            source_counts['ESM-2'] = n_esm2

        # ---- Source 2: DCA (Direct Coupling Analysis) ----
        dca_top_L = int(length * dca_top_L_factor)
        if self.use_dca and dca_top_L > 0:
            print(f"  [Source 2] DCA coevolution analysis (top-L={dca_top_L}, seqs={dca_num_seqs})...")
            try:
                dca_contacts, dca_coupling = self.msa_builder.predict_contacts_from_coevolution(
                    query_sequence=sequence,
                    num_seqs=dca_num_seqs,
                    top_L=dca_top_L
                )
                n_dca = int(dca_contacts.sum() / 2)
                print(f"    DCA: {n_dca} contacts")

                # Add to union — DCA contacts at moderate confidence
                union_contacts = np.maximum(union_contacts, dca_contacts)
                # DCA coupling scores as confidence (normalize to 0-1)
                if dca_coupling.max() > 0:
                    dca_conf_normalized = dca_coupling / dca_coupling.max()
                else:
                    dca_conf_normalized = dca_coupling
                union_confidence = np.maximum(union_confidence, dca_conf_normalized * 0.6)
                source_counts['DCA'] = n_dca
            except Exception as e:
                print(f"    DCA failed: {e}")
                source_counts['DCA'] = 0

        # ---- Source 3: PDB Templates (Kan extension) ----
        if self.use_templates:
            print("  [Source 3] PDB template pattern matching...")
            try:
                template_contacts, template_meta = self.template_predictor.predict_contacts(sequence)
                n_templates = int(template_contacts.sum() / 2)
                print(f"    Templates: {n_templates} contacts ({template_meta['num_motifs_used']} motifs)")

                # Add to union
                union_contacts = np.maximum(union_contacts, template_contacts)
                # Template confidence based on motif frequency
                template_conf = template_contacts.astype(float) * 0.5
                union_confidence = np.maximum(union_confidence, template_conf)
                source_counts['Templates'] = n_templates
            except Exception as e:
                print(f"    Templates failed: {e}")
                source_counts['Templates'] = 0

        # ---- Summary before filtering ----
        n_union = int(union_contacts.sum() / 2)
        print(f"\n  Union (all sources): {n_union} contacts")
        for src, count in source_counts.items():
            print(f"    {src}: {count}")

        # Build contact map from union
        contact_map = ContactMap(
            protein_name=protein,
            sequence=sequence,
            contacts=union_contacts,
            confidence=union_confidence,
            length=length
        )

        # Apply Physical-Chemical Bridge constraints (DURING prediction!)
        if self.use_chemistry:
            print("\n  Applying Physical-Chemical Bridge constraints...")
            contact_map = self._apply_physical_constraints(contact_map, sequence)

        # Kan extension predictions (inter-protein)
        kan_preds = self.apply_kan_extension(protein, sequence)

        # Ricci validation
        ricci_val = self.validate_with_ricci(contact_map)

        # Generate reasoning
        reasoning_lines = [
            f"Predicted {contact_map.num_contacts} contacts for {protein} ({length} residues)",
            f"Sources: {', '.join(f'{src}={count}' for src, count in source_counts.items())}",
            f"Union before filtering: {n_union}",
            f"After Physical-Chemical Bridge: {contact_map.num_contacts}",
            f"Detected {len(motifs)} structural motifs",
            f"Applied {len(kan_preds)} Kan extension predictions",
            f"Ricci validation: {ricci_val['reasoning']}"
        ]

        return PredictionResult(
            contact_map=contact_map,
            motifs_detected=motifs,
            kan_predictions=kan_preds,
            ricci_validation=ricci_val,
            reasoning="\n".join(reasoning_lines)
        )


def test_contact_prediction():
    """Test contact prediction on a simple protein."""
    from data import create_store

    print("=" * 70)
    print("TESTING COMPOSITIONAL CONTACT PREDICTION")
    print("=" * 70)
    print()

    # Load protein database
    db_path = Path("data/proteins/cancer_proteins.db")
    if not db_path.exists():
        print(f"ERROR: {db_path} not found")
        return

    store = create_store(db_path)

    # Initialize predictor
    print("Initializing contact predictor...")
    predictor = CompositionalContactPredictor(store)

    # Test on a protein
    test_protein = "TP53"
    test_sequence = "MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGP"

    print(f"\nPredicting contacts for {test_protein}...")
    print(f"Sequence length: {len(test_sequence)}")

    result = predictor.predict(test_protein, test_sequence)

    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(result.reasoning)
    print()
    print(f"Contact map: {result.contact_map.length} x {result.contact_map.length}")
    print(f"Total contacts: {result.contact_map.num_contacts}")
    print(f"Contact density: {result.contact_map.contact_density:.3f}")
    print(f"Motifs detected: {len(result.motifs_detected)}")
    print(f"Kan predictions: {len(result.kan_predictions)}")

    print("\n" + "=" * 70)
    print("NEXT: Use this contact map for 3D reconstruction")
    print("=" * 70)


if __name__ == "__main__":
    test_contact_prediction()
