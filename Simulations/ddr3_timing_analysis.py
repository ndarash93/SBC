#!/usr/bin/env python3
"""
DDR3 Timing Analysis Script
Analyzes DDR signal timing against JEDEC DDR3 specifications
using JLCPCB PCB material constants.
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple
from enum import Enum

# =============================================================================
# JLCPCB Material Constants
# =============================================================================

class JLCPCBMaterial:
    """JLCPCB standard PCB material properties"""

    # FR-4 Standard (JLC7628 prepreg)
    FR4_STANDARD = {
        'name': 'FR-4 Standard (7628)',
        'Er': 4.3,           # Dielectric constant at 1GHz
        'Df': 0.02,          # Loss tangent (dissipation factor)
        'thickness_core_mm': 1.2,    # Typical core thickness
        'thickness_prepreg_mm': 0.2, # Typical prepreg thickness
        'copper_oz': 1,      # Standard copper weight (oz/sq ft)
    }

    # FR-4 High-Tg (JLC370HR)
    FR4_HIGH_TG = {
        'name': 'FR-4 High-Tg (370HR)',
        'Er': 4.2,
        'Df': 0.018,
        'thickness_core_mm': 1.2,
        'thickness_prepreg_mm': 0.2,
        'copper_oz': 1,
    }

    # JLC04161H-7628 (4-layer 1.6mm stackup)
    JLC04161H_7628 = {
        'name': 'JLC04161H-7628 4-Layer',
        'Er': 4.5,           # Slightly higher for this stackup
        'Df': 0.02,
        'layer_heights_mm': [0.035, 0.36, 0.76, 0.36, 0.035],  # L1-prepreg-core-prepreg-L4
        'copper_oz': 1,
    }


# =============================================================================
# DDR3 JEDEC Timing Specifications
# =============================================================================

class DDR3Speed(Enum):
    DDR3_800  = 800
    DDR3_1066 = 1066
    DDR3_1333 = 1333
    DDR3_1600 = 1600
    DDR3_1866 = 1866
    DDR3_2133 = 2133


@dataclass
class DDR3TimingSpec:
    """DDR3 JEDEC timing specifications (in picoseconds unless noted)"""
    speed_grade: DDR3Speed
    tCK_min: float      # Clock period minimum (ps)
    tCK_max: float      # Clock period maximum (ps)
    tIS_base: float     # Input setup time base (ps)
    tIH_base: float     # Input hold time base (ps)
    tDS: float          # DQ input setup time (ps)
    tDH: float          # DQ input hold time (ps)
    tDQSS_min: float    # DQS to CLK timing min (fraction of tCK)
    tDQSS_max: float    # DQS to CLK timing max (fraction of tCK)
    tDSS: float         # DQS falling edge setup (fraction of tCK)
    tDSH: float         # DQS falling edge hold (fraction of tCK)
    tDQSCK_min: float   # DQS output access time min (ps)
    tDQSCK_max: float   # DQS output access time max (ps)


DDR3_SPECS = {
    DDR3Speed.DDR3_800: DDR3TimingSpec(
        speed_grade=DDR3Speed.DDR3_800,
        tCK_min=2500, tCK_max=3300,
        tIS_base=200, tIH_base=275,
        tDS=75, tDH=150,
        tDQSS_min=-0.27, tDQSS_max=0.27,
        tDSS=0.18, tDSH=0.18,
        tDQSCK_min=-400, tDQSCK_max=400,
    ),
    DDR3Speed.DDR3_1066: DDR3TimingSpec(
        speed_grade=DDR3Speed.DDR3_1066,
        tCK_min=1875, tCK_max=2500,
        tIS_base=170, tIH_base=250,
        tDS=50, tDH=125,
        tDQSS_min=-0.27, tDQSS_max=0.27,
        tDSS=0.18, tDSH=0.18,
        tDQSCK_min=-300, tDQSCK_max=300,
    ),
    DDR3Speed.DDR3_1333: DDR3TimingSpec(
        speed_grade=DDR3Speed.DDR3_1333,
        tCK_min=1500, tCK_max=1875,
        tIS_base=125, tIH_base=200,
        tDS=25, tDH=100,
        tDQSS_min=-0.27, tDQSS_max=0.27,
        tDSS=0.18, tDSH=0.18,
        tDQSCK_min=-255, tDQSCK_max=255,
    ),
    DDR3Speed.DDR3_1600: DDR3TimingSpec(
        speed_grade=DDR3Speed.DDR3_1600,
        tCK_min=1250, tCK_max=1500,
        tIS_base=100, tIH_base=175,
        tDS=10, tDH=70,
        tDQSS_min=-0.27, tDQSS_max=0.27,
        tDSS=0.18, tDSH=0.18,
        tDQSCK_min=-225, tDQSCK_max=225,
    ),
    DDR3Speed.DDR3_1866: DDR3TimingSpec(
        speed_grade=DDR3Speed.DDR3_1866,
        tCK_min=1071, tCK_max=1250,
        tIS_base=75, tIH_base=150,
        tDS=5, tDH=60,
        tDQSS_min=-0.27, tDQSS_max=0.27,
        tDSS=0.18, tDSH=0.18,
        tDQSCK_min=-195, tDQSCK_max=195,
    ),
    DDR3Speed.DDR3_2133: DDR3TimingSpec(
        speed_grade=DDR3Speed.DDR3_2133,
        tCK_min=938, tCK_max=1071,
        tIS_base=55, tIH_base=140,
        tDS=5, tDH=45,
        tDQSS_min=-0.27, tDQSS_max=0.27,
        tDSS=0.18, tDSH=0.18,
        tDQSCK_min=-175, tDQSCK_max=175,
    ),
}


# =============================================================================
# DDR3 Signal Groups and Skew Requirements
# =============================================================================

@dataclass
class DDR3SkewRequirements:
    """DDR3 signal group skew requirements (in ps)"""
    # Within byte lane (DQ to DQS)
    dq_to_dqs_max: float = 100      # Max skew within byte lane

    # Clock signals
    ck_to_ckn_max: float = 5        # CK/CK# differential skew

    # Address/Command to Clock
    addr_cmd_to_ck_max: float = 50  # Typical target for addr/cmd matching

    # Data mask to DQS
    dm_to_dqs_max: float = 100      # DM treated same as DQ in byte lane

    # Between byte lanes (for multi-rank)
    dqs_to_dqs_max: float = 200     # Between different byte lanes


# =============================================================================
# Signal Definitions
# =============================================================================

@dataclass
class DDRSignal:
    """Represents a DDR signal with its trace properties"""
    name: str
    group: str           # Signal group (DATA0, DATA1, ADDR, CMD, CLK)
    length_mm: float     # Trace length in mm
    layer: int           # PCB layer (1-indexed)
    impedance: float     # Target impedance (ohms)
    is_differential: bool = False
    pair_name: str = None


class DDR3SignalGroups:
    """Standard DDR3 signal groupings"""

    CLOCK = ['CK', 'CK#']

    # Byte lane 0 (DQ0-7)
    DATA0 = ['DQ0', 'DQ1', 'DQ2', 'DQ3', 'DQ4', 'DQ5', 'DQ6', 'DQ7',
             'DQS0', 'DQS0#', 'DM0']

    # Byte lane 1 (DQ8-15)
    DATA1 = ['DQ8', 'DQ9', 'DQ10', 'DQ11', 'DQ12', 'DQ13', 'DQ14', 'DQ15',
             'DQS1', 'DQS1#', 'DM1']

    # Address signals
    ADDRESS = ['A0', 'A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7',
               'A8', 'A9', 'A10', 'A11', 'A12', 'A13', 'A14', 'A15']

    # Bank address
    BANK = ['BA0', 'BA1', 'BA2']

    # Command signals
    COMMAND = ['RAS#', 'CAS#', 'WE#', 'CS#', 'CKE', 'ODT', 'RESET#']


# =============================================================================
# Timing Calculator
# =============================================================================

class DDR3TimingAnalyzer:
    """Analyzes DDR3 signal timing and skew"""

    # Speed of light: 299,792,458 m/s = 299.792458 mm/ns = 0.299792458 mm/ps
    SPEED_OF_LIGHT_MM_PS = 0.299792458  # mm per picosecond

    def __init__(self, material: dict, speed_grade: DDR3Speed):
        self.material = material
        self.speed_grade = speed_grade
        self.spec = DDR3_SPECS[speed_grade]
        self.skew_req = DDR3SkewRequirements()
        self.signals: Dict[str, DDRSignal] = {}

    @property
    def propagation_velocity(self) -> float:
        """Calculate propagation velocity in mm/ps for microstrip"""
        Er_eff = (self.material['Er'] + 1) / 2  # Effective Er for microstrip
        return self.SPEED_OF_LIGHT_MM_PS / math.sqrt(Er_eff)

    @property
    def propagation_delay_ps_per_mm(self) -> float:
        """Propagation delay in ps/mm"""
        return 1.0 / self.propagation_velocity

    @property
    def propagation_delay_ps_per_inch(self) -> float:
        """Propagation delay in ps/inch"""
        return self.propagation_delay_ps_per_mm * 25.4

    def add_signal(self, signal: DDRSignal):
        """Add a signal to analyze"""
        self.signals[signal.name] = signal

    def add_signals_from_dict(self, signals_dict: Dict[str, Dict]):
        """
        Add signals from a dictionary format:
        {'DQ0': {'length_mm': 45, 'layer': 3, 'group': 'DATA0'}, ...}
        """
        for name, props in signals_dict.items():
            is_diff = '#' in name or (name.startswith('DQS') and not name.endswith('#'))
            pair = None
            if name.endswith('#'):
                pair = name[:-1]
            elif name.startswith('DQS') and not name.endswith('#'):
                pair = name + '#'
            elif name == 'CK':
                pair = 'CK#'
            elif name == 'CK#':
                pair = 'CK'

            signal = DDRSignal(
                name=name,
                group=props.get('group', 'UNKNOWN'),
                length_mm=props.get('length_mm', 0),
                layer=props.get('layer', 1),
                impedance=props.get('impedance', 50),
                is_differential='DQS' in name or name in ['CK', 'CK#'],
                pair_name=pair
            )
            self.add_signal(signal)

    def calculate_delay(self, length_mm: float) -> float:
        """Calculate propagation delay for a given trace length"""
        return length_mm * self.propagation_delay_ps_per_mm

    def get_signal_delay(self, signal_name: str) -> float:
        """Get propagation delay for a specific signal"""
        if signal_name not in self.signals:
            raise ValueError(f"Signal {signal_name} not found")
        return self.calculate_delay(self.signals[signal_name].length_mm)

    def analyze_group_skew(self, group_name: str) -> Dict:
        """Analyze timing skew within a signal group"""
        group_signals = [s for s in self.signals.values() if s.group == group_name]

        if not group_signals:
            return {'error': f'No signals found in group {group_name}'}

        delays = {s.name: self.calculate_delay(s.length_mm) for s in group_signals}
        lengths = {s.name: s.length_mm for s in group_signals}

        min_delay = min(delays.values())
        max_delay = max(delays.values())
        skew = max_delay - min_delay

        min_length = min(lengths.values())
        max_length = max(lengths.values())
        length_diff = max_length - min_length

        # Determine max allowed skew based on group type
        if 'DATA' in group_name:
            max_allowed = self.skew_req.dq_to_dqs_max
        elif group_name == 'CLK':
            max_allowed = self.skew_req.ck_to_ckn_max
        else:
            max_allowed = self.skew_req.addr_cmd_to_ck_max

        return {
            'group': group_name,
            'signals': list(delays.keys()),
            'delays_ps': delays,
            'lengths_mm': lengths,
            'min_delay_ps': min_delay,
            'max_delay_ps': max_delay,
            'skew_ps': skew,
            'length_diff_mm': length_diff,
            'max_allowed_skew_ps': max_allowed,
            'status': 'PASS' if skew <= max_allowed else 'FAIL',
            'margin_ps': max_allowed - skew,
        }

    def analyze_dq_to_dqs_skew(self, byte_lane: int) -> Dict:
        """Analyze DQ to DQS skew within a byte lane"""
        dqs_name = f'DQS{byte_lane}'
        dq_prefix = f'DQ{byte_lane * 8}' if byte_lane == 0 else f'DQ{byte_lane * 8}'

        # Find DQS signal
        dqs_signal = self.signals.get(dqs_name)
        if not dqs_signal:
            return {'error': f'DQS{byte_lane} not found'}

        dqs_delay = self.calculate_delay(dqs_signal.length_mm)

        # Find all DQ signals in this byte lane
        dq_signals = []
        for i in range(8):
            dq_name = f'DQ{byte_lane * 8 + i}'
            if dq_name in self.signals:
                dq_signals.append(self.signals[dq_name])

        if not dq_signals:
            return {'error': f'No DQ signals found for byte lane {byte_lane}'}

        results = []
        for dq in dq_signals:
            dq_delay = self.calculate_delay(dq.length_mm)
            skew = abs(dq_delay - dqs_delay)
            results.append({
                'dq': dq.name,
                'dq_delay_ps': dq_delay,
                'dq_length_mm': dq.length_mm,
                'skew_to_dqs_ps': skew,
                'status': 'PASS' if skew <= self.skew_req.dq_to_dqs_max else 'FAIL',
            })

        max_skew = max(r['skew_to_dqs_ps'] for r in results)

        return {
            'byte_lane': byte_lane,
            'dqs': dqs_name,
            'dqs_delay_ps': dqs_delay,
            'dqs_length_mm': dqs_signal.length_mm,
            'dq_results': results,
            'max_skew_ps': max_skew,
            'max_allowed_ps': self.skew_req.dq_to_dqs_max,
            'overall_status': 'PASS' if max_skew <= self.skew_req.dq_to_dqs_max else 'FAIL',
        }

    def analyze_clock_differential(self) -> Dict:
        """Analyze CK/CK# differential pair matching"""
        ck = self.signals.get('CK')
        ck_n = self.signals.get('CK#')

        if not ck or not ck_n:
            return {'error': 'CK or CK# not found'}

        ck_delay = self.calculate_delay(ck.length_mm)
        ck_n_delay = self.calculate_delay(ck_n.length_mm)
        skew = abs(ck_delay - ck_n_delay)
        length_diff = abs(ck.length_mm - ck_n.length_mm)

        return {
            'ck_length_mm': ck.length_mm,
            'ck_delay_ps': ck_delay,
            'ck#_length_mm': ck_n.length_mm,
            'ck#_delay_ps': ck_n_delay,
            'skew_ps': skew,
            'length_diff_mm': length_diff,
            'max_allowed_ps': self.skew_req.ck_to_ckn_max,
            'status': 'PASS' if skew <= self.skew_req.ck_to_ckn_max else 'FAIL',
        }

    def calculate_timing_budget(self) -> Dict:
        """Calculate overall timing budget for the DDR3 interface"""
        spec = self.spec
        tCK = spec.tCK_min  # Use minimum clock period (worst case)

        # Flight time budget - typically want signals to arrive well within setup window
        # For address/command: setup time is relative to clock
        addr_setup_budget = spec.tIS_base

        # For DQ: setup/hold relative to DQS
        dq_setup = spec.tDS
        dq_hold = spec.tDH

        # Calculate max allowed trace length difference based on timing
        max_skew_for_setup = addr_setup_budget * 0.5  # Use 50% for margin
        max_length_diff_mm = max_skew_for_setup / self.propagation_delay_ps_per_mm

        return {
            'speed_grade': self.speed_grade.name,
            'tCK_ps': tCK,
            'frequency_MHz': 1e6 / tCK,
            'data_rate_MT_s': 2e6 / tCK,
            'propagation_delay_ps_per_mm': self.propagation_delay_ps_per_mm,
            'propagation_delay_ps_per_inch': self.propagation_delay_ps_per_inch,
            'addr_cmd_setup_budget_ps': addr_setup_budget,
            'dq_setup_ps': dq_setup,
            'dq_hold_ps': dq_hold,
            'recommended_max_length_diff_mm': max_length_diff_mm,
            'material': self.material['name'],
            'Er': self.material['Er'],
        }

    def generate_report(self) -> str:
        """Generate a comprehensive timing analysis report"""
        lines = []
        lines.append("=" * 70)
        lines.append("DDR3 TIMING ANALYSIS REPORT")
        lines.append("=" * 70)
        lines.append("")

        # Material and speed info
        budget = self.calculate_timing_budget()
        lines.append("CONFIGURATION:")
        lines.append(f"  PCB Material: {budget['material']}")
        lines.append(f"  Dielectric Constant (Er): {budget['Er']}")
        lines.append(f"  Speed Grade: {budget['speed_grade']}")
        lines.append(f"  Clock Period: {budget['tCK_ps']:.0f} ps")
        lines.append(f"  Frequency: {budget['frequency_MHz']:.1f} MHz")
        lines.append(f"  Data Rate: {budget['data_rate_MT_s']:.0f} MT/s")
        lines.append("")
        lines.append("PROPAGATION CHARACTERISTICS:")
        lines.append(f"  Delay: {budget['propagation_delay_ps_per_mm']:.2f} ps/mm")
        lines.append(f"  Delay: {budget['propagation_delay_ps_per_inch']:.1f} ps/inch")
        lines.append(f"  Recommended max length difference: {budget['recommended_max_length_diff_mm']:.2f} mm")
        lines.append("")

        # Check if we have signals to analyze
        if not self.signals:
            lines.append("WARNING: No signals defined. Add signals to analyze.")
            return '\n'.join(lines)

        # Clock analysis
        if 'CK' in self.signals and 'CK#' in self.signals:
            lines.append("-" * 70)
            lines.append("CLOCK DIFFERENTIAL PAIR ANALYSIS:")
            lines.append("-" * 70)
            clk_result = self.analyze_clock_differential()
            if 'error' not in clk_result:
                lines.append(f"  CK length:  {clk_result['ck_length_mm']:.2f} mm ({clk_result['ck_delay_ps']:.1f} ps)")
                lines.append(f"  CK# length: {clk_result['ck#_length_mm']:.2f} mm ({clk_result['ck#_delay_ps']:.1f} ps)")
                lines.append(f"  Skew: {clk_result['skew_ps']:.1f} ps (max allowed: {clk_result['max_allowed_ps']} ps)")
                lines.append(f"  Status: {clk_result['status']}")
            lines.append("")

        # Byte lane analysis
        for lane in range(2):
            dqs_name = f'DQS{lane}'
            if dqs_name in self.signals:
                lines.append("-" * 70)
                lines.append(f"BYTE LANE {lane} (DQ{lane*8}-DQ{lane*8+7} to DQS{lane}) ANALYSIS:")
                lines.append("-" * 70)
                result = self.analyze_dq_to_dqs_skew(lane)
                if 'error' not in result:
                    lines.append(f"  DQS{lane} length: {result['dqs_length_mm']:.2f} mm ({result['dqs_delay_ps']:.1f} ps)")
                    lines.append("")
                    for dq in result['dq_results']:
                        status_mark = "✓" if dq['status'] == 'PASS' else "✗"
                        lines.append(f"  {dq['dq']:5s}: {dq['dq_length_mm']:6.2f} mm, "
                                   f"skew: {dq['skew_to_dqs_ps']:5.1f} ps [{status_mark}]")
                    lines.append("")
                    lines.append(f"  Max skew: {result['max_skew_ps']:.1f} ps (limit: {result['max_allowed_ps']} ps)")
                    lines.append(f"  Byte Lane Status: {result['overall_status']}")
                lines.append("")

        # Address/Command group analysis
        groups_to_check = ['ADDRESS', 'BANK', 'COMMAND']
        for group in groups_to_check:
            group_signals = [s for s in self.signals.values() if s.group == group]
            if group_signals:
                lines.append("-" * 70)
                lines.append(f"{group} SIGNAL GROUP ANALYSIS:")
                lines.append("-" * 70)
                result = self.analyze_group_skew(group)
                if 'error' not in result:
                    for sig, delay in sorted(result['delays_ps'].items()):
                        length = result['lengths_mm'][sig]
                        lines.append(f"  {sig:8s}: {length:6.2f} mm ({delay:6.1f} ps)")
                    lines.append("")
                    lines.append(f"  Group skew: {result['skew_ps']:.1f} ps (limit: {result['max_allowed_skew_ps']} ps)")
                    lines.append(f"  Length variation: {result['length_diff_mm']:.2f} mm")
                    lines.append(f"  Status: {result['status']}")
                lines.append("")

        lines.append("=" * 70)
        lines.append("END OF REPORT")
        lines.append("=" * 70)

        return '\n'.join(lines)

    def get_length_targets(self, reference_length_mm: float) -> Dict[str, Tuple[float, float]]:
        """
        Calculate target length ranges for all signal groups based on a reference.
        Returns dict with (min_length, max_length) tuples.
        """
        targets = {}

        # Clock - very tight matching
        clk_tolerance = self.skew_req.ck_to_ckn_max / self.propagation_delay_ps_per_mm
        targets['CLK'] = (reference_length_mm - clk_tolerance/2,
                         reference_length_mm + clk_tolerance/2)

        # Data groups - match to DQS
        dq_tolerance = self.skew_req.dq_to_dqs_max / self.propagation_delay_ps_per_mm
        targets['DATA'] = (reference_length_mm - dq_tolerance/2,
                          reference_length_mm + dq_tolerance/2)

        # Address/Command
        addr_tolerance = self.skew_req.addr_cmd_to_ck_max / self.propagation_delay_ps_per_mm
        targets['ADDR_CMD'] = (reference_length_mm - addr_tolerance/2,
                              reference_length_mm + addr_tolerance/2)

        return targets


