restart;
mi:=2: q:=0.1: vfuel:=250: g:=9.81:
a:=piecewise(t<mi/(2*q), -g+q*vfuel/(mi-q*t), t>=mi/(2*q), -g);
v:=simplify(int(a, t=0..t));
y:=simplify(int(v, t=0..t));
plot([a*20, v*5, y], t=0..20);
ymax:=maximize(y);
