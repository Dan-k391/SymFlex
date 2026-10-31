> restart: rho:=10: CD:=.8: A:=2: with(LinearAlgebra):
vvec:=<3,-2>: vwvec:=<2,0>:
vrelvec:=vvec-vwvec;
vrel:=sqrt(vrelvec.vrelvec); vrelhat:=vrelvec/vrel;
FD:=.5*rho*CD*A*vrel^2*(-vrelhat); evalf(%);
