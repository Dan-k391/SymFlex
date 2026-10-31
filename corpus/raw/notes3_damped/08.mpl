> restart:
zeta:=1/16: omega0:=10:
DE:=diff(x(t),t,t)+2*zeta*omega0*diff(x(t),t)
+omega0^2*x(t)=omega0^2*sin(omega*t);
ICs:=x(0)=0,D(x)(0)=0:
dsolve([subs(omega=2, DE), ICs]): xLF:=rhs(%):
dsolve([subs(omega=50, DE), ICs]): xHF:=rhs(%):
dsolve([subs(omega=10, DE), ICs]): xRF:=rhs(%):
dsolve([diff(x(t),t,t)+2*zeta*omega0*diff(x(t),t)
+omega0^2*x(t)=omega0^2*(sin(2*t)+sin(10*t)+sin(50*t)), ICs]):
xMF:=rhs(%):
plot([xLF, xHF, xRF, xMF], t=0..20);
