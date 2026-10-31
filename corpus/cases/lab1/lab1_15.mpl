# SOURCE: lab1 block 15 (para 399) - It looks like it first exceeds 2300 N between 3 and 4 s, so fsolve in ...
# DEPENDS: lab1_14
restart: mc:=200: vc0:=.5: vc:=.5*(1+t*(sin(t))^2): g:=9.81:
W:=mc*g;
ac:=diff(vc,t);
FNetc:=ac*mc;
Tc:=FNetc+W;
plot(Tc, t=0..6);
fsolve(Tc=2300, t=3..4);
