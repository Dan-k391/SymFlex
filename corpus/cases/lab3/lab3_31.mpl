# SOURCE: lab3 block 31 (para 721) - L19 forced response at resonance
restart: m:=1.9: k:=300: b:=2: omega0:=sqrt(k/m);
omega:=omega0;
F:=5*cos(omega*t): se:=F/k; #If got to equilibrium instantly:
dsolve({m*diff(s(t),t,t)+b*diff(s(t),t)+k*s(t)=F, s(0)=0, D(s)(0)=0}): s:=evalf(rhs(%)); plot([s, se], t=0..10, numpoints=1000);
