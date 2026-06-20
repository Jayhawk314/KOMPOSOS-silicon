# Real OpenROAD STA on our existing 45_gcd layout (Nangate45 placed gcd).
#
# Why this design: we already hold 45_gcd.def + 45_gcd.spefok + Nangate45.lef, and the
# nangate45 Liberty ships in the openroad/opensta image. Running STA *directly on the
# DEF* means the report's instance names (_255_, _258_, ...) are IDENTICAL to what
# netlist_bridge parses from the same DEF -- so critical_nets() maps report -> layout
# with no name-matching guesswork. This is the matched DEF+report the cross-mapping
# scoreboard needs. Constraints live in 45_gcd.sdc (hashed as the constraints receipt).
read_lef /work/Nangate45.lef
read_liberty /work/nangate45_typ.lib.gz
read_def /work/45_gcd.def
read_spef /work/45_gcd.spef
source /work/45_gcd.sdc
report_checks -path_delay max -group_path_count 1000 -endpoint_path_count 1 -slack_max 1e30 -digits 4
