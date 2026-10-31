> restart: V0:=1: C:=1e-9: L:=100e-3: R:=100: f:=1e3: omega:=2*Pi*f;
omega0:=1/sqrt(L*C); omegar:=omega/omega0; Q:=sqrt(L/C)/R; A0:=V0*C;
H:=Q/sqrt(Q^2*(1-omegar^2)^2+omegar^2); phi:=arctan(omegar, (1-omegar^2)*Q);
qss:=H*A0*cos(omega*t-phi);
