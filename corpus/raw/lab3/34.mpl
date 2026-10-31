restart: b:=30:
k:=800.8: m:=20: omega0:=sqrt(k/m); zeta:=b/(2*sqrt(m*k)); sc:=.01*sin(omega*t):
Q:=1/(2*zeta): s0:=-.01*Q: #start conditions don't matter for steady-state response
dsolve({m*diff(s(t),t,t)+b*diff(s(t),t)+k*s(t)=k*sc, s(0)=s0, D(s)(0)=0}):
s:=evalf(rhs(%));
a1:=coeff(s, sin(omega*t)); a2:=coeff(s, cos(omega*t));
A:=evalf(simplify(sqrt(a1^2+a2^2))); phi:=arctan(-a2, a1); phideg:=phi*180/3.14159;
with(plots):
loglogplot(A, omega=1..100); semilogplot(phi, omega=1..100);
