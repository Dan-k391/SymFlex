> restart:
m:=100: P:=t+10: k:=.35: tf:=5: g:=9.81: IG:=k^2*m;
IIC:=IG+m*(.75)^2;
omegaf:=solve(int(P*(.4+.75),t=0..tf) = IIC*omegaf);
vf:=.75*omegaf;
