{ SOURCE: lab2 block 20 (para 595) - L14 modification 1: V3 rocket v0=20 m/s at 45 deg }
{ EXPECT: error }
{ NOTE: doc image80: rx= 197214.3 t= 87.88285 KE= 1.880397e+8 (FlexPDE 6); FlexPDE 8 patched copy halts at t=90 (end of fuel burn step) with val(rx,0)=202923.0 val(KE,0)=1.883417e+8 }
{ NOTE: FlexPDE 8.01 aborts: 'Line N Col 8: A Scalar Evaluation has encountered a Field value with no Location Specified' at 'report rx' (bare field in REPORT). Doc was made with FlexPDE 6 Student which accepted it. With 'report val(rx,0)' and 'report val(KE,0)' FlexPDE 8 runs and halts on ry<0. }
TITLE 'IVP numeric Solver'     !optional title
COORDINATES cartesian1 !Leave this alone for 2CD4 - this has to do with boundaries, not whether the particle moves in 2D
VARIABLES        !"variables" in Flex are only the ones that need to be defined with a DE
  r(threshold=1e-3) =vector(rx,ry)!note that 'x' and 'y' are reserved in Flex, so use different letters
v(threshold=1e-3)=vector(vx,vy)
SELECT  ngrid = 1

DEFINITIONS
v0=20 theta0=Pi/4

m0=500
mfuel0 = m0*0.9
qfuel =20
ve = 1200
tfuel = mfuel0/qfuel
m=if(t<tfuel) then(m0-qfuel*t) else (m0-qfuel*tfuel)
Ftmag = if(t<tfuel) then(qfuel*ve) else (0)

vmag = sqrt(dot(v,v))
vhat = v/vmag
Ft = Ftmag*vhat !thrust force is in direction of motion

Fg = -m*9.81*vector(0,1) !gravity is in the -y direction
a=(Ft+Fg)/m
KE = .5*m*vmag^2
INITIAL VALUES !for the "variables"
r=vector(0,0)
v=v0*vector(cos(theta0),sin(theta0))
EQUATIONS        !DEs (or PDEs) for the "variables"
r: dt(r) = v
v: dt(v) = a

BOUNDARIES       !Leave this alone 2CD4 - This is FEM stuff for defining DEs in space (i.e., instead of in time)
  REGION 1 START(0) LINE TO (1)

TIME 0 TO 500 halt(ry<0)    !change this to whatever time range you need to solve for

PLOTS            !Adjust to plot what you need
for t= 0 by endtime/50 to endtime
  history(ry) at (0) vs rx !trajectory plot
report rx
report t
report KE
!history(vx,vy) at (0)
!history(Ftmag)
!history(KE) at (0) report KE
END
