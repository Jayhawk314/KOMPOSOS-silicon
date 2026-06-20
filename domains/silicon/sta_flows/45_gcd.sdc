# Constraints for the 45_gcd (Nangate45 gcd) STA run. Clock tightened to 0.3 ns on
# purpose to surface real violating paths (=> real critical nets for the scoreboard).
set period 0.3
create_clock -name clk -period $period [get_ports clk]
set delay [expr $period * 0.2]
set_input_delay $delay -clock clk [get_ports {req_val reset resp_rdy}]
set_input_delay $delay -clock clk [get_ports req_msg*]
set_output_delay $delay -clock clk [all_outputs]
set_input_transition 0.1 [all_inputs]
