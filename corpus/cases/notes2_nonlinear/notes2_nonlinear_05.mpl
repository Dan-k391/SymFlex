# SOURCE: notes2_nonlinear block 05 (page 10) - Misaligned shuttle thruster: subs(t=t2, %) variant without assume
# NOTE: omega/theta stay as unevaluated (nested) int(..., t2=0..t). Maple 2024 prints "Warning, unable to determine if 5569600/15463-2688/2209*6951^(1/2) is between 0 and t2; try to use assumptions or use the AllSolutions option" (and the same with +) when plotting; doc block 06 shows older wording "...between 0 and t; try to use assumptions or set _EnvAllSolutions to true"
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
