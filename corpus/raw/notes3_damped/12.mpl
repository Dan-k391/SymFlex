> restart;
omega0:=10: x0:=1: zeta:=1/16:
ode:= diff(x(t), t,t)+2*zeta*omega0*diff(x(t),t)
+omega0^2*x(t)=x0*omega0^2*sin(omega*t):
ics:=x(0)=0, D(x)(0)=0;
dsolve({ode, ics});
x:=rhs(%):
omega_d:=evalf(omega0*sqrt(1-zeta^2));
omega_max:=evalf(omega0*sqrt(1-2*zeta^2));
evalf(subs(omega=omega0,x));
evalf(subs(omega=omega_d, x));
evalf(subs(omega=omega_max, x));
