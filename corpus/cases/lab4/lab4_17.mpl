# SOURCE: lab4 block 17 (para 454) - Crank-slider: rotation matrices for cross products
restart: with(VectorCalculus): BasisFormat(false):
R:=q->Matrix([[cos(q),-sin(q)],[sin(q),cos(q)]]):
R90:=R(Pi/2):
theta:=1200*2*Pi/60*t: rPC:=12/100: rOP:=5/100:
phi:=arcsin(rOP/rPC*sin(theta)):
omegaOP:=-diff(theta,t): omegaPC:=diff(phi,t):
rP:=rOP*<sin(theta),cos(theta)>;
rPCvec:=rPC*<-sin(phi),+cos(phi)>;
rC:=rP+rPCvec;
vP:=omegaOP*R90.rP; vC:=vP+omegaPC*R90.rPCvec;
T:=2*Pi/abs(omegaOP):
plot([rP[1], rP[2], rC[2]], t=0..T, legend=['rPx','rPy','rCy']);
plot([vP[1], vP[2], vC[2]], t=0..T, legend=['vPx','vPy','vC']);
