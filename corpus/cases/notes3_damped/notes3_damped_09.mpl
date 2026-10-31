# SOURCE: notes3_damped block 09 (page 16) - Amplitude & phase shift log plots (loglogplot/semilogplot)
restart;
w0:=10: x0:=1: zeta:=1/16:
A:=x0*w0^2/sqrt((w^2-w0^2)^2+(2*zeta*w0*w)^2);
phi:=-arctan((w^2-w0^2)/(2*zeta*w0*w))-Pi/2;
with(plots): #Includes the plots package in Maple, which is required for advanced plotting like loglogplot() and semilogplot()
loglogplot(A, w=1..100, numpoints=1000); #loglogplot is log horizontal, log vertical
semilogplot(phi*180/Pi, w=1..100); #semilogplot is log horizontal, linear vertical
