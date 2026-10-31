restart;
FThrust:=13.8e6:
mshuttle:=24000: mtank:=760000: mbooster:=400000-3500*t:
mtotal:=mshuttle+mtank+mbooster:
xbooster:=6: L:=47: tfinal:=60:
xbar:=xbooster*mbooster/mtotal:
tau:=(xbooster-xbar)*(FThrust):
Izz:=(mshuttle+mtank)*(1/12*L^2+xbar^2)+mbooster*(1/12*L^2+(xbooster-
xbar)^2);
alpha:=tau/Izz;
omega:=simplify(int(subs(t=t2, %), t2=0..t));
theta:=simplify(int(subs(t=t2, %), t2=0..t));
plot([alpha*100, omega*10, theta], t=0..60);
