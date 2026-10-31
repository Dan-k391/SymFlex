# SOURCE: lab3 text line 783 (L20 "dsolve method", not auto-extracted) - L20 frequency response via dsolve
# NOTE: this block was not in corpus/raw (different font in the doc); transcribed from corpus/text/lab3.txt lines 783-790
restart: m:=1.9: k:=300: b:=2: omega0:=sqrt(k/m);
F:=3*cos(omega*t):
dsolve({m*diff(s(t),t,t)+b*diff(s(t),t)+k*s(t)=F, s(0)=0, D(s)(0)=0}): s:=evalf(rhs(%));
#Extract Coefficients of Steady-State term:
a1:=coeff(s, sin(omega*t)); a2:=coeff(s, cos(omega*t));
A:=simplify(sqrt(a1^2+a2^2)); phi:=arctan(a1, a2);
plot(A, omega=.1*omega0..2*omega0);
plot(phi, omega=.1*omega0..2*omega0);
