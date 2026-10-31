> restart: with(VectorCalculus): BasisFormat(false):
R:=q->Matrix([[cos(q),-sin(q)],[sin(q),cos(q)]]):
R90:=R(Pi/2):
theta:=1200*2*Pi/60*t: rPC:=12/100: rOP:=5/100:
phi:=arcsin(rOP/rPC*sin(theta)):
omegaOP:=-diff(theta,t): omegaPC:=diff(phi,t):
rP:=rOP*<sin(theta),cos(theta)>; rPCvec:=rPC*<-sin(phi),+cos(phi)>; rC:=rP+rPCvec;
vP:=omegaOP*R90.rP; vC:=vP+omegaPC*R90.rPCvec;
rD:=rP+rPCvec/2; vD:=vP+omegaPC*R90.rPCvec/2; vD0:=evalf(subs(t=0,vD));
