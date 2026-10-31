> restart:
m:=12: L:=.6: k:=3e3*4: b:=200: F0:=30: omega:=6:
omega0:=sqrt(k/m); Q:=omega0/(b/m); Q2:=sqrt(m*k)/b;
wr:=omega/omega0;
q0:=6/(m*L)*F0/omega0^2; #low freq amplitude
H:=Q/sqrt(Q^2*(1-wr^2)^2+wr^2);
qss:=q0*H;
