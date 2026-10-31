# SOURCE: notes1_kinematics block 22 (page 48) - Maple Dealing: Numeric dsolve (output=listprocedure)
# NOTE: doc outputs: DE1 := diff(w(t),t) = 0.3*w(t)^2 + 29.43000000*cos(q(t)) - 98.10000000*sin(q(t)); dsn1(0.34) = [t(0.34)=0.34, q(t)(0.34)=-0.527438896723720, w(t)(0.34)=-0.0424197855971864]; qsol := proc(t) ... end proc; tfinal := 0.3405670561; qfinal := -0.527450924084159
restart:
g:=9.81: r:=0.1: muk:=0.3:
DE1:=diff(w(t),t)=muk*((w(t))^2+g/r*cos(q(t)))-g/r*sin(q(t)); #DE for omega
DE2:=diff(q(t),t)=w(t); #DE for theta
ICs:=[q(0)=Pi/2, w(0)=0]; #Initial conditions
dsn1:=dsolve({DE1, DE2, op(ICs)}, numeric, output=listprocedure);
dsn1(0.34); #FlexPDE told us the final time was 0.34.  Check what we get at this time.
qsol:=eval(q(t), dsn1); #Assign the q(t) from dsn1 to its own function name.
wsol:=eval(w(t), dsn1); #Assign the w(t) from dsn1 to its own function name.
plot(wsol(t), t=0..0.5); #Examine w(t); look for where omega = 0.
tfinal:=fsolve(wsol(t)=0, t=0.3..0.4); #having found the range, solve for the exact t
plot(qsol(t), t=0..tfinal); #Examine q(t)
qfinal:=qsol(tfinal); #Determine the final angle
