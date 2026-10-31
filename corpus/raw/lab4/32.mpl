> restart: with(VectorCalculus): BasisFormat(false):
R90:=Matrix([[0, -1], [1, 0]]): rPC:=12/100: rOP:=5/100:
theta:=1200*2*Pi/60*t: phi:=arcsin(rOP/rPC*sin(theta)):
rOPvec:=rOP*<sin(theta), cos(theta)>:
rPCvec:=rPC*<-sin(phi), cos(phi)>:
omegaOP:=-diff(theta,t):
vOP:=diff(rOPvec,t): vPC:=diff(rPCvec,t):
aOP:=diff(vOP,t);
aPC:=diff(vPC,t);
aP:=aOP: aC:=aP+aPC:    T:=2*Pi/abs(omegaOP):
rD:=rOPvec+rPCvec/2: aD:=diff(rD,t,t);
simplify(subs(t=0, aD)); evalf(%);
#plot([aP[2], aC[2], aPC[2]], t=0..T, legend=['aPy', 'aCy', 'aPCy']);
