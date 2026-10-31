# SOURCE: lab1 block 10 (para 313) - fsolve for when T2 first passes 5 kN (elevator)
# DEPENDS: lab1_09
# NOTE: prepended block 09 and the un-extracted group 'T:=(m*diff(v,t)+m*g)/4; T2:=2*T; plot(T2, t=0..1);' from the doc (it defines T2)
restart: vret:=t^3*(t+27): m:=500: g:=9.81:
#upwards velocity is:
v:=vret/4; #from work above
#upwards displacement from starting position is:
y:=int(v, t=0..t);
plot(y, t=0..1);
T:=(m*diff(v,t)+m*g)/4;
T2:=2*T;
plot(T2, t=0..1);
fsolve(T2=5e3, t=0.6..1);
