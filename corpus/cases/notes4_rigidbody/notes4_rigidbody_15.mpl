# SOURCE: notes4_rigidbody block 15 (page 37) - eg 17.11 drum
# NOTE: output matches document: IG := 3.7500 (Maple keeps trailing zeros from float product), T = 105.8633094, alpha = 11.29208633
restart:
k:=.25: mD:=60: IG:=mD*k^2;
mB:=20: g:=9.81: r:=.4:
a:=alpha*r:
solve([
mB*g-T = mB*a,
T*r = IG*alpha]);
solve([
mB*g*r = IG*alpha+mB*a*r]);
