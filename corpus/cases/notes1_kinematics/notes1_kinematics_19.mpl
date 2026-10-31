# SOURCE: notes1_kinematics block 19 (page 45) - Part 2 Option B: Have Maple solve the halfpipe IVP
# NOTE: doc output: w(q) = -6*exp(2*muk*q)*g*r*muk/((4*muk^2+1)*exp(muk*Pi)) + 2*g*r*(-2*cos(q)*muk^2+3*sin(q)*muk+cos(q))/(4*muk^2+1); then w(q) = -12.98382353*exp(0.6*q)/exp(0.9424777962) + 11.82970588*cos(q) + 12.98382353*sin(q); plot crosses zero near q=-0.5
restart: #Clears variables
dsolve({g*r*sin(q)+1/2*diff(w(q), q) = muk*(g*r*cos(q)+w(q)), w(Pi/2)=0}); #Solves the IVP
subs([g=9.81, r=1, muk=0.3], %); #Substitutes values for the constants into the DE solution
assign(%); #Makes w(q) assigned to the solution
plot(w(q), q=-Pi/2..Pi/2); #Plots w(q)
