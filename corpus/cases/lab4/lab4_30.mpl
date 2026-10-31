# SOURCE: lab4 block 30 (para 663) - L26 accelerations via 2d vector relations
restart: with(VectorCalculus): BasisFormat(false):
R90:=Matrix([[0, -1], [1, 0]]): rPC:=12/100: rOP:=5/100:
theta:=1200*2*Pi/60*t: phi:=arcsin(rOP/rPC*sin(theta)):
rOPvec:=rOP*<sin(theta), cos(theta)>:
rPCvec:=rPC*<-sin(phi), cos(phi)>:
omegaOP:=-diff(theta,t): omegaPC:=diff(phi,t):
alphaOP:=diff(omegaOP,t); alphaPC:=diff(omegaPC,t);
vOP:=omegaOP*R90.rOPvec: vPC:=omegaPC*R90.rPCvec:
aOP:=alphaOP*R90.rOPvec-omegaOP^2*rOPvec;
aPC:=alphaPC*R90.rPCvec-omegaPC^2*rPCvec;
aP:=aOP: aC:=aP+aPC:    T:=2*Pi/abs(omegaOP):
plot([aP[2], aC[2], aPC[2]], t=0..T, legend=['aPy', 'aCy', 'aPCy']);
