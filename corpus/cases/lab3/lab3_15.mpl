# SOURCE: lab3 block 15 (para 412) - L18 linear damper with dsolve
restart: m:=1.9: k:=300: b:=10: s0:=0.1: v0:=0:
omega0:=sqrt(k/m); zeta:=b/(2*sqrt(m*k)); omegad:=omega0*sqrt(1-zeta^2);
Td:=2*Pi/omegad;
Fnet:=-k*s(t)-b*D(s)(t);
dsolve({m*diff(s(t),t,t)=Fnet, s(0)=s0, D(s)(0)=v0});
s:=rhs(%): v:=diff(s,t): a:=diff(v,t):
KE:=.5*m*v^2: U:=.5*k*s^2:
plot([s, v/10, a/100],t=0..2*Td, legend=['s','v/10','a/100']);
plot([KE,U,KE+U],t=0..2*Td,legend=['KE','U','KE+U']);
