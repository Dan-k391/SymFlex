# SOURCE: lab3 block 08 (para 219) - L16 mod 4b vector drag force moving fluid
restart: rho:=10: CD:=.8: A:=2: with(LinearAlgebra):
vvec:=<3,-2>: vwvec:=<2,0>:
vrelvec:=vvec-vwvec;
vrel:=sqrt(vrelvec.vrelvec); vrelhat:=vrelvec/vrel;
FD:=.5*rho*CD*A*vrel^2*(-vrelhat); evalf(%);
