# SOURCE: lab4 block 22 (para 524) - L25 P25.1 d) angular velocities & cross product
# DEPENDS: lab4_19, lab4_20, lab4_21
restart: r:=.25: L:=1: theta:=2*Pi*t:
phi:=arcsin(r/L*sin(theta));
plot([theta, phi], t=0..1);
xB:=r*cos(theta); yB:=r*sin(theta); xC:=r*cos(theta)+L*cos(phi);
plot([[xB,yB,t=0..1],[xC,0,t=0..1]]);
vBx:=diff(xB,t); vBy:=diff(yB,t); vCx:=diff(xC,t);
omegaAB:=diff(theta,t);
omegaBC:=-diff(phi,t);
#using cross product:
with(VectorCalculus): BasisFormat(false):
rAB:=r*<cos(theta),sin(theta),0>: rBC:=L*<cos(phi),-sin(phi),0>:
vB:=<0,0,omegaAB> &x rAB; vC:=vB+ <0,0,omegaBC> &x rBC;
