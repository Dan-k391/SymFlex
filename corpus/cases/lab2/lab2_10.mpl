# SOURCE: lab2 block 10 (para 190) - L12 fraction of KE remaining vs e
# DEPENDS: lab2_09
# NOTE: block 10 continues the worksheet of block 09 (no restart); block 09 code prepended
restart: mA:=5: mB:=4: vA1:=8: vB1:=-4:
solve([
mA*vA1+mB*vB1=mA*vA2+mB*vB2,
e=(vB2-vA2)/(vA1-vB1)], [vA2, vB2]); assign(%);
plot([vA2, vB2], e=0..1);
KE2:=.5*mA*vA2^2+.5*mB*vB2^2:
KE1:=.5*mA*vA1^2+.5*mB*vB1^2:
plot(KE2/KE1, e=0..1);
