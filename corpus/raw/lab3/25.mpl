KE:=evalf(.5*m*v^2);
U:=evalf(.5*k*s^2);
E:=KE+U:
plot([KE,U,E], t=0..2*Td, legend=['KE','U','Etotal']);
E0:=evalf(subs(t=0,E));
E1:=evalf(subs(t=Td,E));
E2:=evalf(subs(t=2*Td,E));
FracLostInCycle1:=-(E1-E0)/E0;
FracLostInCycle2:=-(E2-E1)/E1;