# =============================================================================
# Example Usage / Main
# =============================================================================

def create_example_signals() -> Dict[str, Dict]:
    """Create example signal definitions - replace with your actual trace lengths"""
    signals = {}

    # Clock signals (differential pair)
    signals['CK'] = {'length_mm': 50.0, 'layer': 3, 'group': 'CLK', 'impedance': 100}
    signals['CK#'] = {'length_mm': 50.1, 'layer': 3, 'group': 'CLK', 'impedance': 100}

    # Byte Lane 0 - DQ0-7, DQS0, DM0
    base_len_bl0 = 45.0
    signals['DQS0'] = {'length_mm': base_len_bl0, 'layer': 3, 'group': 'DATA0', 'impedance': 100}
    signals['DQS0#'] = {'length_mm': base_len_bl0 + 0.1, 'layer': 3, 'group': 'DATA0', 'impedance': 100}
    signals['DM0'] = {'length_mm': base_len_bl0 + 0.5, 'layer': 3, 'group': 'DATA0', 'impedance': 50}
    for i in range(8):
        # Simulate some variation in trace lengths
        signals[f'DQ{i}'] = {'length_mm': base_len_bl0 + (i-4)*0.3, 'layer': 3, 'group': 'DATA0', 'impedance': 50}

    # Byte Lane 1 - DQ8-15, DQS1, DM1
    base_len_bl1 = 48.0
    signals['DQS1'] = {'length_mm': base_len_bl1, 'layer': 3, 'group': 'DATA1', 'impedance': 100}
    signals['DQS1#'] = {'length_mm': base_len_bl1 + 0.1, 'layer': 3, 'group': 'DATA1', 'impedance': 100}
    signals['DM1'] = {'length_mm': base_len_bl1 + 0.4, 'layer': 3, 'group': 'DATA1', 'impedance': 50}
    for i in range(8):
        signals[f'DQ{i+8}'] = {'length_mm': base_len_bl1 + (i-4)*0.25, 'layer': 3, 'group': 'DATA1', 'impedance': 50}

    # Address signals
    addr_base = 52.0
    for i in range(16):
        signals[f'A{i}'] = {'length_mm': addr_base + (i % 5) * 0.2, 'layer': 1, 'group': 'ADDRESS', 'impedance': 50}

    # Bank address
    for i in range(3):
        signals[f'BA{i}'] = {'length_mm': addr_base + 0.5 + i*0.15, 'layer': 1, 'group': 'BANK', 'impedance': 50}

    # Command signals
    cmd_base = 51.0
    for i, cmd in enumerate(['RAS#', 'CAS#', 'WE#', 'CS#', 'CKE', 'ODT', 'RESET#']):
        signals[cmd] = {'length_mm': cmd_base + i*0.2, 'layer': 1, 'group': 'COMMAND', 'impedance': 50}

    return signals


