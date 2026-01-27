#!/usr/bin/env python3
"""
JLCPCB Manufacturing DRC Checker for KiCad PCB files.

This script checks a KiCad PCB against JLCPCB's manufacturing capabilities
for both Standard and Advanced tiers, reporting any violations.

Usage:
    Run from within KiCad's scripting console, or with KiCad Python bindings installed.

    From KiCad scripting console:
        exec(open('/path/to/jlcpcb_drc_check.py').read())

    From command line (with KiCad Python in path):
        python jlcpcb_drc_check.py /path/to/board.kicad_pcb
"""

import sys
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from enum import Enum

try:
    import pcbnew
except ImportError:
    print("ERROR: pcbnew module not found.")
    print("This script requires KiCad's Python bindings.")
    print("Run from within KiCad's scripting console or ensure KiCad Python is in your path.")
    sys.exit(1)


# =============================================================================
# JLCPCB Manufacturing Specifications
# =============================================================================
# All measurements in mm unless otherwise noted
# Sources: JLCPCB capabilities page (as of 2024)

class ManufacturingTier(Enum):
    STANDARD = "Standard"
    ADVANCED = "Advanced"


@dataclass
class JLCPCBSpecs:
    """Manufacturing specifications for a JLCPCB tier."""
    tier: ManufacturingTier

    # Trace specifications
    min_trace_width: float          # mm
    min_trace_spacing: float        # mm (copper to copper clearance)

    # Via specifications
    min_via_drill: float            # mm (finished hole size)
    min_via_diameter: float         # mm (outer diameter / pad size)
    min_annular_ring: float         # mm
    max_aspect_ratio: float         # board thickness / hole diameter

    # PTH (Plated Through Hole) specifications
    min_pth_drill: float            # mm
    min_pth_annular_ring: float     # mm

    # NPTH (Non-Plated Through Hole) specifications
    min_npth_drill: float           # mm

    # Board outline specifications
    min_board_size: float           # mm (smallest dimension)
    max_board_size: float           # mm (largest dimension)
    min_slot_width: float           # mm
    min_cutout_size: float          # mm
    min_hole_to_hole: float         # mm (edge to edge)
    min_hole_to_edge: float         # mm (hole edge to board edge)

    # Layer count constraints
    max_layers: int


# JLCPCB Standard specifications (4+ layer boards)
JLCPCB_STANDARD = JLCPCBSpecs(
    tier=ManufacturingTier.STANDARD,

    # Trace specs (4+ layer standard)
    min_trace_width=0.09,           # 3.5 mil
    min_trace_spacing=0.09,         # 3.5 mil

    # Via specs
    min_via_drill=0.2,              # 8 mil
    min_via_diameter=0.45,          # ~18 mil (0.2mm drill + 2*0.125mm annular ring)
    min_annular_ring=0.125,         # ~5 mil (conservative)
    max_aspect_ratio=10.0,

    # PTH specs
    min_pth_drill=0.2,
    min_pth_annular_ring=0.15,      # 6 mil

    # NPTH specs
    min_npth_drill=0.5,

    # Board outline specs
    min_board_size=10.0,
    max_board_size=500.0,
    min_slot_width=0.8,
    min_cutout_size=0.8,
    min_hole_to_hole=0.5,           # Edge to edge
    min_hole_to_edge=0.3,           # Hole edge to board edge

    max_layers=32,
)


# JLCPCB Advanced specifications
JLCPCB_ADVANCED = JLCPCBSpecs(
    tier=ManufacturingTier.ADVANCED,

    # Trace specs (advanced)
    min_trace_width=0.075,          # 3 mil
    min_trace_spacing=0.075,        # 3 mil

    # Via specs (advanced)
    min_via_drill=0.15,             # 6 mil
    min_via_diameter=0.35,          # With smaller annular ring
    min_annular_ring=0.1,           # 4 mil
    max_aspect_ratio=12.0,

    # PTH specs
    min_pth_drill=0.15,
    min_pth_annular_ring=0.1,       # 4 mil

    # NPTH specs
    min_npth_drill=0.4,

    # Board outline specs
    min_board_size=10.0,
    max_board_size=500.0,
    min_slot_width=0.6,
    min_cutout_size=0.6,
    min_hole_to_hole=0.4,
    min_hole_to_edge=0.25,

    max_layers=32,
)


