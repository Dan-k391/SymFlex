# SOURCE: notes4_rigidbody block 14 (page 36) - example 17.10
# NOTE: output matches document (3 identical solutions On = 750., Ot = 19.05, alpha = -5.905)
restart:
omega:=5: m:=20: L:=3: IO:=1/3*m*L^2: M1:=60: IG:=1/12*m*L^2:
at:=alpha*L/2: W:=m*9.81:
an:=omega^2*L/2:
solve([
Ot-W = m*at,
On = m*an,
-M1-L/2*W = IO*alpha]); #torque @ O
solve([
Ot-W = m*at,
On = m*an,
-M1-L/2*W = IG*alpha+m*L/2*at]);
solve([
Ot-W = m*at,
On = m*an,
-Ot*L/2 - M1 = IG*alpha]); #torque @ G
