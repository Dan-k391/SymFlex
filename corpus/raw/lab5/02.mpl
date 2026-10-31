> v:=360/3.6; #km/hr to m/s
r:=1e3:
Omega:=v/r;
acent:=Omega^2*r;
aCorr:=2*Omega*5;
acentMod:=(v+5)^2/r;
