# SOURCE: lab5 block 23 (para 600) - L31 impulse momentum
restart: IA:=.4: mB:=6: g:=9.81: R:=.2:
vB0:=2: DvB:=mB*g*3*R/(IA/R+R*mB);
vB3:=vB0+DvB;
