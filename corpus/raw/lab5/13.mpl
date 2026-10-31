> #input masses & determine MoIs
mAB:=5: mBC:=2: mC:=8: kG:=.15:
IAB:=mAB*kG^2; IBCatC:=mBC*L^2/3;
#Apply N2 eqns to find forces:
FCx:=-mC*aCx:
FBx:=FCx-mBC*aDx:
FBy:=(IBCatC*alphaBC-L/2*sin(phi)*mBC*aCx-L*sin(phi)*FBx)/(L*cos(phi)):
MA:=IAB*alpha+r*sin(theta)*FBx-r*cos(theta)*FBy:
plot(MA,t=0..1);
