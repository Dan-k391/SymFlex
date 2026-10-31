# SOURCE: lab3 block 25 (para 622) - P18.1 mod energy per cycle continued
# DEPENDS: lab3_24
# --- prepended from lab3 block 24 ---
restart: b:=30: k:=800.8: m:=20: omega0:=sqrt(k/m); zeta:=b/(2*sqrt(m*k)); T0:=evalf(2*Pi/omega0);
omegad:=omega0*sqrt(1-zeta^2); Td:=evalf(2*Pi/omegad);
dsolve({m*diff(s(t),t,t)+b*diff(s(t),t)+k*s(t), s(0)=.03, D(s)(0)=0});
s:=evalf(rhs(%));
v:=diff(s,t): a:=diff(v,t):
plot([s,v/10,a/100], t=0..2*Td, legend=['s','v/10','a/100']);
# --- end prepended ---
KE:=evalf(.5*m*v^2);
U:=evalf(.5*k*s^2);
E:=KE+U:
plot([KE,U,E], t=0..2*Td, legend=['KE','U','Etotal']);
E0:=evalf(subs(t=0,E));
E1:=evalf(subs(t=Td,E));
E2:=evalf(subs(t=2*Td,E));
FracLostInCycle1:=-(E1-E0)/E0;
FracLostInCycle2:=-(E2-E1)/E1;