# =============================================================================
# Violation Tracking
# =============================================================================

@dataclass
class Violation:
    """Represents a single DRC violation."""
    category: str
    description: str
    location: Optional[Tuple[float, float]]  # X, Y in mm
    value: float                              # Actual value found
    limit: float                              # Required limit
    unit: str = "mm"
    net_name: str = ""
    layer: str = ""

    def __str__(self):
        loc_str = f" at ({self.location[0]:.3f}, {self.location[1]:.3f})" if self.location else ""
        net_str = f" [{self.net_name}]" if self.net_name else ""
        layer_str = f" on {self.layer}" if self.layer else ""
        return (f"  [{self.category}]{loc_str}{layer_str}{net_str}: "
                f"{self.description} - found {self.value:.4f}{self.unit}, "
                f"minimum {self.limit:.4f}{self.unit}")


@dataclass
class DRCResults:
    """Collection of DRC check results."""
    violations: List[Violation] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    stats: Dict[str, any] = field(default_factory=dict)

    def add_violation(self, violation: Violation):
        self.violations.append(violation)

    def add_warning(self, warning: str):
        self.warnings.append(warning)

    @property
    def has_violations(self) -> bool:
        return len(self.violations) > 0

    @property
    def violation_count(self) -> int:
        return len(self.violations)


# =============================================================================
# Unit Conversion Helpers
# =============================================================================

def nm_to_mm(nm: int) -> float:
    """Convert KiCad internal units (nanometers) to millimeters."""
    return nm / 1_000_000.0


def mm_to_nm(mm: float) -> int:
    """Convert millimeters to KiCad internal units (nanometers)."""
    return int(mm * 1_000_000)


def iu_to_mm(iu: int) -> float:
    """Convert KiCad internal units to mm (same as nm_to_mm for KiCad 6+)."""
    return nm_to_mm(iu)


def get_position_mm(item) -> Tuple[float, float]:
    """Get position of a PCB item in mm."""
    pos = item.GetPosition()
    return (iu_to_mm(pos.x), iu_to_mm(pos.y))


# =============================================================================
# DRC Check Functions
# =============================================================================

def check_trace_widths(board: pcbnew.BOARD, specs: JLCPCBSpecs, results: DRCResults):
    """Check all traces for minimum width violations."""
    min_width_found = float('inf')
    trace_count = 0
    violation_count = 0

    for track in board.GetTracks():
        if track.GetClass() == "PCB_TRACK" or isinstance(track, pcbnew.PCB_TRACK):
            if track.GetClass() == "PCB_VIA" or isinstance(track, pcbnew.PCB_VIA):
                continue  # Skip vias, handled separately

            trace_count += 1
            width = iu_to_mm(track.GetWidth())
            min_width_found = min(min_width_found, width)

            if width < specs.min_trace_width:
                violation_count += 1
                if violation_count <= 20:  # Limit reported violations
                    pos = get_position_mm(track)
                    layer_name = board.GetLayerName(track.GetLayer())
                    results.add_violation(Violation(
                        category="TRACE_WIDTH",
                        description="Trace width below minimum",
                        location=pos,
                        value=width,
                        limit=specs.min_trace_width,
                        net_name=track.GetNetname(),
                        layer=layer_name,
                    ))

    if violation_count > 20:
        results.add_warning(f"  ... and {violation_count - 20} more trace width violations")

    results.stats['trace_count'] = trace_count
    results.stats['min_trace_width'] = min_width_found if trace_count > 0 else 0
    results.stats['trace_width_violations'] = violation_count


