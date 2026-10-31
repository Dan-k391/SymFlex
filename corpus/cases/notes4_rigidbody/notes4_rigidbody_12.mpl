# SOURCE: notes4_rigidbody block 12 (page 35) - example 17.9 flywheel (incorrect torque eqn)
# NOTE: intentionally incorrect torque equation per the notes (Ot = 15.27777778 is "wrong"), not a Maple error; output matches document
restart:
k:=.6: w:=50: g:=32.2: rG:=.5:
m:=w/g; IG:=m*k^2;
omega:=0; #starting from rest
solve([
On = m*omega^2*rG,
w-Ot = m*rG*alpha,
rG*w = IG*alpha]);
