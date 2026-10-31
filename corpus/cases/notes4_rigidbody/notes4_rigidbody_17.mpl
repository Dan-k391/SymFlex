# SOURCE: notes4_rigidbody block 17 (page 39) - eg 17.12 first order in theta DE
# NOTE: dsolve on omega(theta) with D[1](omega)(theta); assign(%[1]) of first solution; output matches document (An := 5/2*m*g*sin(theta), At := -1/4*m*g*cos(theta))
restart:
IG:=1/12*m*L^2:
at:=L/2*alpha;
an:=(omega(theta))^2*L/2;
DE1:=L/2*m*g*cos(theta) = IG*alpha + m*L/2*at;
alpha:=solve(DE1, alpha);
DE2:= alpha = omega(theta)*D[1](omega)(theta);
dsolve([DE2, omega(0)=0]);
assign(%[1]);
An := m*g*sin(theta)+m*an;
At :=-m*g*cos(theta)+m*at;
