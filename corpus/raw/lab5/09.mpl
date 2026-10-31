> restart: with(VectorCalculus): BasisFormat(false):
LPC:=12/100: LOP:=5/100: theta:=1200*2*Pi/60*t: phi:=arcsin(LOP/LPC*sin(theta)):
rOP:=LOP*<sin(theta), cos(theta), 0>: rPC:=LPC*<-sin(phi), cos(phi),0>:
omegaOP:=<0,0,-diff(theta,t)>:  omegaPC:=<0,0,diff(phi,t)>:
alphaOP:=diff(omegaOP,t): alphaPC:=diff(omegaPC,t):
vOP:=omegaOP &x rOP: vPC:=omegaPC &x rPC:
aOP:=alphaOP &x rOP - (omegaOP.omegaOP)*rOP:
aPC:=alphaPC &x rPC - (omegaPC.omegaPC)*rPC:
aP:=aOP: aC:=aP+aPC:    T:=2*Pi/abs(omegaOP[3]):
plot([aP[2], aC[2], aPC[2]], t=0..T, legend=['aPy', 'aCy', 'aPCy']);
