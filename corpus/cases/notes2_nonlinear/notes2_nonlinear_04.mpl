# SOURCE: notes2_nonlinear block 04 (page 10) - Misaligned shuttle thruster: angle vs time using assume
# NOTE: assume makes t display as t~ in alpha/omega/theta; omega/theta come out in closed form (arccoth, ln). Doc shows only the plot (theta about 500 rad at t=60)
restart;
FThrust:=13.8e6:
mshuttle:=24000: mtank:=760000: mbooster:=400000-3500*t:
mtotal:=mshuttle+mtank+mbooster:
xbooster:=6: L:=47: tfinal:=60:
xbar:=xbooster*mbooster/mtotal:
tau:=(xbooster-xbar)*(FThrust):
Izz:=(mshuttle+mtank)*(1/12*L^2+xbar^2)+mbooster*(1/12*L^2+(xbooster-xbar)^2);
assume(0<t, t<tfinal); #New!
alpha:=tau/Izz;
omega:=simplify(int(alpha, t=0..t));
theta:=simplify(int(omega, t=0..t));
plot([alpha*100, omega*10, theta], t=0..60);
