# SOURCE: notes4_rigidbody block 06 (page 16) - example 16.13 solution 1 without IC
# NOTE: Matrix/Vector angle-bracket constructors and &x cross product (LinearAlgebra); vC[1] ~ -5.138e-13 (roundoff) as in document
restart: with(LinearAlgebra):
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
