# SOURCE: lab5 block 24 (para 609) - L31 mod: CCW moment 5 N-m
restart: IA:=.4: m:=6: R:=.2: omega:=vB/R:
HA:=IA*omega: HB:=R*m*vB: #both into page
Htotal:=HA+HB; H0:=subs(vB=2, Htotal);
torque:=m*9.81*R - 5; #torque into page about A
AngImp:=torque*3; #angular impulse into page
H3:=H0+AngImp: v3:=solve(H3=Htotal);
