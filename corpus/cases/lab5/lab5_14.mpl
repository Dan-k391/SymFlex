# SOURCE: lab5 block 14 (para 320) - crank: putting it all together
# NOTE: same as 11+13 but FBy uses +L/2*sin(phi)*mBC*aCx (author change), kept
restart: r:=.25: L:=1: omega:=2*Pi: theta:=omega*t: phi:=arcsin(r/L*sin(theta)):
omegaBC:=diff(-phi,t): alphaBC:=diff(omegaBC,t):
alpha:=diff(omega,t):
xC:=r*cos(theta)+L*cos(phi): vCx:=diff(xC,t): aCx:=diff(vCx,t):
xD:=r*cos(theta)+L/2*cos(phi): vDx:=diff(xD,t): aDx:=diff(vDx,t):
#input masses & determine MoIs
mAB:=5: mBC:=2: mC:=8: kG:=.15:
IAB:=mAB*kG^2; IBCatC:=mBC*L^2/3;
#Apply N2 eqns to find forces:
FCx:=-mC*aCx:
FBx:=FCx-mBC*aDx:
FBy:=(IBCatC*alphaBC+L/2*sin(phi)*mBC*aCx-L*sin(phi)*FBx)/(L*cos(phi)):
MA:=IAB*alpha+r*sin(theta)*FBx-r*cos(theta)*FBy:
plot(MA,t=0..1);
