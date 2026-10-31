TITLE 'IVP numeric Solver'     !optional title
COORDINATES cartesian1 !Leave this alone for 2CD4 - this has to do with boundaries, not whether the particle moves in 2D
VARIABLES       !"variables" in Flex are only the ones that need to be defined with a DE
  r(threshold=1e-3) =vector(rx,ry)!note that 'x' and 'y' are reserved in Flex, so use different letters
v(threshold=1e-3) =vector(vx,vy)
SELECT  ngrid = 1
DEFINITIONS !!define any parameters you need in terms of the t or the "variables" s or v
ri = vector(-8e3,0)!initial position
theta_i=pi/4vi=40*vector(cos(theta_i), sin(theta_i))!initial velocity
mi = 600mfi = mi*0.6md=mi-mfi
q = 20ve=1000 !fuel exhaust velocity

tfuel = mfi/qmfuel = if(t<tfuel) then mfi-q*t else 0
m = md + mfuel
Ftmag = if(t<tfuel) then q*ve else 0
ut = v/magnitude(v)
Ft = Ftmag*ut!vector thrust force

Fg = -m*9.81*vector(0,1)!vector weight

rrel = sqrt(rx^2+ry^2) !position relative to the weather controller @ the origin
CD=.1Area=1rho_air=(1.2+10/sqrt(rrel/50+1))
vwind=6*exp(-sqrt(rrel/50))*vector(rx, -ry/(rx^2+.01)+rrel/2)
vrel = v - vwind !velocity relative to the air
Fd = -0.5*rho_air*CD*Area*magnitude(vrel)*vrel!fluidic drag force

Fnet = Ft+Fg+Fd
a = Fnet/m

KE = .5*m*(magnitude(v))^2

INITIAL VALUES !for the "variables"
v = vir = ri

EQUATIONS !DEs (or PDEs) for the "variables"
r: dt(r) = v
v: dt(v) = a

BOUNDARIES       !Leave this alone 2CD4 - This is FEM stuff for defining DEs in space (i.e., instead of in time)
  REGION 1 START(0) LINE TO (1)

TIME 0 TO 200 halt(ry<0 or rrel<500)    !change this to whatever time range you need to solve for

PLOTS            !Adjust to plot what you needs
for t= 0 by endtime/50 to endtime
  history(ry) at (0) vs rx !make a trajectory plot
!report h
report val(rx,0)
report ry !val(ry,0)
report KE
!history(Ft, Fg) at (0)
history(rrel, 500) at(0) !export file 'L14.txt'
END
