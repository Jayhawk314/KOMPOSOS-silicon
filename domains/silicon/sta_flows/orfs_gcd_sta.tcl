# STA on the SELF-MINTED gcd layout (ORFS nangate45 RTL->GDSII, results/base/6_final.def).
#
# This is the end-to-end story: we synthesized + placed + routed gcd ourselves with the
# open flow, then read the routed DEF + extracted SPEF back and run real timing on it.
# Instance names in the report == instance names in 6_final.def by construction, so the
# scoreboard maps critical nets onto our own layout with no guesswork.
#
# Uses the ORFS nangate45 platform tech/macro LEF + Liberty (the same libs the flow used),
# referenced by their in-image paths. Constraints (tight 0.40 ns clock) in orfs_gcd.sdc.
read_lef /OpenROAD-flow-scripts/flow/platforms/nangate45/lef/NangateOpenCellLibrary.tech.lef
read_lef /OpenROAD-flow-scripts/flow/platforms/nangate45/lef/NangateOpenCellLibrary.macro.mod.lef
read_liberty /OpenROAD-flow-scripts/flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib
read_def /work/results/base/6_final.def
read_spef /work/results/base/6_final.spef
source /work/orfs_gcd.sdc
report_checks -path_delay max -group_path_count 1000 -endpoint_path_count 1 -slack_max 1e30 -digits 4
