> restart: with(LinearAlgebra):
deg2rad:=3.14159/180:
theta:=13.6*deg2rad:
phi:=45*deg2rad:
rAB:=.25: #ft
rBC:=.75:
rABVec:=rAB*<-sin(phi), cos(phi),0>;
rBCVec:=rBC*<sin(theta), cos(theta),0>;
omegaAB:=10: omegaABVec:=<0,0,-omegaAB>;
vB:=omegaABVec &x rABVec;
omegaBC:=rAB/rBC*(cos(phi)/cos(theta))*omegaAB;
omegaBCVec:=<0,0,omegaBC>:
vC:=vB+omegaBCVec &x rBCVec;
