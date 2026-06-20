# Generic STA on a SELF-MINTED ORFS layout (nangate45). Stage the design's routed
# artifacts into /work as design.def / design.spef / design_tight.sdc, where the SDC is
# the flow's own 6_final.sdc with the clock period tightened (~0.9x of the achieved min
# period) to push real near-critical paths into violation. Instance names in the report
# == names in design.def by construction, so critical_nets() maps onto the layout exactly.
read_lef /OpenROAD-flow-scripts/flow/platforms/nangate45/lef/NangateOpenCellLibrary.tech.lef
read_lef /OpenROAD-flow-scripts/flow/platforms/nangate45/lef/NangateOpenCellLibrary.macro.mod.lef
read_liberty /OpenROAD-flow-scripts/flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib
read_def /work/design.def
read_spef /work/design.spef
source /work/design_tight.sdc
# slack_max 0 => report only the violating (timing-critical) paths, one per endpoint.
# That is exactly what critical_nets() consumes, and keeps the report lean on 30k-cell
# designs (no point dumping thousands of met paths).
report_checks -path_delay max -group_path_count 100000 -endpoint_path_count 1 -slack_max 0.0 -digits 4
