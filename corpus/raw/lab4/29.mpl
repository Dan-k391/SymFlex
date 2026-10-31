> restart: r:=.25: L:=1: theta:=2*Pi*t:
phi:=arcsin(r/L*sin(theta));
omegaAB:=diff(theta,t);
omegaBC:=-diff(phi,t);
#using cross product:
with(VectorCalculus): BasisFormat(false):
rAB:=r*<cos(theta),sin(theta),0>: rBC:=L*<cos(phi),-sin(phi),0>:
vB:=<0,0,omegaAB> &x rAB:
vC:=vB+ <0,0,omegaBC> &x rBC;
vD:=vB+ <0,0,omegaBC> &x rBC/2;
