# SOURCE: notes4_rigidbody block 16 (page 38) - eg 17.12 2nd-order DE in time
# NOTE: dsolve returns two implicit solutions theta(t) = RootOf(-Int(...,_a=0.._Z)+t) as in document ("tough form for Maple")
restart:
IG:=1/12*m*L^2:
at:=L/2*alpha;
#assume(L, positive); assume(g, positive); assume(t, positive);
#doesn't help here
omega:=diff(theta(t),t);
alpha:=diff(omega,t);
#dsolve([at=g, theta(0)=0, D[1](theta)(0)=0]);  #syntax test
an:=omega^2*r;
DE:=L/2*m*g*cos(theta(t)) = IG*alpha + m*L/2*at;
#L/2*m*g = (1/3*m*L^2)*alpha;  #same eqn using IO instead of IG
dsolve([DE, theta(0)=0, D[1](theta)(0)=0]);
