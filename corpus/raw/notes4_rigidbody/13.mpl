> restart:
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
