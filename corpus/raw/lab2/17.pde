TITLE 'IVP numeric Solver'     !optional title
COORDINATES cartesian1
VARIABLES        !"varialbes" in Flex are only the ones that need to be defined with a DE
  r(threshold=1e-3) = vector(rx, ry) !note that 'x' and 'y' are reserved in Flex, so use different letters
v(threshold=1e-3) = vector(vx, vy)
SELECT  ngrid = 1

DEFINITIONS
!!define any parameters you need in terms of the t or the "variables" s or v
md = 100  mfi = 900   q = 30   ve = 1200     thetai=pi/3
tfuel = mfi/q
mf = if(t<tfuel) then mfi-q*t else 0
m = mf + md
Ftmag = if(t<tfuel) then q*ve else 0
ut = v/magnitude(v)
Ft = Ftmag*ut
bigG=6.674e-11   mearth = 5.97e24   rearth = 6371e3
rrel = vector(rx,ry+rearth)
!Fg = vector(0,-9.81*m)
Fg = -bigG*mearth*m/(magnitude(rrel)^3)*rrel
rrelmag = magnitude(rrel)

a=(Ft+Fg)/m
KE = 0.5*m*(magnitude(v))^2

INITIAL VALUES
!for the "variables"
r = vector(0,0)
v = 50*vector(cos(thetai), sin(thetai))

EQUATIONS
!DEs (or PDEs) for the "variables"
r: dt(r) = v
v: dt(v) = a

BOUNDARIES
!Leave this alone 2CD4.
!(This is FEM stuff for defining DEs in space (i.e., instead of in time))
  REGION 1 START(0) LINE TO (1)

TIME 0 TO 18000 halt (rrelmag<rearth)    !change this to whatever time range you need to solve for

PLOTS            !Adjust to plot what you need
for t= 0 by endtime/50 to endtime
history(ry, -rearth+sqrt(rearth^2-rx^2)) at (0) vs rx !make a plot of ry vs. rx
report val(rx,0)
report t
report val(KE,0)
!SUMMARY
!report val(s,0)  !says what s is at any time (eventually, what it is when the simulation ended; i.e., at endtime)
!report val(v,0)
!complicated part:
!report val(t,0)!this is not how you report time, because time isn't a "variable" or something that depends on one, so it doesn't get a location and "report val" can get tricked.
!report t!this is better for something like t.
END
