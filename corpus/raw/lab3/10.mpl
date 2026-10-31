> restart: m:=1.9: k:=300: s0:=0.1: v0:=0:
Fnet:=-k*s(t):
DE:=m*diff(s(t),t,t)=Fnet;
dsolve({DE, s(0)=s0, D(s)(0)=v0});
s:=rhs(%): v:=diff(s,t): a:=diff(v,t):
omega:=sqrt(k/m): T:=2*Pi/omega;
plot([s,v/10,a/100],t=0..T);
KE:=0.5*m*v^2: Us:=0.5*k*s^2:
plot([KE, Us,KE+Us],t=0..T);
