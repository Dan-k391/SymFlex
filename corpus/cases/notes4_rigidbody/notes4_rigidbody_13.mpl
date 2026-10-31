# SOURCE: notes4_rigidbody block 13 (page 35) - example 17.9 flywheel corrected
# NOTE: output matches document (both solves give Ot = 29.50819672, alpha = 26.39344262)
restart:
k:=.6: w:=50: g:=32.2: rG:=.5:
m:=w/g; IG:=m*k^2;
omega:=0; #starting from rest
solve([
On = m*omega^2*rG,
w-Ot = m*rG*alpha,
rG*Ot = IG*alpha]); #torque about G
#alternative soln:
solve([
On = m*omega^2*rG,
w-Ot = m*rG*alpha,
rG*w = (IG+m*rG^2)*alpha]); #using IP
