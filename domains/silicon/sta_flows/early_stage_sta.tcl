# EARLY-STAGE STA: timing on a design BEFORE the optimizer flattens the slack.
#
# Motivation: in the finished-design scoreboard, structural triage failed because
# timing-driven place/route equalizes slack (no spike left to predict). The only design
# that passed was less-optimized. So we test the honest question a designer actually has
# EARLY: at an un-optimized placement, does structure predict where timing trouble is?
#
# We load an early placement ODB (plain global placement + IO placement, BEFORE the
# timing-driven global place / resize / CTS / route), estimate placement parasitics,
# and run real timing there. The slack still has a wide spread at this stage.
read_liberty /OpenROAD-flow-scripts/flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib
read_db /work/early.odb
source /work/early_tight.sdc
estimate_parasitics -placement
write_spef /work/early.spef
write_def  /work/early.def
report_checks -path_delay max -group_path_count 100000 -endpoint_path_count 1 -slack_max 0.0 -digits 4