def main():
    print("DDR3 Timing Analysis Tool")
    print("Using JLCPCB FR-4 Standard material constants")
    print("")

    # Create analyzer with JLCPCB material and DDR3-1600 speed grade
    analyzer = DDR3TimingAnalyzer(
        material=JLCPCBMaterial.FR4_STANDARD,
        speed_grade=DDR3Speed.DDR3_1600
    )

    # Add example signals (replace with your actual trace lengths from PCB design)
    example_signals = create_example_signals()
    analyzer.add_signals_from_dict(example_signals)

    # Generate and print the report
    report = analyzer.generate_report()
    print(report)

    # Print length targets for routing
    print("\n" + "=" * 70)
    print("RECOMMENDED LENGTH TARGETS (based on 50mm reference):")
    print("=" * 70)
    targets = analyzer.get_length_targets(50.0)
    for group, (min_len, max_len) in targets.items():
        print(f"  {group:12s}: {min_len:.2f} mm to {max_len:.2f} mm (±{(max_len-min_len)/2:.2f} mm)")

    # Show timing budget summary
    print("\n" + "=" * 70)
    print("TIMING SPECIFICATIONS FOR DDR3-1600:")
    print("=" * 70)
    budget = analyzer.calculate_timing_budget()
    print(f"  Address/Command setup: {budget['addr_cmd_setup_budget_ps']:.0f} ps")
    print(f"  DQ setup time: {budget['dq_setup_ps']:.0f} ps")
    print(f"  DQ hold time: {budget['dq_hold_ps']:.0f} ps")


if __name__ == '__main__':
    main()
