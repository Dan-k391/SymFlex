restart;
Eqn1:=x^2+3*x*y=0:
Eqn2:=y-2*x = 7:
solve([Eqn1, Eqn2]); #solve 2 equations in 2 unknowns; output is in random order
solve([Eqn1, Eqn2], [x,y]); #solve 2 equations in 2 unknowns, and always output x
before y in the list
solve(Eqn2, x);  #solve 1 equation in 2 unknowns for the variable you want
Eqn3:=z*2+x*y-y^2=1:
solve([Eqn2, Eqn3], [x,z]); #specify several variables to solve for
op(%); #open a list. removes brackets
%[1]; #again
x;
assign(%%); #executes x:=y/2-7/2
x;
