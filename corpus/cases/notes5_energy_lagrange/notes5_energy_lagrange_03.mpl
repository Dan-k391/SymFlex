# SOURCE: notes5_energy_lagrange block 03 (page 9) - eg 19.3 spool, angular impulse-momentum about IC
# NOTE: omegaf appears on both sides of the assignment (solve for the unassigned name, then assign it).
restart:
m:=100: P:=t+10: k:=.35: tf:=5: g:=9.81: IG:=k^2*m;
IIC:=IG+m*(.75)^2;
omegaf:=solve(int(P*(.4+.75),t=0..tf) = IIC*omegaf);
vf:=.75*omegaf;
