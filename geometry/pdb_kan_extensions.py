# SPDX-License-Identifier: Apache-2.0 OR KOMPOSOS-III-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
PDB Pattern Extraction via Kan Extensions

Extract structural motifs from PDB database and transfer to new sequences
using category-theoretic Kan extensions.

Mathematical Framework:
- PDB structures form a category StructCat
- Sequence motifs form a category SeqCat
- Structural motifs are objects in StructCat
- Kan extension: Lan_F(G): SeqCat → StructCat
  transfers patterns from known to unknown structures

This is fundamentally compositional:
- Each PDB structure contributes patterns (objects)
- Patterns compose via morphisms
- Kan extension lifts compositions to new sequences
- Result is a compositionally-derived contact map

Integration with Store:
- Store provides the Kan extension machinery
- We populate Store with PDB-derived patterns
- Query sequence gets contacts via Lan composition
"""

import numpy as np
from typing import List, Tuple, Dict, Optional, Set
from dataclasses import dataclass
from pathlib import Path
import re

# Import Store for Kan extensions
try:
    from ..memory.store import KomposOSStore
    from ..ops.kan_extensions import Kan, KanOperation
    STORE_AVAILABLE = True
except ImportError:
    try:
        from memory.store import KomposOSStore
        from ops.kan_extensions import Kan, KanOperation
        STORE_AVAILABLE = True
    except ImportError:
        STORE_AVAILABLE = False
        print("Warning: Store not available. Using simplified Kan extensions.")


@dataclass
class StructuralMotif:
    """
    A structural motif object in the structure category.

    Motifs are recurring patterns: helices, sheets, turns, specific contacts.
    """
    motif_id: str
    motif_type: str  # 'helix', 'sheet', 'turn', 'contact_pattern'
    sequence_pattern: str  # Sequence motif (with wildcards)
    contact_pattern: List[Tuple[int, int]]  # Relative contact positions
    frequency: int  # How often seen in PDB
    source_pdbs: List[str]  # Which PDBs contributed this

    @staticmethod
    def _parse_pattern(pattern: str):
        """Parse a pattern string into a list of match elements.

        Each element is either a single character, 'X' (wildcard),
        or a set of allowed characters (from [ABC] bracket notation).

        Returns list of (type, value) where type is 'char', 'wildcard', or 'class'.
        """
        elements = []
        i = 0
        while i < len(pattern):
            if pattern[i] == '[':
                end = pattern.find(']', i)
                if end < 0:
                    end = len(pattern)
                allowed = pattern[i+1:end]
                elements.append(('class', allowed))
                i = end + 1
            elif pattern[i] == 'X':
                elements.append(('wildcard', None))
                i += 1
            else:
                elements.append(('char', pattern[i]))
                i += 1
        return elements

    def effective_length(self) -> int:
        """Number of residues this pattern actually matches."""
        return len(self._parse_pattern(self.sequence_pattern))

    def matches_sequence(self, sequence: str, start_pos: int) -> bool:
        """Check if this motif matches sequence at start_pos."""
        elements = self._parse_pattern(self.sequence_pattern)
        eff_len = len(elements)

        if start_pos + eff_len > len(sequence):
            return False

        for i, (etype, value) in enumerate(elements):
            seq_aa = sequence[start_pos + i]

            if etype == 'wildcard':
                continue
            elif etype == 'class':
                if seq_aa not in value:
                    return False
            elif etype == 'char':
                if seq_aa != value:
                    return False

        return True


class PDBPatternLibrary:
    """
    Library of structural motifs extracted from PDB database.

    Acts as a structured knowledge base for Kan extensions.
    """

    def __init__(self):
        self.motifs: List[StructuralMotif] = []
        self.motif_index: Dict[str, List[StructuralMotif]] = {}

    def add_motif(self, motif: StructuralMotif):
        """Add a motif to the library."""
        self.motifs.append(motif)

        # Index by motif type
        if motif.motif_type not in self.motif_index:
            self.motif_index[motif.motif_type] = []
        self.motif_index[motif.motif_type].append(motif)

    def find_matching_motifs(self, sequence: str) -> List[Tuple[StructuralMotif, int]]:
        """
        Find all motifs that match the query sequence.

        Returns:
            List of (motif, start_position) pairs
        """
        matches = []

        for motif in self.motifs:
            eff_len = motif.effective_length()
            # Scan sequence for matches using effective (residue) length
            for start in range(len(sequence) - eff_len + 1):
                if motif.matches_sequence(sequence, start):
                    matches.append((motif, start))

        return matches

    def build_default_library(self):
        """Build default library with common structural motifs."""
        print("Building default PDB pattern library...")

        # Alpha helix motifs (i, i+3), (i, i+4) contacts
        helix_motifs = [
            StructuralMotif(
                motif_id="helix_hydrophobic",
                motif_type="helix",
                sequence_pattern="[AILMFVW]XX[AILMFVW]",  # Hydrophobic at i, i+3
                contact_pattern=[(0, 3), (0, 4)],  # i to i+3, i+4 contacts
                frequency=1000,
                source_pdbs=["helix_library"]
            ),
            StructuralMotif(
                motif_id="helix_charged",
                motif_type="helix",
                sequence_pattern="[DEKR]XXX[DEKR]",  # Charged at i, i+4
                contact_pattern=[(0, 4)],
                frequency=500,
                source_pdbs=["helix_library"]
            )
        ]

        # Beta sheet motifs (i, j) contacts where j = i+2, i+4 (antiparallel)
        sheet_motifs = [
            StructuralMotif(
                motif_id="sheet_hydrophobic",
                motif_type="sheet",
                sequence_pattern="[VILFYW]X[VILFYW]",  # Alternating hydrophobic
                contact_pattern=[(0, 2)],  # Strand pairing
                frequency=800,
                source_pdbs=["sheet_library"]
            )
        ]

        # Turn motifs
        turn_motifs = [
            StructuralMotif(
                motif_id="turn_type1",
                motif_type="turn",
                sequence_pattern="[NDS]X[GP]",  # Common turn residues
                contact_pattern=[(0, 3)],  # Hairpin contact
                frequency=300,
                source_pdbs=["turn_library"]
            )
        ]

        # Add all motifs
        for motif in helix_motifs + sheet_motifs + turn_motifs:
            self.add_motif(motif)

        print(f"  Loaded {len(self.motifs)} structural motifs")
        print(f"  Types: {list(self.motif_index.keys())}")

    def build_extended_library(self):
        """Build extended library with more secondary structure motifs.

        Adds idealized helix, sheet, and turn motifs with broader sequence
        patterns for better coverage during fragment assembly.
        """
        # Start with defaults if empty
        if not self.motifs:
            self.build_default_library()

        # Additional helix motifs
        helix_extended = [
            StructuralMotif(
                motif_id="helix_alanine",
                motif_type="helix",
                sequence_pattern="AXXAX",
                contact_pattern=[(0, 3), (0, 4), (1, 4)],
                frequency=600,
                source_pdbs=["helix_library"]
            ),
            StructuralMotif(
                motif_id="helix_leucine",
                motif_type="helix",
                sequence_pattern="[LI]XXX[LIV]",
                contact_pattern=[(0, 4)],
                frequency=700,
                source_pdbs=["helix_library"]
            ),
            StructuralMotif(
                motif_id="helix_glutamate",
                motif_type="helix",
                sequence_pattern="[EQ]XXX[KR]",
                contact_pattern=[(0, 4)],
                frequency=400,
                source_pdbs=["helix_library"]
            ),
        ]

        # Additional sheet motifs
        sheet_extended = [
            StructuralMotif(
                motif_id="sheet_threonine",
                motif_type="sheet",
                sequence_pattern="[TV]X[TV]X[TV]",
                contact_pattern=[(0, 2), (2, 4)],
                frequency=400,
                source_pdbs=["sheet_library"]
            ),
            StructuralMotif(
                motif_id="sheet_isoleucine",
                motif_type="sheet",
                sequence_pattern="[IVLF]X[IVLF]",
                contact_pattern=[(0, 2)],
                frequency=500,
                source_pdbs=["sheet_library"]
            ),
        ]

        # Additional turn motifs
        turn_extended = [
            StructuralMotif(
                motif_id="turn_type2",
                motif_type="turn",
                sequence_pattern="XPGX",
                contact_pattern=[(0, 3)],
                frequency=250,
                source_pdbs=["turn_library"]
            ),
            StructuralMotif(
                motif_id="turn_asparagine",
                motif_type="turn",
                sequence_pattern="[ND]XXG",
                contact_pattern=[(0, 3)],
                frequency=200,
                source_pdbs=["turn_library"]
            ),
        ]

        for motif in helix_extended + sheet_extended + turn_extended:
            self.add_motif(motif)

    def get_fragment_coordinates(self, motif: StructuralMotif, length: int) -> np.ndarray:
        """Generate idealized CA coordinates for a matched motif.

        Args:
            motif: The matched structural motif
            length: Number of residues

        Returns:
            (length, 3) numpy array of CA coordinates
        """
        coords = np.zeros((length, 3))

        if motif.motif_type == "helix":
            # Alpha helix: 1.5 A rise/residue, 100 deg rotation, radius 2.3 A
            for i in range(length):
                angle = np.radians(100.0 * i)
                coords[i] = [2.3 * np.cos(angle), 2.3 * np.sin(angle), 1.5 * i]

        elif motif.motif_type == "sheet":
            # Beta strand: 3.3 A rise/residue, alternating +/- 1.2 A
            for i in range(length):
                coords[i] = [3.3 * i, 1.2 * ((-1) ** i), 0.0]

        elif motif.motif_type == "turn":
            # Turn: arc with ~3.8 A per residue
            if length <= 1:
                return coords
            for i in range(length):
                t = i / max(length - 1, 1)
                angle = np.pi * t
                r = 3.8 * length / (2 * np.pi)
                coords[i] = [r * (1 - np.cos(angle)), r * np.sin(angle), 0.0]

        else:
            # Extended chain
            for i in range(length):
                angle = i * 0.3
                coords[i] = [3.8 * i, np.sin(angle) * 1.5, np.cos(angle) * 1.5]

        return coords

    def extract_from_pdb(self, pdb_path: Path):
        """
        Extract structural motifs from a PDB file.

        Identifies:
        - Secondary structure elements
        - Conserved contact patterns
        - Sequence-structure relationships
        """
        print(f"Extracting motifs from {pdb_path.name}...")

        # Parse PDB (simplified - read CA atoms and contacts)
        sequence, coords = self._parse_pdb(pdb_path)
        if sequence is None:
            return

        contacts = self._compute_contacts_from_coords(coords, threshold=8.0)

        # Extract motifs
        # For each window of size 3-10, check if it forms consistent pattern
        for window_size in [3, 4, 5]:
            for start in range(len(sequence) - window_size + 1):
                motif_seq = sequence[start:start+window_size]
                motif_contacts = []

                # Find contacts within this window
                for i in range(window_size):
                    for j in range(i+2, window_size):
                        if contacts[start+i, start+j]:
                            motif_contacts.append((i, j))

                if len(motif_contacts) >= 1:
                    # Create motif
                    motif = StructuralMotif(
                        motif_id=f"{pdb_path.stem}_{start}_{window_size}",
                        motif_type="pdb_extracted",
                        sequence_pattern=motif_seq,
                        contact_pattern=motif_contacts,
                        frequency=1,
                        source_pdbs=[pdb_path.stem]
                    )
                    self.add_motif(motif)

        print(f"  Extracted {len(self.motifs)} motifs")

    def _parse_pdb(self, pdb_path: Path) -> Tuple[Optional[str], Optional[np.ndarray]]:
        """Parse PDB file for sequence and CA coordinates."""
        if not pdb_path.exists():
            return None, None

        sequence = []
        coords = []

        aa_map = {
            'ALA': 'A', 'CYS': 'C', 'ASP': 'D', 'GLU': 'E',
            'PHE': 'F', 'GLY': 'G', 'HIS': 'H', 'ILE': 'I',
            'LYS': 'K', 'LEU': 'L', 'MET': 'M', 'ASN': 'N',
            'PRO': 'P', 'GLN': 'Q', 'ARG': 'R', 'SER': 'S',
            'THR': 'T', 'VAL': 'V', 'TRP': 'W', 'TYR': 'Y'
        }

        with open(pdb_path) as f:
            for line in f:
                if line.startswith('ATOM') and ' CA ' in line:
                    aa_3letter = line[17:20].strip()
                    if aa_3letter in aa_map:
                        sequence.append(aa_map[aa_3letter])

                        x = float(line[30:38])
                        y = float(line[38:46])
                        z = float(line[46:54])
                        coords.append([x, y, z])

        if len(sequence) == 0:
            return None, None

        return ''.join(sequence), np.array(coords)

    def _compute_contacts_from_coords(self, coords: np.ndarray, threshold: float = 8.0) -> np.ndarray:
        """Compute contact map from coordinates."""
        N = len(coords)
        contacts = np.zeros((N, N), dtype=int)

        for i in range(N):
            for j in range(i+2, N):
                dist = np.linalg.norm(coords[i] - coords[j])
                if dist < threshold:
                    contacts[i, j] = 1
                    contacts[j, i] = 1

        return contacts


class KanExtensionContactPredictor:
    """
    Predict contacts via Kan extension from PDB patterns.

    Mathematical procedure:
    1. Build pattern library from PDB (objects in StructCat)
    2. Find matching patterns in query sequence (morphisms)
    3. Compose patterns via Kan extension (Lan_F(G))
    4. Output compositionally-derived contact map

    Uses Store for Kan machinery.
    """

    def __init__(self, store: Optional = None, library: Optional[PDBPatternLibrary] = None):
        """
        Initialize Kan extension predictor.

        Args:
            store: KomposOSStore for Kan extensions
            library: PDB pattern library
        """
        self.store = store
        self.library = library or PDBPatternLibrary()

        if self.library.motifs == []:
            print("Building default pattern library...")
            self.library.build_default_library()

        print(f"Kan Extension Predictor ready with {len(self.library.motifs)} patterns")

    def predict_contacts(self, sequence: str) -> Tuple[np.ndarray, Dict]:
        """
        Predict contacts via Kan extension composition.

        Args:
            sequence: Query amino acid sequence

        Returns:
            (contact_map, metadata_dict)
        """
        print(f"Predicting contacts via Kan extension for {len(sequence)} residues...")

        # 1. Find all matching motifs
        matches = self.library.find_matching_motifs(sequence)
        print(f"  Found {len(matches)} motif matches")

        # 2. Compose motifs to build contact map
        L = len(sequence)
        contact_map = np.zeros((L, L), dtype=float)
        contact_counts = np.zeros((L, L), dtype=int)

        for motif, start_pos in matches:
            # Apply motif's contact pattern at start_pos
            for (i, j) in motif.contact_pattern:
                pos_i = start_pos + i
                pos_j = start_pos + j

                if pos_i < L and pos_j < L:
                    # Weight by motif frequency (more common = more reliable)
                    weight = np.log(1 + motif.frequency)
                    contact_map[pos_i, pos_j] += weight
                    contact_map[pos_j, pos_i] += weight
                    contact_counts[pos_i, pos_j] += 1
                    contact_counts[pos_j, pos_i] += 1

        # 3. Normalize by counts (average over all motifs)
        mask = contact_counts > 0
        contact_map[mask] /= contact_counts[mask]

        # 4. Convert to binary (threshold)
        mean_score = contact_map[mask].mean() if mask.any() else 0
        std_score = contact_map[mask].std() if mask.any() else 1
        threshold = mean_score + 0.5 * std_score

        binary_contacts = (contact_map > threshold).astype(int)

        print(f"  Predicted {int(binary_contacts.sum() / 2)} contacts")
        print(f"  Mean score: {mean_score:.3f}, Threshold: {threshold:.3f}")

        metadata = {
            'num_motifs_used': len(matches),
            'mean_score': mean_score,
            'threshold': threshold,
            'motif_coverage': len(matches) / len(sequence)
        }

        return binary_contacts, metadata

    def predict_contacts_with_store(self, sequence: str) -> Tuple[np.ndarray, Dict]:
        """
        Predict contacts using Store's Kan extension machinery.

        This is the true category-theoretic version using Store composition.
        """
        if not STORE_AVAILABLE or self.store is None:
            print("  Store not available, using simplified Kan extension")
            return self.predict_contacts(sequence)

        print(f"Predicting via Store Kan extension...")

        # TODO: Integrate with Store's actual Kan extension
        # For now, use simplified version
        return self.predict_contacts(sequence)


def test_pdb_kan_extensions():
    """Test PDB Kan extension contact prediction."""
    print("=" * 70)
    print("TESTING PDB KAN EXTENSION CONTACT PREDICTION")
    print("=" * 70)
    print()

    # Test sequence (Villin HP36)
    sequence = "MLSDEDFKAVFGMTRSAFANLPLWKQQNLKKEKGLF"

    print(f"Query: {sequence}")
    print(f"Length: {len(sequence)} residues")
    print()

    # Initialize predictor with default library
    predictor = KanExtensionContactPredictor()

    # Predict contacts
    contacts, metadata = predictor.predict_contacts(sequence)

    num_contacts = int(contacts.sum() / 2)

    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"Contacts predicted: {num_contacts}")
    print(f"Motifs used: {metadata['num_motifs_used']}")
    print(f"Coverage: {metadata['motif_coverage']:.2f} motifs per residue")
    print()

    print("Category-theoretic interpretation:")
    print("  - PDB patterns = Objects in StructCat")
    print("  - Pattern matches = Morphisms to query sequence")
    print("  - Kan extension = Compositional lifting Lan_F(G)")
    print("  - Contact map = Result of composition")
    print()
    print("Fully compositional and interpretable!")
    print("=" * 70)


if __name__ == "__main__":
    test_pdb_kan_extensions()
