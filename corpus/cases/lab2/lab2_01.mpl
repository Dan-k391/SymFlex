# SOURCE: lab2 block 01 (para 6) - L9 work & kinetic energy on ramp (phi=45 deg)
restart:
W:=300: T:=100: theta:=10*Pi/180: phi:=45*Pi/180: s:=5:
Wx:=-300*sin(theta);
Tx:=T*cos(phi);
WorkW:=Wx*s; evalf(%);
WorkT:=Tx*s; evalf(%);
DeltaKE:=WorkW+WorkT; evalf(%);
