# SOURCE: notes1_kinematics block 18 (page 44) - Part 3: check whether static friction holds the block
# DEPENDS: notes1_kinematics_15, notes1_kinematics_17
# NOTE: doc output: 0.6048650907 then 0.5033322068
restart:
int1:=simplify(int(exp(-2*mu_k*theta)*gr*(mu_k*cos(theta)-sin(theta)), theta)):
C:=simplify(solve(0=subs(theta=Pi/2, int1)+C, C));
w:=simplify((int1+C)/exp(-2*mu_k*theta));
theta1:=fsolve(subs(mu_k=0.3, w/gr)=0, theta=-Pi/2..0);
0.7*cos(theta1);
sin(-theta1);
