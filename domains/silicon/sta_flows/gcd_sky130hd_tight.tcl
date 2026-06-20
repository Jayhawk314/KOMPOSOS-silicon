# Same real gcd_sky130hd design, clock tightened 5x (period 5 -> 1 ns) to force
# real setup violations. This exercises the measured-tier path on a STRESSED real
# design: genuine negative slacks + critical-net mapping, not a fabricated number.
read_liberty /work/sky130hd_tt.lib.gz
read_verilog /work/gcd_sky130hd.v
link_design gcd
read_spef /work/gcd_sky130hd.spef
set period 1.0
create_clock -period $period [get_ports clk]
set delay [expr $period * 0.2]
set_input_delay $delay -clock clk {req_val reset resp_rdy req_msg[*]}
set_output_delay $delay -clock clk [all_outputs]
set_input_transition .1 [all_inputs]
report_checks -path_delay max -group_path_count 1000 -endpoint_path_count 1 -slack_max 1e30 -digits 4
