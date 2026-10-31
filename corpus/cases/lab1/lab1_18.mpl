# SOURCE: lab1 block 18 (para 450) - Therefore, Tc = 2400 is to the left of t = 4, so use fsolve on the ran...
# DEPENDS: lab1_17
restart: mc:=200: vc0:=.5: vc:=.5*(1+t*(sin(t))^2): g:=9.81:
W:=mc*g;
ac:=diff(vc,t);
FNetc:=ac*mc;
Tc:=FNetc+W;
plot(Tc, t=4..4.1);
fsolve(Tc=2400, t=3..4);
