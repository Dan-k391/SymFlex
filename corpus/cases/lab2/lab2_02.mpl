# SOURCE: lab2 block 02 (para 23) - L9 modification: pull angle 15 deg
restart:
W:=300: T:=100: theta:=10*Pi/180: phi:=15*Pi/180: s:=5:
Wx:=-300*sin(theta);
Tx:=T*cos(phi);
WorkW:=Wx*s; evalf(%);
WorkT:=Tx*s; evalf(%);
DeltaKE:=WorkW+WorkT; evalf(%);
