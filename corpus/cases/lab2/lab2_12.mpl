# SOURCE: lab2 block 12 (para 282) - L13 modification: 1D rocket with constant g, symbolic piecewise integration
restart:
mi:=500: mfi:=mi*.9: md:=mi-mfi: g:=9.81:
q:=5: ve:=1200: tfuel:=mfi/q;
mfuel:=piecewise(t<tfuel,mfi-q*t):
m:=md+mfuel:
Ft:=piecewise(t<tfuel, q*ve, t>tfuel, 0):
Fg:=-m*g:
a:=(Ft+Fg)/m:
v:=int(a, t=0..t):
h:=int(v, t=0..t):
plot(h, t=0..300);
maximize(h, t=200..300, location=true);
