{ SOURCE: lab2 block 14 (para 360) - L13 modification: rocket with universal gravity (FlexPDE) }
{ NOTE: doc image55: val(h,0)= 228884.0 t= 292.4475; FlexPDE 8 gives 228859.0 at t=292.09 }
TITLE 'IVP numeric Solver'     !optional title
COORDINATES cartesian1 !Leave this alone for 2CD4 - this has to do with boundaries, not whether the particle moves in 2D
VARIABLES        !"variables" in Flex are only the ones that need to be defined with a DE
  h(threshold=1e-3) !note that 'x' and 'y' are reserved in Flex, so use different letters
v(threshold=1e-3)
SELECT  ngrid = 1

DEFINITIONS
m0=500
mfuel0 = m0*0.9
qfuel = 5
ve = 1200
tfuel = mfuel0/qfuel
m=if(t<tfuel) then(m0-qfuel*t) else (m0-qfuel*tfuel)
Ft = if(t<tfuel) then(qfuel*ve) else (0)

BigG = 6.674e-11
rEarth = 6371e3
mEarth = 5.97e24
rrel = rEarth+h
Fg = -BigG*mEarth*m/rrel^2
!Fg = -m*9.81
a=(Ft+Fg)/m
INITIAL VALUES !for the "variables"
h = 0    v = 0
EQUATIONS        !DEs (or PDEs) for the "variables"
h: dt(h) = v
v: dt(v) = a

BOUNDARIES       !Leave this alone 2CD4 - This is FEM stuff for defining DEs in space (i.e., instead of in time)
  REGION 1 START(0) LINE TO (1)

TIME 0 TO 500 halt(v<0)    !change this to whatever time range you need to solve for

PLOTS            !Adjust to plot what you need
for t= 0 by endtime/50 to endtime
  history(h) at (0) !make a plot of s vs. time.
!history(v) at (0)

!SUMMARY
report val(h,0)  !says what s is at any time (eventually, what it is when the simulation ended; i.e., at endtime)
!report val(v,0)
!complicated part:
!report val(t,0)!this is not how you report time, because time isn't a "variable" or something that depends on one, so it doesn't get a location and "report val" can get tricked.
report t!this is better for something like t.
END
