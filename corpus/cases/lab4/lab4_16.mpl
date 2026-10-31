# SOURCE: lab4 block 16 (para 434) - Crank-slider: derivative after vector positions
restart: with(VectorCalculus): BasisFormat(false):
R:=q->Matrix([[cos(q),-sin(q)],[sin(q),cos(q)]]):
R90:=R(Pi/2):
theta:=1200*2*Pi/60*t: rPC:=12/100: rOP:=5/100:
phi:=arcsin(rOP/rPC*sin(theta)):
omegaOP:=-diff(theta,t): omegaPC:=diff(phi,t):
rP:=rOP*<sin(theta),cos(theta)>; rC:=rP+rPC*<-sin(phi),+cos(phi)>;
vP:=diff(rP,t); vC:=diff(rC,t);
T:=2*Pi/abs(omegaOP):
plot([rP[1], rP[2], rC[2]], t=0..T, legend=['rPx','rPy','rCy']);
plot([vP[1], vP[2], vC[2]], t=0..T, legend=['vPx','vPy','vC']);
