> restart: omega:=2*Pi*100.: sf0:=1e-3: omega0t:=2*Pi: omega0b:=2*Pi*100: Qt:=10: Qb:=20:
sf:=sf0*cos(omega*t): omegatr:=omega/omega0t:
st:=sf0/omegatr^2*cos(omega*t-Pi):
dsolve({diff(sb(t),t,t)+omega0b/Qb*diff(sb(t),t)+omega0b^2*(sb(t)-st), sb(0)=0, D(sb)(0)=0}): sb:=rhs(%):
plot([sb, st, Qb/100^2*sf0*cos(omega*t-3/2*Pi)], t=20..20.05); #plot once in steady-state
