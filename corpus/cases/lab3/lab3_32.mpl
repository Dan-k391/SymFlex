# SOURCE: lab3 block 32 (para 748) - L19 mod resonance starting in steady state
restart: m:=1.9: k:=300: b:=2: omega0:=sqrt(k/m);
omega:=omega0;
F:=5*cos(omega*t): se:=F/k; #If got to equilibrium instantly:
A0:=5/k: zeta:=b/(2*m*omega0):
dsolve({m*diff(s(t),t,t)+b*diff(s(t),t)+k*s(t)=F, s(0)=0, D(s)(0)=A0/(2*zeta)*omega0}): s:=evalf(rhs(%)); plot([s, se], t=0..10, numpoints=1000);
