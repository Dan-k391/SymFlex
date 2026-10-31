# SOURCE: notes1_kinematics block 16 (page 44) - Plotting w/gr for theta in (-Pi/2, Pi/2)
# DEPENDS: notes1_kinematics_15
# NOTE: doc plot: hump with roots near theta=-0.53 and theta=Pi/2, max ~0.5 near theta=0.6
restart:
int1:=simplify(int(exp(-2*mu_k*theta)*gr*(mu_k*cos(theta)-sin(theta)), theta)):
C:=simplify(solve(0=subs(theta=Pi/2, int1)+C, C));
w:=simplify((int1+C)/exp(-2*mu_k*theta));
plot(subs(mu_k=0.3, w/gr), theta=-Pi/2..Pi/2);
