# SOURCE: notes1_kinematics block 09 (page 21) - Function declaration & Multiple assignment
restart;
x:=t->t^2-2; #function assignment
x; #x is a function
x(2);
x(Pi);
x(y);
evalf(x(Pi)); #evaluate as a floating point number
Soln:=solve(x(tf) = 0);
t1,t2:=Soln; #multiple assignment
t1;
t2;
plot(x(t), t=t1..t2);
x(steve); #functions will sub whatever you type into them
t1,t2:=solve(x(steve)=2);
plot(x(frank), frank=t1..t2);
x(x(y)+2); #compound function evaluation
