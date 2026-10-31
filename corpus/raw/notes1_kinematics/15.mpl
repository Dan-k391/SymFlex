restart:
int1:=simplify(int(exp(-2*mu_k*theta)*gr*(mu_k*cos(theta)-sin(theta)), theta)):
C:=simplify(solve(0=subs(theta=Pi/2, int1)+C, C));
w:=simplify((int1+C)/exp(-2*mu_k*theta));
