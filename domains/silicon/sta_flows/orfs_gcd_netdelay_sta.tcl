# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# measured-tier net-delay on the SELF-MINTED orfs_gcd layout (results/base/6_final.*).
#
# Same idea as tau_netdelay_sta.tcl (45_gcd) but on orfs_gcd, our full-file design.
# Run under OpenROAD (embeds OpenSTA) so it reads DEF+SPEF+LEF. `-fields {input_pins ...}`
# renders the load INPUT-pin rows whose incremental Delay column IS the net (wire) delay;
# net_delay.py attributes each load-pin row to its net via the DEF pin->net map.
# Uses the in-image ORFS nangate45 platform libs (same libs the flow used to mint it).

read_lef /OpenROAD-flow-scripts/flow/platforms/nangate45/lef/NangateOpenCellLibrary.tech.lef
read_lef /OpenROAD-flow-scripts/flow/platforms/nangate45/lef/NangateOpenCellLibrary.macro.mod.lef
read_liberty /OpenROAD-flow-scripts/flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib
read_def /work/results/base/6_final.def
read_spef /work/results/base/6_final.spef
source /work/orfs_gcd.sdc

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
