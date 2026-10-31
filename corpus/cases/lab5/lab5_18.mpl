# SOURCE: lab5 block 18 (para 446) - solution writeup shown in class
restart: with(VectorCalculus): BasisFormat(false):
thetadot:=1200*2*Pi/60: mC:=.5: mPC:=.8: LPG:=.04:
LPC:=.12: mOP:=.6: kG:=.03: LOP:=.05:
theta:=thetadot*t: phi:=arcsin(LOP*sin(theta)/LPC):
omegaOP:=-thetadot: omegaPC:=diff(phi,t):
rP:=LOP*<sin(theta), cos(theta)>:
rPC:=LPC*<-sin(phi), cos(phi)>: rPG:=rPC*LPG/LPC:
rC:=rP+rPC: vC:=diff(rC,t):
IOP:=mOP*kG^2: IPC:=mPC*kG^2: rG:=rP+rPG: vG:=diff(rG,t): Tcycle:=2*Pi/thetadot:
T:=.5*(IOP*omegaOP^2 + mPC*vG.vG + IPC*omegaPC^2 + mC*vC.vC):
MO:=diff(T,t)/omegaOP: plot(MO, t=0..Tcycle);
