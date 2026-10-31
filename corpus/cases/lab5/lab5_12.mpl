# SOURCE: lab5 block 12 (para 297) - check aC
# DEPENDS: lab5_11
restart: r:=.25: L:=1: omega:=2*Pi: theta:=omega*t: phi:=arcsin(r/L*sin(theta)):
omegaBC:=diff(-phi,t): alphaBC:=diff(omegaBC,t):
alpha:=diff(omega,t):
xC:=r*cos(theta)+L*cos(phi): vCx:=diff(xC,t): aCx:=diff(vCx,t):
xD:=r*cos(theta)+L/2*cos(phi): vDx:=diff(xD,t): aDx:=diff(vDx,t):
aCcheck:=-omega^2*r*cos(theta)+alphaBC*L*sin(phi)-omegaBC^2*L*cos(phi); plot([aCcheck, aCx],t=0..1);
