> restart: vret:=t^3*(t+27): m:=500: g:=9.81:
#upwards velocity is:
v:=vret/4; #from work above
#upwards displacement from starting position is:
y:=int(v, t=0..t);
plot(y, t=0..1);
