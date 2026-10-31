> restart: mc:=200: vc0:=.5: vc:=3*(2*t+t^2+t^3/3): g:=9.81:
W:=mc*g;
ac:=diff(vc,t);
FNetc:=ac*mc;
Tc:=FNetc+W;
T:=Tc/2;
plot(T, t=0..6);