def check_via_specs(board: pcbnew.BOARD, specs: JLCPCBSpecs, results: DRCResults):
    """Check all vias for drill size, diameter, and annular ring violations."""
    via_count = 0
    drill_violations = 0
    annular_violations = 0
    aspect_violations = 0

    min_drill_found = float('inf')
    min_annular_found = float('inf')
    max_aspect_found = 0

    # Get board thickness for aspect ratio calculation
    design_settings = board.GetDesignSettings()
    board_thickness = iu_to_mm(design_settings.GetBoardThickness())

    for track in board.GetTracks():
        if track.GetClass() == "PCB_VIA" or isinstance(track, pcbnew.PCB_VIA):
            via_count += 1
            via = track

            drill = iu_to_mm(via.GetDrill())
            diameter = iu_to_mm(via.GetWidth())  # Outer diameter
            annular_ring = (diameter - drill) / 2.0
            aspect_ratio = board_thickness / drill if drill > 0 else float('inf')

            min_drill_found = min(min_drill_found, drill)
            min_annular_found = min(min_annular_found, annular_ring)
            max_aspect_found = max(max_aspect_found, aspect_ratio)

            pos = get_position_mm(via)

            # Check drill size
            if drill < specs.min_via_drill:
                drill_violations += 1
                if drill_violations <= 10:
                    results.add_violation(Violation(
                        category="VIA_DRILL",
                        description="Via drill below minimum",
                        location=pos,
                        value=drill,
                        limit=specs.min_via_drill,
                        net_name=via.GetNetname(),
                    ))

            # Check annular ring
            if annular_ring < specs.min_annular_ring:
                annular_violations += 1
                if annular_violations <= 10:
                    results.add_violation(Violation(
                        category="VIA_ANNULAR",
                        description="Via annular ring below minimum",
                        location=pos,
                        value=annular_ring,
                        limit=specs.min_annular_ring,
                        net_name=via.GetNetname(),
                    ))

            # Check aspect ratio
            if aspect_ratio > specs.max_aspect_ratio:
                aspect_violations += 1
                if aspect_violations <= 10:
                    results.add_violation(Violation(
                        category="VIA_ASPECT",
                        description="Via aspect ratio exceeds maximum",
                        location=pos,
                        value=aspect_ratio,
                        limit=specs.max_aspect_ratio,
                        unit=":1",
                        net_name=via.GetNetname(),
                    ))

    if drill_violations > 10:
        results.add_warning(f"  ... and {drill_violations - 10} more via drill violations")
    if annular_violations > 10:
        results.add_warning(f"  ... and {annular_violations - 10} more via annular ring violations")
    if aspect_violations > 10:
        results.add_warning(f"  ... and {aspect_violations - 10} more via aspect ratio violations")

    results.stats['via_count'] = via_count
    results.stats['min_via_drill'] = min_drill_found if via_count > 0 else 0
    results.stats['min_via_annular'] = min_annular_found if via_count > 0 else 0
    results.stats['max_via_aspect'] = max_aspect_found if via_count > 0 else 0
    results.stats['via_drill_violations'] = drill_violations
    results.stats['via_annular_violations'] = annular_violations
    results.stats['via_aspect_violations'] = aspect_violations


def check_pth_specs(board: pcbnew.BOARD, specs: JLCPCBSpecs, results: DRCResults):
    """Check plated through-hole specifications on footprints."""
    pth_count = 0
    drill_violations = 0
    annular_violations = 0

    min_drill_found = float('inf')
    min_annular_found = float('inf')

    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            # Check for through-hole pads (PTH)
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                pth_count += 1

                drill_size = pad.GetDrillSize()
                drill = iu_to_mm(min(drill_size.x, drill_size.y))  # Use smaller dimension
                pad_size = pad.GetSize()
                pad_dim = iu_to_mm(min(pad_size.x, pad_size.y))
                annular_ring = (pad_dim - drill) / 2.0

                min_drill_found = min(min_drill_found, drill)
                min_annular_found = min(min_annular_found, annular_ring)

                pos = get_position_mm(pad)

                if drill < specs.min_pth_drill:
                    drill_violations += 1
                    if drill_violations <= 10:
                        results.add_violation(Violation(
                            category="PTH_DRILL",
                            description="PTH drill below minimum",
                            location=pos,
                            value=drill,
                            limit=specs.min_pth_drill,
                            net_name=pad.GetNetname(),
                        ))

                if annular_ring < specs.min_pth_annular_ring:
                    annular_violations += 1
                    if annular_violations <= 10:
                        results.add_violation(Violation(
                            category="PTH_ANNULAR",
                            description="PTH annular ring below minimum",
                            location=pos,
                            value=annular_ring,
                            limit=specs.min_pth_annular_ring,
                            net_name=pad.GetNetname(),
                        ))

    if drill_violations > 10:
        results.add_warning(f"  ... and {drill_violations - 10} more PTH drill violations")
    if annular_violations > 10:
        results.add_warning(f"  ... and {annular_violations - 10} more PTH annular ring violations")

    results.stats['pth_count'] = pth_count
    results.stats['min_pth_drill'] = min_drill_found if pth_count > 0 else 0
    results.stats['min_pth_annular'] = min_annular_found if pth_count > 0 else 0
    results.stats['pth_drill_violations'] = drill_violations
    results.stats['pth_annular_violations'] = annular_violations


