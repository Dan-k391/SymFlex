# SOURCE: lab1 block 19 (para 453) - fsolve(Tc=2400) with no range (doc labels the result "(wrong)")
# DEPENDS: lab1_17
# NOTE: intentionally "wrong" per doc: without a range fsolve returns -3.905324933 (doc image92 matches), vs 3.905324933 with t=3..4
restart: mc:=200: vc0:=.5: vc:=.5*(1+t*(sin(t))^2): g:=9.81:
W:=mc*g;
ac:=diff(vc,t);
FNetc:=ac*mc;
Tc:=FNetc+W;
plot(Tc, t=4..4.1);
fsolve(Tc=2400);
