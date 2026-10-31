# SOURCE: notes4_rigidbody block 09 (page 21) - example 16.18 solution method 2
# NOTE: omegaBC/alphaBC are assigned after being used inside omegaBCVec/aCVec and vectors are recomputed; output matches document
restart: with(LinearAlgebra):
deg2rad:=3.14159/180:
theta:=13.6*deg2rad:
phi:=45*deg2rad:
rAB:=.25: #ft
rBC:=.75:
rABVec:=rAB*<-sin(phi), cos(phi),0>:
rBCVec:=rBC*<sin(theta), cos(theta),0>:
omegaAB:=10: omegaABVec:=<0,0,-omegaAB>:
vB:=omegaABVec &x rABVec:
#omegaBC:=rAB/rBC*(cos(phi)/cos(theta))*omegaAB;
omegaBCVec:=<0,0,omegaBC>:
vC:=vB+omegaBCVec &x rBCVec:
omegaBC:=solve(vC[1]=0);
vC:=vB+omegaBCVec &x rBCVec;
alphaAB:=20:
aBVec:=<0,0,-alphaAB> &x rABVec - omegaAB^2*rABVec;
aCVec:=aBVec + <0,0,alphaBC> &x rBCVec - omegaBC^2*rBCVec:
alphaBC:=solve(aCVec[1]=0);
aCVec:=aBVec + <0,0,alphaBC> &x rBCVec - omegaBC^2*rBCVec;
