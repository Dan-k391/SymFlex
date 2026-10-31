# SOURCE: lab5 block 06 (para 161) - slider-crank kinematics plot
# NOTE: trailing "mC:=..." line is the first line of block 07, kept as in document
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
plot([aP[2], aC[2], aPC[2]], t=0..T, legend=['aPy', 'aCy', 'aPCy']);
mC:=5/10: mPC:=8/10: LPG:=4/100: kG_PC:=3/100: mOP:=6/10: kG_OP:=3/100:
