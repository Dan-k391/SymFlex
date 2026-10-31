> restart: m:=1.9: k:=300: b:=2: omega0:=sqrt(k/m);
F:=3*cos(omega*t): zeta:=b/(2*sqrt(m*k)); Q:=1/(2*zeta); wr:=omega/omega0:
A0:=3/k; A:=A0*Q/sqrt(Q^2*(1-wr^2)^2+wr^2); phi:=arctan(wr, (1-wr^2)*Q);
plot(A, omega=.1*omega0..2*omega0);
plot(phi, omega=.1*omega0..2*omega0);
