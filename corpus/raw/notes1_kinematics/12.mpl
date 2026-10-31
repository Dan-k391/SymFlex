restart;
x:=t->t^3+3*t^2+t+7;
v:=D(x); #alternative derivative notation
v(t);
v0:=D(x)(0); #D has the ability to write derivative at a point
a:=D[1,1](x); #second derivative;
a0:=D[1,1](x)(0);
f:=(x,y)->x^2+2*x*y^2+y^3; #function of 2 variables;
f(1,y);
fsubx:=D[1](f); #partial derivative of f wrt x
fsuby:=D[2](f); #partial derivative of f wrt y
fsubxyy:=D[1,2,2](f);
D[1,2,2](g)(x,y); #D doesn't need to know what the function yet; in that case it just
doesn't evaluate it
convert(%,diff);
