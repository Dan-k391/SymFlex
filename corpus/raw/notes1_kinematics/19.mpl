restart: #Clears variables
dsolve({g*r*sin(q)+1/2*diff(w(q), q) = muk*(g*r*cos(q)+w(q)), w(Pi/2)=0}); #Solves the
IVP
subs([g=9.81, r=1, muk=0.3], %); #Substitutes values for the constants into the DE
solution
assign(%); #Makes w(q) assigned to the solution
plot(w(q), q=-Pi/2..Pi/2); #Plots w(q)
