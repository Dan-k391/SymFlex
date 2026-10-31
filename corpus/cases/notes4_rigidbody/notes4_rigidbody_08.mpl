# SOURCE: notes4_rigidbody block 08 (page 20) - example 16.18 solution method 1
# NOTE: output matches document; aCVec[1] ~ -2.1337e-9 roundoff
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
omegaBC:=rAB/rBC*(cos(phi)/cos(theta))*omegaAB;
omegaBCVec:=<0,0,omegaBC>:
#vC:=vB+omegaBCVec &x rBCVec:
alphaAB:=20:
aBVec:=<0,0,-alphaAB> &x rABVec - omegaAB^2*rABVec;
alphaBC:=solve(
cos(phi)/rBC*(-alphaAB)-sin(phi)/rBC*(omegaAB)^2
=cos(theta)/rAB*(-alphaBC)-sin(theta)/rAB*(omegaBC)^2);
aCVec:=aBVec + <0,0,alphaBC> &x rBCVec - omegaBC^2*rBCVec;
