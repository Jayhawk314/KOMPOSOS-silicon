# Constraints for STA on the SELF-MINTED gcd (ORFS nangate45 RTL->GDSII output,
# results/base/6_final.def). The flow optimized to a 0.46 ns clock and met timing at
# the edge (worst slack +0.01 ns, min period 0.44). We tighten to 0.40 ns here to push
# the real near-critical paths into violation, so the scoreboard has real critical nets.
set period 0.40
create_clock -name clk -period $period [get_ports clk]
set delay [expr $period * 0.2]
set_input_delay $delay -clock clk [get_ports {req_val reset resp_rdy}]
set_input_delay $delay -clock clk [get_ports req_msg*]
set_output_delay $delay -clock clk [all_outputs]
set_input_transition 0.1 [all_inputs]
