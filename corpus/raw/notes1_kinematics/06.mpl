restart;
eqn:=4=3*tan(theta) - 9.81/2/10^2*3^2/(cos(theta))^2;  #an equation
eqn;
rhs(eqn); #right hand side
lhs(eqn);
solve(eqn);
solve(rhs(eqn)=0);  #solving a different equation
solve(rhs(eqn)); #assumes you mean = 0 if you give solve only half of an equation
plot(rhs(eqn), theta=-Pi..Pi);  #note that Pi = 3.14159, but pi and PI are initially
undefined variables.
plot(rhs(eqn), theta=-Pi..Pi, y = -1..1); #Restrict the vertical range
fsolve(rhs(eqn)); #numeric solve; only finds one root and does it numerically (using
something like Newton's Method for Approximating Roots)
fsolve(rhs(eqn), theta = 1..2); #with fsolve you can specify a range to look for the
root; use plots to figure out where to look