def check_npth_specs(board: pcbnew.BOARD, specs: JLCPCBSpecs, results: DRCResults):
    """Check non-plated through-hole specifications."""
    npth_count = 0
    drill_violations = 0
    min_drill_found = float('inf')

    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                npth_count += 1

                drill_size = pad.GetDrillSize()
                drill = iu_to_mm(min(drill_size.x, drill_size.y))
                min_drill_found = min(min_drill_found, drill)

                if drill < specs.min_npth_drill:
                    drill_violations += 1
                    pos = get_position_mm(pad)
                    if drill_violations <= 10:
                        results.add_violation(Violation(
                            category="NPTH_DRILL",
                            description="NPTH drill below minimum",
                            location=pos,
                            value=drill,
                            limit=specs.min_npth_drill,
                        ))

    if drill_violations > 10:
        results.add_warning(f"  ... and {drill_violations - 10} more NPTH drill violations")

    results.stats['npth_count'] = npth_count
    results.stats['min_npth_drill'] = min_drill_found if npth_count > 0 else 0
    results.stats['npth_drill_violations'] = drill_violations


def check_board_outline(board: pcbnew.BOARD, specs: JLCPCBSpecs, results: DRCResults):
    """Check board outline dimensions and constraints."""
    # Get bounding box of the board
    bbox = board.GetBoardEdgesBoundingBox()

    width = iu_to_mm(bbox.GetWidth())
    height = iu_to_mm(bbox.GetHeight())

    min_dim = min(width, height)
    max_dim = max(width, height)

    results.stats['board_width'] = width
    results.stats['board_height'] = height

    if min_dim < specs.min_board_size:
        results.add_violation(Violation(
            category="BOARD_SIZE",
            description="Board dimension below minimum",
            location=None,
            value=min_dim,
            limit=specs.min_board_size,
        ))

    if max_dim > specs.max_board_size:
        results.add_violation(Violation(
            category="BOARD_SIZE",
            description="Board dimension exceeds maximum",
            location=None,
            value=max_dim,
            limit=specs.max_board_size,
        ))

    # Check layer count
    layer_count = board.GetCopperLayerCount()
    results.stats['layer_count'] = layer_count

    if layer_count > specs.max_layers:
        results.add_violation(Violation(
            category="LAYER_COUNT",
            description="Layer count exceeds maximum",
            location=None,
            value=layer_count,
            limit=specs.max_layers,
            unit=" layers",
        ))


def check_hole_to_hole_spacing(board: pcbnew.BOARD, specs: JLCPCBSpecs, results: DRCResults):
    """Check minimum spacing between holes (edge to edge)."""
    # Collect all holes with their positions and radii
    holes = []

    # Collect via holes
    for track in board.GetTracks():
        if track.GetClass() == "PCB_VIA" or isinstance(track, pcbnew.PCB_VIA):
            pos = track.GetPosition()
            drill = track.GetDrill()
            holes.append((pos.x, pos.y, drill / 2, "via", track.GetNetname()))

    # Collect pad holes
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            if pad.GetAttribute() in [pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH]:
                pos = pad.GetPosition()
                drill_size = pad.GetDrillSize()
                drill = min(drill_size.x, drill_size.y)
                pad_type = "PTH" if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH else "NPTH"
                holes.append((pos.x, pos.y, drill / 2, pad_type, pad.GetNetname()))

    results.stats['total_holes'] = len(holes)

    # Check spacing between holes (O(n^2) but limited to first violations)
    spacing_violations = 0
    min_spacing_found = float('inf')
    min_spacing_nm = mm_to_nm(specs.min_hole_to_hole)

    for i, (x1, y1, r1, type1, net1) in enumerate(holes):
        for j, (x2, y2, r2, type2, net2) in enumerate(holes[i+1:], i+1):
            # Calculate edge-to-edge distance
            center_dist = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
            edge_dist = center_dist - r1 - r2
            edge_dist_mm = iu_to_mm(edge_dist)

            if edge_dist_mm < min_spacing_found:
                min_spacing_found = edge_dist_mm

            if edge_dist < min_spacing_nm:
                spacing_violations += 1
                if spacing_violations <= 10:
                    results.add_violation(Violation(
                        category="HOLE_SPACING",
                        description=f"Hole-to-hole spacing below minimum ({type1} to {type2})",
                        location=(iu_to_mm(x1), iu_to_mm(y1)),
                        value=edge_dist_mm,
                        limit=specs.min_hole_to_hole,
                    ))

        # Early exit if we've found enough violations
        if spacing_violations > 100:
            break

    if spacing_violations > 10:
        results.add_warning(f"  ... and {spacing_violations - 10} more hole spacing violations")

    results.stats['min_hole_spacing'] = min_spacing_found if len(holes) > 1 else float('inf')
    results.stats['hole_spacing_violations'] = spacing_violations


