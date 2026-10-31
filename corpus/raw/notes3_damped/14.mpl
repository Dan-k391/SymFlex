restart;
m:=1: y0:=.05: g:=9.81: W:=m*g: k:=W/y0: x0:=+0.02: v0:=0:
b:=sqrt(4*m*k)/8:
ode:= m*diff(x(t), t,t)+b*diff(x(t),t)+k*x(t)=3*sin(omega*t);
ics:= x(0)=x0, D(x)(0)=v0;
interface(displayprecision=4): #Makes Maple only show 4 decimals in its
displayed output
evalf(dsolve({ode,ics}));
assign(%):
subs(omega=3, x(t));
plot([%, 0.016*cos(3*t)], t=0..8);
