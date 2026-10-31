{ SOURCE: lab3 block 05 (para 127) - P16.1 clifftop launch with wind }
{ NOTE: Word soft line breaks were lost in extraction (e.g. "m=1.9k=300..."); joined definitions were split back onto separate lines }
{ EXPECT: error }
{ NOTE: FlexPDE 8.01 aborts: 'Line N Col 8: A Scalar Evaluation has encountered a Field value with no Location Specified' at the first bare-field REPORT ('report ry'). Doc was made with FlexPDE 6/7 Student which accepted it. With 'report val(X,0)' FlexPDE 8 runs: halts at t=10.045 val(rx,0)=-0.247533 ry=215.8345 KE=1701403; doc image12: t=10.042 rx=-0.094694 ry=216.0455 KE=1700816 (hits cliff face ~216 m up) }
TITLE 'IVP numeric Solver'     !optional title
COORDINATES cartesian1 !Leave this alone for 2CD4 - this has to do with boundaries, not whether the particle moves in 2D
VARIABLES       !"variables" in Flex are only the ones that need to be defined with a DE
  r(threshold=1e-3) =vector(rx,ry)!note that 'x' and 'y' are reserved in Flex, so use different letters
v(threshold=1e-3) =vector(vx,vy)
SELECT  ngrid = 1
DEFINITIONS !!define any parameters you need in terms of the t or the "variables" s or v
ri = vector(0,500)!initial position
theta_i=pi/6
vi=45*vector(cos(theta_i), sin(theta_i))!initial velocity
mi = 500
mfi = mi*0.9
md=mi-mfi
q = 10
ve=800 !fuel exhaust velocity

tfuel = mfi/q
mfuel = if(t<tfuel) then mfi-q*t else 0
m = md + mfuel
Ftmag = if(t<tfuel) then q*ve else 0
ut = v/magnitude(v)
Ft = Ftmag*ut!vector thrust force

Fg = -m*9.81*vector(0,1)!vector weight

CD=.6
Area=5
rho_air=1.2
vwind=vector(-50,0)
vrel = v - vwind !velocity relative to the air
Fd = -0.5*rho_air*CD*Area*magnitude(vrel)*vrel!fluidic drag force

Fnet = Ft+Fg+Fd
a = Fnet/m

KE = .5*m*(magnitude(v))^2

INITIAL VALUES !for the "variables"
v = vi
r = ri

EQUATIONS !DEs (or PDEs) for the "variables"
r: dt(r) = v
v: dt(v) = a

BOUNDARIES       !Leave this alone 2CD4 - This is FEM stuff for defining DEs in space (i.e., instead of in time)
  REGION 1 START(0) LINE TO (1)

TIME 0 TO 200 halt((ry<0) or (ry < 500 and rx < 0))    !change this to whatever time range you need to solve for

PLOTS            !Adjust to plot what you needs
for t= 0 by endtime/50 to endtime
  history(ry) at (0) vs rx !make a trajectory plot
!report h
report val(rx,0)
report ry !val(ry,0)
report KE
!history(Ft, Fg) at (0)
!history(rrel, 500) at(0) !export file 'L14.txt'
END
