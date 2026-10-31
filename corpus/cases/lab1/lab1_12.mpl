# SOURCE: lab1 block 12 (para 358) - We know the cylinder speed, but not the motor speed. The FBD above tel...
restart: mc:=200: vc0:=.5: vc:=.5*(1+t*(sin(t))^2): g:=9.81:
W:=mc*g;
ac:=diff(vc,t);
FNetc:=ac*mc;
Tc:=FNetc+W;
T:=Tc/2;
plot(T, t=0..6);
