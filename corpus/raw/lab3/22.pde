TITLE 'IVP numeric Solver'     !optional title
COORDINATES cartesian1 !Leave this alone for 2CD4 - this has to do with boundaries, not whether the particle moves in 2D
VARIABLES       !"variables" in Flex are only the ones that need to be defined with a DE
  s(threshold=1e-3) !note that 'x' and 'y' are reserved in Flex, so use different letters
v(threshold=1e-3)
SELECT  ngrid = 1
DEFINITIONS !!define any parameters you need in terms of the t or the "variables" s or v
m=20k=800.8s0=0.03v0=0

Fs = -k*s
b = 0.5*1200*5*0.01

omega0=sqrt(k/m)
T0=2*pi/omega0

Fnet = Fs - b*v
a = Fnet/m

KE=0.5*m*v^2
Us=0.5*k*s^2
Etotal=KE+Us

Etotal0 = 0.5*m*v0^2+0.5*k*s0^2 !initial energy

INITIAL VALUES !for the "variables"
s = s0
v = v0

EQUATIONS !DEs (or PDEs) for the "variables"
s: dt(s) = v
v: dt(v) = a

BOUNDARIES       !Leave this alone 2CD4 - This is FEM stuff for defining DEs in space (i.e., instead of in time)
  REGION 1 START(0) LINE TO (1)

TIME 0 TO T0 ! halt(h<0)    !change this to whatever time range you need to solve for

PLOTS            !Adjust to plot what you needs
for t= 0 by endtime/50 to endtime
  history(s, v/10, a/100) at (0) !make a plot of s vs. time.
report s
report v
history(KE, Us, KE+Us) at (0)
report Etotal/Etotal0
END
