> restart: m:=500: g:=9.81: vret:=t^3*(t+27):
vdown:=-1/4*vret; vup:=-vdown;
y:=int(vup, t=0..t); plot(y, t=0..1):
sdotdot:=diff(-1/4*vret, t);
T:=(m*g-m*sdotdot)/4;
plot(T, t=0..2);
fsolve(T=5e3,t=1..1.4);
solve(T=5e3);
