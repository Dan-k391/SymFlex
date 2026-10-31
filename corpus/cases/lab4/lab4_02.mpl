# SOURCE: lab4 block 02 (para 36) - L21 check: table response via dsolve
restart: omega:=2*Pi*100.: sf0:=1e-3: omega0t:=2*Pi: omega0b:=2*Pi*100: Qt:=10: Qb:=20:
sf:=sf0*cos(omega*t): omegatr:=omega/omega0t:
dsolve({diff(st(t),t,t)+omega0t/Qt*diff(st(t),t)+omega0t^2*(st(t)-sf), st(0)=0, D(st)(0)=0}): st:=rhs(%):
plot([st, sf0/omegatr^2*cos(omega*t-Pi)], t=20..20.05);
#plot once in steady-state
