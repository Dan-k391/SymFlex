> restart:
k:=.25: mD:=60: IG:=mD*k^2;
mB:=20: g:=9.81: r:=.4:
a:=alpha*r:
solve([
mB*g-T = mB*a,
T*r = IG*alpha]);
solve([
mB*g*r = IG*alpha+mB*a*r]);
