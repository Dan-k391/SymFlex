# SOURCE: lab5 block 05 (para 127) - vector accel of struck bar
restart: F:=<0,10,0>: m:=5: L:=2: with(VectorCalculus): BasisFormat(false):
aG:=F/m; IG:=m*L^2/12; rGQ:=<-L/2,0,0>: tauG:=rGQ &x F;
alpha:=tauG/IG;
rGP:=<L/2,0,0>: aGP:=alpha &x rGP;
aP:=aG+aGP;
