> restart;
M:=0.5: q:=0.1: vfuel:=250: g:=9.81: mfi:=q*vfuel/g-M;
tfuel:=mfi/q:
a:=piecewise(t<tfuel, -g+q*vfuel/(M+mfi-q*t), t>=tfuel, -g);
v:=simplify(int(a, t=0..t));
y:=simplify(int(v, t=0..t));
plot([a*20, v*5, y], t=0..50);
ymax:=maximize(y);
