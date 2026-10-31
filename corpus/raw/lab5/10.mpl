> restart: with(VectorCalculus): BasisFormat(false):
LPC:=12/100: LOP:=5/100: theta:=1200*2*Pi/60*t: phi:=arcsin(LOP/LPC*sin(theta)):
rOP:=LOP*<sin(theta), cos(theta), 0>: rPC:=LPC*<-sin(phi), cos(phi),0>:
omegaOP:=<0,0,-diff(theta,t)>:  omegaPC:=<0,0,diff(phi,t)>:
alphaOP:=diff(omegaOP,t): alphaPC:=diff(omegaPC,t):
vOP:=omegaOP &x rOP: vPC:=omegaPC &x rPC:
aOP:=alphaOP &x rOP - (omegaOP.omegaOP)*rOP:
aPC:=alphaPC &x rPC - (omegaPC.omegaPC)*rPC:
aP:=aOP: aC:=aP+aPC:    T:=2*Pi/abs(omegaOP[3]):
#plot([aP[2], aC[2], aPC[2]], t=0..T, legend=['aPy', 'aCy', 'aPCy']);
mC:=5/10: mPC:=8/10: LPG:=4/100: kG_PC:=3/100: mOP:=6/10: kG_OP:=3/100:
FO:=<FOx, FOy,0>: FP:=<FPx, FPy,0>: FC:=<FCx, FCy,0>: Fcom:=<Fcomx,0,0>:
aO:=<0,0,0>: aG:=aP+aPC*(LPG/LPC): #rel accel of G, midway from P to C
rPG:=rPC*(LPG/LPC): rCP:=-rPC: rCG:=rCP+rPG: MO:=<0,0,M>:
IOP_O:=mOP*kG_OP^2:  IPC_C:=mPC*kG_PC^2+mPC*(LPC-LPG)^2:
VectorEqns:=[FO-FP - (mOP*aO), #Fnet on OP
MO + rOP &x (-FP) - (IOP_O*alphaOP), #sum of torque on OP @ O
FP+FC -(mPC*aG), #Fnet on PC
rCP &x FP - ( rCG &x (mPC*aC) + IPC_C*alphaPC), #Torque on PC @ C
Fcom-FC -(mC*aC)]:
[seq(seq(VectorEqns[i][j], i=1..5), j=1..3)]: #separate each component into an eqn
solve(%, [M, FOx, FOy, FPx, FPy, FCx, FCy, Fcomx]); assign(%): #solve 15 eqns (7 trivial)
#ScalarEqns:=[VectorEqns[2][3], VectorEqns[4][3], VectorEqns[3][2], VectorEqns[5][2]]:
#solve(ScalarEqns, [M, FPx, FPy, FCy]): assign(%):
plot(M, t=0..T, labels=['t', 'M__O']);
