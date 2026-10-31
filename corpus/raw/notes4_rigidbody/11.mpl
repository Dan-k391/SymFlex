> restart:
MA:=10/32.2: LA:=2:
MoIOA:=1/3*MA*LA^2;
MB:=8/32.2: LB:=2*0.75:
MoIB:=1/12*MB*LB^2+MB*LA^2;
MoI:=MoIOA+MoIB;
y:=(LA/2*MA+LA*MB)/(MA+MB);
MoIOA:=1/12*MA*LA^2+MA*(y-1)^2;
MoIB:=1/12*MB*LB^2+MB*(LA-y)^2;
MoIB+MoIOA;