def check_clearances(board: pcbnew.BOARD, specs: JLCPCBSpecs, results: DRCResults):
    """
    Check copper-to-copper clearances.
    Note: This is a simplified check. Full clearance checking requires
    geometric analysis that KiCad's DRC engine handles better.
    """
    # Report the board's configured clearance settings
    design_settings = board.GetDesignSettings()

    # Get minimum clearance from design settings
    min_clearance = iu_to_mm(design_settings.m_MinClearance)
    results.stats['configured_min_clearance'] = min_clearance

    if min_clearance < specs.min_trace_spacing:
        results.add_warning(
            f"  Board's configured minimum clearance ({min_clearance:.4f}mm) is below "
            f"JLCPCB {specs.tier.value} minimum ({specs.min_trace_spacing:.4f}mm). "
            f"Run KiCad DRC to check for actual violations."
        )


# =============================================================================
# Main DRC Runner
# =============================================================================

def run_jlcpcb_drc(board: pcbnew.BOARD, specs: JLCPCBSpecs) -> DRCResults:
    """Run all JLCPCB DRC checks against the board."""
    results = DRCResults()

    print(f"\nRunning JLCPCB DRC checks ({specs.tier.value} tier)...")
    print("-" * 60)

    check_board_outline(board, specs, results)
    check_trace_widths(board, specs, results)
    check_via_specs(board, specs, results)
    check_pth_specs(board, specs, results)
    check_npth_specs(board, specs, results)
    check_hole_to_hole_spacing(board, specs, results)
    check_clearances(board, specs, results)

    return results


def print_results(results: DRCResults, specs: JLCPCBSpecs):
    """Print DRC results in a readable format."""
    print(f"\n{'='*60}")
    print(f"JLCPCB DRC Results - {specs.tier.value} Tier")
    print(f"{'='*60}")

    # Print statistics
    print("\nBoard Statistics:")
    print(f"  Board size: {results.stats.get('board_width', 0):.2f} x {results.stats.get('board_height', 0):.2f} mm")
    print(f"  Layer count: {results.stats.get('layer_count', 0)}")
    print(f"  Total traces: {results.stats.get('trace_count', 0)}")
    print(f"  Total vias: {results.stats.get('via_count', 0)}")
    print(f"  Total PTH pads: {results.stats.get('pth_count', 0)}")
    print(f"  Total NPTH pads: {results.stats.get('npth_count', 0)}")
    print(f"  Total holes: {results.stats.get('total_holes', 0)}")

    print("\nMeasured Minimums:")
    if results.stats.get('min_trace_width', 0) > 0:
        print(f"  Min trace width: {results.stats['min_trace_width']:.4f} mm "
              f"(limit: {specs.min_trace_width:.4f} mm)")
    if results.stats.get('min_via_drill', 0) > 0:
        print(f"  Min via drill: {results.stats['min_via_drill']:.4f} mm "
              f"(limit: {specs.min_via_drill:.4f} mm)")
    if results.stats.get('min_via_annular', 0) > 0:
        print(f"  Min via annular ring: {results.stats['min_via_annular']:.4f} mm "
              f"(limit: {specs.min_annular_ring:.4f} mm)")
    if results.stats.get('max_via_aspect', 0) > 0:
        print(f"  Max via aspect ratio: {results.stats['max_via_aspect']:.2f}:1 "
              f"(limit: {specs.max_aspect_ratio:.1f}:1)")
    if results.stats.get('min_pth_drill', 0) > 0:
        print(f"  Min PTH drill: {results.stats['min_pth_drill']:.4f} mm "
              f"(limit: {specs.min_pth_drill:.4f} mm)")
    if results.stats.get('min_hole_spacing', float('inf')) < float('inf'):
        print(f"  Min hole-to-hole spacing: {results.stats['min_hole_spacing']:.4f} mm "
              f"(limit: {specs.min_hole_to_hole:.4f} mm)")

    # Print violations
    if results.violations:
        print(f"\nVIOLATIONS FOUND: {len(results.violations)}")
        print("-" * 40)

        # Group by category
        by_category = {}
        for v in results.violations:
            if v.category not in by_category:
                by_category[v.category] = []
            by_category[v.category].append(v)

        for category, violations in sorted(by_category.items()):
            print(f"\n{category} ({len(violations)} violations):")
            for v in violations:
                print(v)
    else:
        print(f"\n*** NO VIOLATIONS - Board passes {specs.tier.value} tier requirements! ***")

    # Print warnings
    if results.warnings:
        print(f"\nWarnings:")
        for w in results.warnings:
            print(w)

    print()


