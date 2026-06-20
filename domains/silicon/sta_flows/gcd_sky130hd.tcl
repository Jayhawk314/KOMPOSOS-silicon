# Real OpenSTA report_checks flow for the bundled gcd_sky130hd design.
# Reads Liberty (typical corner), gate netlist, SPEF parasitics, and SDC,
# then dumps one path per endpoint (setup) so the silicon STA ingestion has
# real timing ground truth with full design context.
#
# Files come from the openroad/opensta image's /OpenSTA/examples (staged into /work).
read_liberty /work/sky130hd_tt.lib.gz
read_verilog /work/gcd_sky130hd.v
link_design gcd
read_spef /work/gcd_sky130hd.spef
source /work/gcd_sky130hd.sdc
report_checks -path_delay max -group_path_count 1000 -endpoint_path_count 1 -slack_max 1e30 -digits 4
