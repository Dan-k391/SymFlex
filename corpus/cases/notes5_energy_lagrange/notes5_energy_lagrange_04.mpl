# SOURCE: notes5_energy_lagrange block 04 (pages 9-10) - eg 19.3 spool solved about centre with constant FA
restart:
m:=100: P:=t+10: k:=.35: tf:=5: g:=9.81: IG:=k^2*m;
solve([
0+int(P-FA, t=0..tf)=m*vxf,
0+int(NA-m*g, t=0..tf)=0,
0+int(P*.4 + FA*.75, t=0..tf) = IG*omegaf,
omegaf*.75=vxf]);
