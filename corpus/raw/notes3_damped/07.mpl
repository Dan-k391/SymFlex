restart;
w0:=10: x0:=1: zeta:=1/16:
ode:= diff(x(t), t,t)+2*zeta*w0*diff(x(t),t)+w0^2*x(t)=x0*w0^2*sin(omega*t):
ics:=x(0)=0, D(x)(0)=0;
dsolve({ode, ics});
assign(%):
plot([subs(omega=2, x(t)), subs(omega=10, x(t)), subs(omega=50, x(t))],
t=0..10);
