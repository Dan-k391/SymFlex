# SOURCE: lab3 block 30 (para 708) - L19 forced response low frequency
restart: m:=1.9: k:=300: b:=2: omega0:=sqrt(k/m);
omega:=omega0/5;
F:=5*cos(omega*t): se:=F/k; #If got to equilibrium instantly:
dsolve({m*diff(s(t),t,t)+b*diff(s(t),t)+k*s(t)=F, s(0)=0, D(s)(0)=0}): s:=evalf(rhs(%)); plot([s, se], t=0..10); plot([s, se], t=0..10, numpoints=1000);
