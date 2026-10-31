# SOURCE: notes3_damped block 12 (page 28) - Compare response at omega0, omega_d, omega_max
# NOTE: numeric coefficients differ in last digits from doc (e.g. doc 8.007820382 vs 8.007820173 in Maple 2024 at Digits=10); third result also contains a tiny -0.64e-8*exp(..)*sin(..) term not in doc. Compare with tolerance.
restart;
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
