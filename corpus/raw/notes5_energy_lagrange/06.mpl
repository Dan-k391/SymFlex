> restart: g:=9.81: R:=.2: IG:=.156: h:=.03: m:=10:
ConsAngMom:=IG*v2/R+m*v2*R=IG*v1/R+m*v1*(R-h);
ConsEnergy:=-.5*(IG*(v2/R)^2+m*v2^2)=-m*g*h;
simplify(solve([ConsAngMom, ConsEnergy], [v1, v2]));
