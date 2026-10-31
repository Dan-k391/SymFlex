> restart: with(VectorCalculus): BasisFormat(false):
R:=q->Matrix([[cos(q),-sin(q)],[sin(q),cos(q)]]): R90:=R(Pi/2):
theta:=1200*2*Pi/60*t: rPC:=12/100: rOP:=5/100:
phi:=arcsin(rOP/rPC*sin(theta)):
omegaOP:=-diff(theta,t): omegaPC:=diff(phi,t): T:=2*Pi/abs(omegaOP):
rP:=rOP*<sin(theta),cos(theta)>; rPCvec:=rPC*<-sin(phi),+cos(phi)>;
rC:=rP+rPCvec; vP:=omegaOP*R90.rP; vPCvec:=omegaPC*R90.rPCvec; vC:=vP+vPCvec;
plot([rP[2], rC[2], rPCvec[2]], t=0..T, legend=['rPy','rCy', 'rPCy']);
plot([vP[2], vC[2], vPCvec[2]], t=0..T, legend=['vPy','vCy', 'vPCy']);
