> restart: with(VectorCalculus): BasisFormat(false):
R90:=Matrix([[0, -1], [1, 0]]): mAB:=5: r:=25/100: kG:=15/100:
mBC:=2: L:=1: mC:=8:
theta:=2*Pi*t: omegaAB:=diff(theta,t): alphaAB:=diff(omegaAB,t):
phi:=arcsin(r/L*sin(theta)): omegaBC:=-diff(phi,t): alphaBC:=diff(omegaBC,t):
rAB:=r*<cos(theta),sin(theta)>: rBC:=L*<cos(phi),-sin(phi)>:
rB:=rAB: rC:=rB+rBC: rG:=rB+rBC/2: aG:=diff(rG,t,t): aB:=diff(rB,t,t):
aC:=diff(rC, t,t):
FB:=<FBx,FBy>: FC:=<FCx,FCy>:
VecEqns:=[MA+(R90.rAB).FB - (mAB*kG^2)*alphaAB,
-FB+FC - mBC*aG,
(R90.rBC).FC - ((R90.rBC/2).(mBC*aB)+(mBC^2*L/12)*alphaBC),
-FCx-mC*aC[1]]:
ScalarEqns:=[VecEqns[1], VecEqns[2][1], VecEqns[2][2], VecEqns[3], VecEqns[4]]:
solve(ScalarEqns, [MA, FBx, FBy, FCx, FCy]): assign(%): plot(MA, t=0..1);
