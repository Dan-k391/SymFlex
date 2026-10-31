# SOURCE: notes1_kinematics block 17 (page 44) - fsolve for where the block stops in (-Pi/2, 0)
# DEPENDS: notes1_kinematics_15
# NOTE: doc output: theta1 := -0.5274507694
restart:
int1:=simplify(int(exp(-2*mu_k*theta)*gr*(mu_k*cos(theta)-sin(theta)), theta)):
C:=simplify(solve(0=subs(theta=Pi/2, int1)+C, C));
w:=simplify((int1+C)/exp(-2*mu_k*theta));
theta1:=fsolve(subs(mu_k=0.3, w/gr)=0, theta=-Pi/2..0);
