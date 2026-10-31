# SOURCE: notes1_kinematics block 10 (page 21) - Substitute; an alternative to function declaration
restart:
x:=t^2-2; #Declaration
x; #x is t^2-2:
subs(t=2, x); #substitute t = 2 into x:
subs(t=Pi, x);
subs(t=y, x);
evalf(subs(t=Pi, x));
Soln:=solve(subs(t=tf, x)=0);
t1,t2:=Soln; #multiple assignment
t1;
t2;
plot(x, t=t1..t2);
subs(t=steve, x);
t1,t2:=solve(%=2);
plot(subs(t=frank, x), frank=t1..t2);
subs(t=subs(t=y,x)+2, x); #compound function evaluation is a lot harder to read using subs instead of function declaration
