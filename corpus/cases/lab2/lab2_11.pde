{ SOURCE: lab2 block 11 (para 218) - L13 rocket thrust, universal gravity 1D IVP }
{ NOTE: doc image48 (FlexPDE 6): val(h,0)= 148781.1 at t=252; FlexPDE 8 gives 148775.2 }
{ NOTE: repaired extraction artifact: 'mi=1000mfi' and 'q = 8ve' were two definitions per line separated by a tab (see doc image47) }
TITLE 'IVP numeric Solver'     !optional title
COORDINATES cartesian1 !Leave this alone for 2CD4 - this has to do with boundaries, not whether the particle moves in 2D
VARIABLES        !"variables" in Flex are only the ones that need to be defined with a DE
  h(threshold=1e-3) !note that 'x' and 'y' are reserved in Flex, so use different letters
v(threshold=1e-3)
SELECT  ngrid = 1

DEFINITIONS
!Rocket Pararmeters:
mi=1000   mfi = mi*0.8
q = 8   ve = 1500
tfuel = mfi/q
Ft = if(t<tfuel) then q*ve else 0
mfuel = if(t<tfuel) then mfi-q*t else 0
mdry = mi - mfi
m = mdry + mfuel

!Universal Gravity:
BigG = 6.674e-11
mEarth = 5.97e24
rEarth = 6371e3
rrel = rEarth+h
FG = -BigG*mEarth*m/rrel^2

FNet = Ft+FG
a=FNet/m

INITIAL VALUES  !for the "variables"
h = 0
v = 0

EQUATIONS  !DEs (or PDEs) for the "variables"
h: dt(h) = v
v: dt(v) = a

BOUNDARIES       !Leave this alone 2CD4 - This is FEM stuff for defining DEs in space (i.e., instead of in time)
  REGION 1 START(0) LINE TO (1)

TIME 0 TO 300 halt(v<0)    !change this to whatever time range you need to solve for

PLOTS            !Adjust to plot what you need
for t= 0 by endtime/50 to endtime
  history(h) at (0) !make a plot of s vs. time.
report val(h,0)
history(v) at (0)
report val(v,0)

END
