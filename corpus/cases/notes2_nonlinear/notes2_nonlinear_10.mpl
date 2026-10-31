# SOURCE: notes2_nonlinear block 10 (page 11) - translational motion of the misaligned shuttle
# DEPENDS: notes2_nonlinear_05
# NOTE: prepends the subs(t=t2,%) version (block 05). Prepending the assume version (block 04) instead makes cmaple hang >500 s (slow). With block 05, Maple 2024 gives vx := 0. and rx := 0. (nested ints reusing t2); doc shows no output and says Maple cannot really solve this (too many nested numeric integrations)
restart;
FThrust:=13.8e6:
mshuttle:=24000: mtank:=760000: mbooster:=400000-3500*t:
mtotal:=mshuttle+mtank+mbooster:
xbooster:=6: L:=47: tfinal:=60:
xbar:=xbooster*mbooster/mtotal:
tau:=(xbooster-xbar)*(FThrust):
Izz:=(mshuttle+mtank)*(1/12*L^2+xbar^2)+mbooster*(1/12*L^2+(xbooster-xbar)^2);
alpha:=tau/Izz;
omega:=simplify(int(subs(t=t2, %), t2=0..t));
theta:=simplify(int(subs(t=t2, %), t2=0..t));
plot([alpha*100, omega*10, theta], t=0..60);
g:=9.81;
ax:=FThrust*(-sin(theta))/mtotal:
vx:=int(subs(t=t2, %), t2=0 ..t);
rx:=int(subs(t=t2, %), t2=0 ..t);
ay:=FThrust*(cos(theta))/mtotal:
vy:=int(subs(t=t2, %), t2=0 ..t)+433:
ry:=int(subs(t=t2, %), t2=0 ..t)+11617:
plot([ax, vx, rx],t=0..60);
