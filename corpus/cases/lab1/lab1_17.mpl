# SOURCE: lab1 block 17 (para 438) - Now we need to adjust the range a bit to see which part it first goes ...
restart: mc:=200: vc0:=.5: vc:=.5*(1+t*(sin(t))^2): g:=9.81:
W:=mc*g;
ac:=diff(vc,t);
FNetc:=ac*mc;
Tc:=FNetc+W;
plot(Tc, t=4..4.1);
