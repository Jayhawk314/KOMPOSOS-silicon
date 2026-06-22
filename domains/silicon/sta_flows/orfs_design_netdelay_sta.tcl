# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# Generic measured-tier net-delay for ANY self-minted ORFS nangate45 design.
#
# Mount the design's results/base dir (containing 6_final.def/.spef/.sdc) as /work and run
# under OpenROAD (embeds OpenSTA). Same recipe as orfs_gcd_netdelay_sta.tcl, de-hardcoded so
# aes / ibex / etc. reuse it. `-fields {input_pins ...}` renders the load INPUT-pin rows whose
# incremental Delay column IS the net (wire) delay; net_delay.py attributes each row to its net
# via the DEF pin->net map. Uses the in-image ORFS nangate45 libs (same libs that minted it).

read_lef /OpenROAD-flow-scripts/flow/platforms/nangate45/lef/NangateOpenCellLibrary.tech.lef
read_lef /OpenROAD-flow-scripts/flow/platforms/nangate45/lef/NangateOpenCellLibrary.macro.mod.lef
read_liberty /OpenROAD-flow-scripts/flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib
read_def /work/6_final.def
read_spef /work/6_final.spef
read_sdc /work/6_final.sdc

# -digits 5: 45nm wire delays are tiny; default 2-digit rounding floors them to 0.00.
# input_pins -> load-pin rows (Delay col = wire delay); broad coverage so most nets appear.
report_checks \
    -path_delay min_max \
    -fields {input_pins net capacitance slew fanout} \
    -digits 5 \
    -group_path_count 5000 \
    -endpoint_path_count 20 \
    -slack_max 1e30 \
    -slack_min -1e30 \
    > /work/6_final.netdelay.report_checks.txt

puts "wrote /work/6_final.netdelay.report_checks.txt"
exit
