> restart: with(VectorCalculus): BasisFormat(false):
R:=q->Matrix([[cos(q),-sin(q)],[sin(q),cos(q)]]):
R90:=R(Pi/2):
theta:=1200*2*Pi/60*t: rPC:=12/100: rOP:=5/100:
phi:=arcsin(rOP/rPC*sin(theta)):
omegaOP:=-diff(theta,t): omegaPC:=diff(phi,t):
yP:=rOP*cos(theta); xP:=rOP*sin(theta); yC:=yP+rPC*cos(phi); xC:=xP-rPC*sin(phi);
#xC should just be 0, so no needt for them to find it, this is just a check.
T:=2*Pi/abs(omegaOP):
plot([xP, yP, yC], t=0..T, legend=['xP','yP','yC']);
vPx:=diff(xP,t); vPy:=diff(yP,t); vC:=diff(yC,t);
plot([vPx, vPy, vC], t=0..T, legend=['vPx','vPy','vC']);
