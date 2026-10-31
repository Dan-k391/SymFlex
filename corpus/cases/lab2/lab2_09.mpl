# SOURCE: lab2 block 09 (para 181) - L12 final velocities vs coefficient of restitution
restart: mA:=5: mB:=4: vA1:=8: vB1:=-4:
solve([
mA*vA1+mB*vB1=mA*vA2+mB*vB2,
e=(vB2-vA2)/(vA1-vB1)], [vA2, vB2]); assign(%);
plot([vA2, vB2], e=0..1);
