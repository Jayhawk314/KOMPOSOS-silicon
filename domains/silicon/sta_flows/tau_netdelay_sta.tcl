# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# tau measured-tier upgrade: emit per-net INTERCONNECT (wire) delay for 45_gcd.
#
# Run under OpenROAD (which embeds OpenSTA), NOT plain OpenSTA, because we read DEF+LEF.
# The key is `-fields {input_pins ...}`: it renders the load INPUT-pin rows whose
# incremental Delay column IS the net (wire) delay. Broad path coverage (-group_count /
# -endpoint_count large, -slack_max large) so most signal nets appear on some reported
# path. domains/silicon/net_delay.py attributes each load-pin row to its net via the DEF
# pin->net map (no dependence on the report's net-name text).
#
# Mounts: stage 45_gcd.def, 45_gcd.spef, 45_gcd.sdc, Nangate45.lef, nangate45_typ.lib
# (gunzip the .lib.gz first) into /work. See README.md "tau net-delay (measured)".

read_lef   /work/Nangate45.lef
read_liberty /work/nangate45_typ.lib
read_def   /work/45_gcd.def
read_spef  /work/45_gcd.spef
read_sdc   /work/45_gcd.sdc

# Report a large number of max-delay paths regardless of slack, with input pins + net
# fields so wire-delay rows are emitted. Tune the counts up if net coverage is low.
# -digits 5: default 2-digit rounding floors 45nm wire delays to 0.00 -- need precision.
# input_pins makes load-pin rows (whose Delay column IS the wire delay) appear.
# min_max + many paths per endpoint widens net coverage (more nets appear as load rows).
report_checks \
    -path_delay min_max \
    -fields {input_pins net capacitance slew fanout} \
    -digits 5 \
    -group_path_count 5000 \
    -endpoint_path_count 20 \
    -slack_max 1e30 \
    -slack_min -1e30 \
    > /work/45_gcd.netdelay.report_checks.txt

puts "wrote /work/45_gcd.netdelay.report_checks.txt"
exit
