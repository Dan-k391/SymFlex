# SOURCE: notes2_nonlinear block 03 (page 7) - Rocket example 2: optimal fuel mass and max height
# NOTE: "> " prompt removed. Doc output is from an older Maple: v and y printed with ln(2.548419980-0.1000000000*t) and ymax := 3194.329850; Maple 2024 gives ln(-5000000.*t+127420999.) and ymax := 3194.329831
restart;
M:=0.5: q:=0.1: vfuel:=250: g:=9.81: mfi:=q*vfuel/g-M;
tfuel:=mfi/q:
a:=piecewise(t<tfuel, -g+q*vfuel/(M+mfi-q*t), t>=tfuel, -g);
v:=simplify(int(a, t=0..t));
y:=simplify(int(v, t=0..t));
plot([a*20, v*5, y], t=0..50);
ymax:=maximize(y);
