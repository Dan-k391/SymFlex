# SOURCE: lab5 block 17 (para 424) - slider-crank KE and moment from work
restart: with(VectorCalculus): BasisFormat(false):
R90:=Matrix([[0, -1], [1, 0]]): LPC:=12/100: LOP:=5/100: LPG:=4/100:
theta:=1200*2*Pi/60*t: phi:=arcsin(LOP/LPC*sin(theta)):
rOP:=LOP*<sin(theta), cos(theta)>:  rPC:=LPC*<-sin(phi), cos(phi)>:
omegaOP:=-diff(theta,t):  omegaPC:=diff(phi,t):
vOP:=omegaOP*R90.rOP: vPC:=omegaPC*R90.rPC:
vP:=vOP: vG:=vP+vPC*LPG/LPC: vC:=vP+vPC:
mC:=5/10: mPC:=8/10: LPG:=4/100: kG_PC:=3/100: mOP:=6/10: kG_OP:=3/100:
IOP:=mOP*kG_OP^2: IPC:=mPC*kG_PC^2:
TOP:=1/2*IOP*omegaOP^2: TPC:=1/2*(mPC*vG.vG+IPC*omegaPC^2):
TC:=1/2*mC*vC.vC: T:=TOP+TPC+TC: tcycle:=2*Pi/abs(omegaOP):
plot([TOP, TC, TPC], t=0..tcycle);
plot([TOP, TC, 1/2*(mPC*vG.vG),1/2*IPC*omegaPC^2], t=0..tcycle);
Tstart:=subs(t=0, T): U:=T-Tstart: #work done since start of motion
M:=diff(U,t)/omegaOP: plot(M, t=0..tcycle);
