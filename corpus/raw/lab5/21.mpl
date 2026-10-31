> M:=diff(U,t)/omegaAB: plot(M, t=0..1);

> restart: with(VectorCalculus): BasisFormat(false):
mAB:=5: r:=25/100: kG:=15/100:
mBC:=2: L:=1: mC:=8:
theta:=2*Pi*t: omegaAB:=diff(theta,t):
phi:=arcsin(r/L*sin(theta)): omegaBC:=-diff(phi,t):
rAB:=r*<cos(theta),sin(theta)>: rBC:=L*<cos(phi),-sin(phi)>:
rB:=rAB: rC:=rB+rBC: rG:=rB+rBC/2: vG:=diff(rG,t): vB:=diff(rB,t):
vC:=diff(rC, t):
IA:=mAB*kG^2: IBC:=mBC*L^2/12:
TAB:=1/2*IA*omegaAB^2:
TBC:=1/2*(IBC*omegaBC^2+mBC*vG.vG):
TC:=1/2*mC*vC.vC:
Ttotal:=TAB+TBC+TC:  Tstart:=subs(t=0, Ttotal):  U:=Ttotal-Tstart:
plot([TAB, TBC, TC,U], t=0..1, labels=['KE', 't'], legend=['disk', 'bar', 'piston', 'totalwork']);
M:=diff(U,t)/omegaAB: plot(M, t=0..1);
