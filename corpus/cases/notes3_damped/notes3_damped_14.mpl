# SOURCE: notes3_damped block 14 (page 30) - Typical linear DE solve with displayprecision=4
# NOTE: Maple 2024 evalf(dsolve) prints x(t) with huge scaled coefficients (0.1081e38 ...) instead of doc's normalized form; subs(omega=3, x(t)) gives -0.0008 e^(-1.7509t) sin(13.8973t)+0.0209 e^(-1.7509t) cos(13.8973t)+0.0160 sin(3t)-0.0009 cos(3t) with displayprecision=4 (doc shows 3 sig. figs: -0.000817, 0.0208, 0.0159, -0.000893, labelled "x :=").
restart;
m:=1: y0:=.05: g:=9.81: W:=m*g: k:=W/y0: x0:=+0.02: v0:=0:
b:=sqrt(4*m*k)/8:
ode:= m*diff(x(t), t,t)+b*diff(x(t),t)+k*x(t)=3*sin(omega*t);
ics:= x(0)=x0, D(x)(0)=v0;
interface(displayprecision=4): #Makes Maple only show 4 decimals in its displayed output
evalf(dsolve({ode,ics}));
assign(%):
subs(omega=3, x(t));
plot([%, 0.016*cos(3*t)], t=0..8);
