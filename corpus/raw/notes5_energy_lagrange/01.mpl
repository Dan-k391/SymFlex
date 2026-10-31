> restart:
M:=5: k:=10: R:=.2: m:=30: IG:=1/2*m*R^2;
omegaF:=2:
U:=M*theta-.5*k*(R*theta)^2;
solve(U=.5*IG*omegaF^2);
