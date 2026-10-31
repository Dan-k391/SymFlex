# SOURCE: lab5 block 08 (para 204) - slider-crank forces, plot MO
restart: with(VectorCalculus): BasisFormat(false):
R90:=Matrix([[0, -1], [1, 0]]): LPC:=12/100: LOP:=5/100:
theta:=1200*2*Pi/60*t: phi:=arcsin(LOP/LPC*sin(theta)):
rOP:=LOP*<sin(theta), cos(theta)>:
rPC:=LPC*<-sin(phi), cos(phi)>:
omegaOP:=-diff(theta,t):  omegaPC:=diff(phi,t):
alphaOP:=diff(omegaOP,t): alphaPC:=diff(omegaPC,t):
vOP:=omegaOP*R90.rOP: vPC:=omegaPC*R90.rPC:
#aOP:=diff(vOP,t): aPC:=diff(vPC,t):
aOP:=alphaOP*R90.rOP-omegaOP^2*rOP: aPC:=alphaPC*R90.rPC-omegaPC^2*rPC:
aP:=aOP: aC:=aP+aPC:    T:=2*Pi/abs(omegaOP):
#plot([aP[2], aC[2], aPC[2]], t=0..T, legend=['aPy', 'aCy', 'aPCy']);
mC:=5/10: mPC:=8/10: LPG:=4/100: kG_PC:=3/100: mOP:=6/10: kG_OP:=3/100:
FO:=<FOx, FOy>: FP:=<FPx, FPy>: FC:=<FCx, FCy>: Fcom:=<Fcomx,0>:
aO:=<0,0>: aG:=aP+aPC*(LPG/LPC): #rel accel of G, midway from P to C
rPG:=rPC*(LPG/LPC): rCP:=-rPC: rCG:=rCP+rPG:
IOP_O:=mOP*kG_OP^2:  IPC_C:=mPC*kG_PC^2+mPC*(LPC-LPG)^2:
VectorEqns:=[FO-FP - (mOP*aO), #Fnet on OP
MO+(R90.rOP).(-FP) - (IOP_O*alphaOP), #sum of torque on OP @ O
FP+FC -(mPC*aG), #Fnet on PC
(R90.rCP).FP -( (R90.rCG).(mPC*aC)+IPC_C*alphaPC), #Torque on PC @ C
Fcom-FC -(mC*aC)]:
ScalarEqns:=[VectorEqns[2], VectorEqns[4], VectorEqns[3][2], VectorEqns[5][2]]:
solve(ScalarEqns, [MO, FPx, FPy, FCy]): assign(%):
plot(MO, t=0..T, labels=['t', 'M__O']);