def run_full_check(board: pcbnew.BOARD):
    """Run checks against both Standard and Advanced tiers."""
    print("\n" + "="*60)
    print("JLCPCB Manufacturing DRC Check")
    print("="*60)

    # Run Standard tier check
    standard_results = run_jlcpcb_drc(board, JLCPCB_STANDARD)
    print_results(standard_results, JLCPCB_STANDARD)

    # Run Advanced tier check
    advanced_results = run_jlcpcb_drc(board, JLCPCB_ADVANCED)
    print_results(advanced_results, JLCPCB_ADVANCED)

    # Summary
    print("="*60)
    print("SUMMARY")
    print("="*60)

    if not standard_results.has_violations:
        print("  [PASS] Board meets JLCPCB STANDARD tier requirements")
    else:
        print(f"  [FAIL] Board has {standard_results.violation_count} STANDARD tier violations")

    if not advanced_results.has_violations:
        print("  [PASS] Board meets JLCPCB ADVANCED tier requirements")
    else:
        print(f"  [FAIL] Board has {advanced_results.violation_count} ADVANCED tier violations")

    if standard_results.has_violations and advanced_results.has_violations:
        print("\n  Recommendation: Review violations and adjust design to meet at least")
        print("  STANDARD tier requirements for JLCPCB manufacturing.")
    elif standard_results.has_violations:
        print("\n  Recommendation: Board requires ADVANCED tier manufacturing.")
        print("  Consider adjusting design to meet STANDARD tier for lower cost.")
    else:
        print("\n  Board is ready for JLCPCB STANDARD tier manufacturing!")

    print()
    return standard_results, advanced_results


# =============================================================================
# Entry Points
# =============================================================================

def main():
    """Main entry point when run from command line."""
    if len(sys.argv) > 1:
        # Load board from file path argument
        pcb_path = sys.argv[1]
        print(f"Loading board: {pcb_path}")
        board = pcbnew.LoadBoard(pcb_path)
    else:
        # Try to get board from KiCad if running in scripting console
        try:
            board = pcbnew.GetBoard()
            if board is None:
                print("ERROR: No board loaded. Provide a .kicad_pcb file path as argument.")
                print(f"Usage: python {sys.argv[0]} /path/to/board.kicad_pcb")
                sys.exit(1)
        except:
            print("ERROR: No board available. Provide a .kicad_pcb file path as argument.")
            print(f"Usage: python {sys.argv[0]} /path/to/board.kicad_pcb")
            sys.exit(1)

    run_full_check(board)


if __name__ == "__main__":
    main()
else:
    # When imported or exec'd in KiCad scripting console
    try:
        _board = pcbnew.GetBoard()
        if _board is not None:
            print("Board detected. Run 'run_full_check(pcbnew.GetBoard())' to check.")
            print("Or run 'run_jlcpcb_drc(pcbnew.GetBoard(), JLCPCB_STANDARD)' for single tier.")
    except:
        pass
