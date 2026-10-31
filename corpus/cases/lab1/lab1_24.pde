{ SOURCE: lab1 block 24 (para 574) - Use the FlexPDE code we developed in class starting with the IVP templ... }
TITLE 'IVP numeric Solver'
COORDINATES cartesian1
VARIABLES
  	r(threshold=1e-2) = vector(rx,ry)
	v(threshold=1e-2) = vector(vx,vy)
SELECT  ngrid = 1 errlim=1e-2
DEFINITIONS
k_e = 8.99e9
q1=5e-3 	q2 = -20e-6  	m=2
r5 = vector(-2,3)
rrel = r-r5
rrelmag = magnitude(rrel)
rrelhat = rrel/rrelmag
FC = k_e*q1*q2/rrelmag^2*rrelhat
a = FC/m
INITIAL VALUES
r=vector(2,4) 		v=vector(0,8)
EQUATIONS
r: dt(r) = v
v: dt(v) = a
BOUNDARIES
  REGION 1 START(0) LINE TO (1)
TIME 0 TO 2
PLOTS
for t= 0 by endtime/50 to endtime
    history(ry) at (0) vs rx
END
