# SOURCE: lab1 block 08 (para 252) - Repeat if the coefficient of kinetic friction were doubled.
restart: m:=40: g:=9.81: mu_s:=.8: mu_k:=.6: P:=370:
fsMax:=mu_s*N: W:=m*g;
ff:=mu_k*N:
FNetx:=P*cos(Pi/6)-W*sin(Pi/6)-ff;
FNety:=P*sin(Pi/6)-W*cos(Pi/6)+N;
solve([FNetx=m*ax,FNety]); #just barely moving when net force = 0 and at max static friction
assign(%):
s:=int(int(ax, t=0..t), t=0..t);
solve(s=3);
