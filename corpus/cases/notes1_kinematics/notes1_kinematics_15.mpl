# SOURCE: notes1_kinematics block 15 (page 43) - Block in a halfpipe: apply the initial condition w(Pi/2)=0
# NOTE: doc output: C := -3*exp(-mu_k*Pi)*gr*mu_k/(4*mu_k^2+1); w := -gr*(2*cos(theta)*mu_k^2+3*exp(-mu_k*(Pi-2*theta))*mu_k-3*mu_k*sin(theta)-cos(theta))/(4*mu_k^2+1)
restart:
int1:=simplify(int(exp(-2*mu_k*theta)*gr*(mu_k*cos(theta)-sin(theta)), theta)):
C:=simplify(solve(0=subs(theta=Pi/2, int1)+C, C));
w:=simplify((int1+C)/exp(-2*mu_k*theta));
