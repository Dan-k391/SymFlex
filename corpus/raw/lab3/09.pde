TITLE 'IVP numeric Solver'     !optional title
COORDINATES cartesian1 !Leave this alone for 2CD4 - this has to do with boundaries, not whether the particle moves in 2D
VARIABLES       !"variables" in Flex are only the ones that need to be defined with a DE
  s(threshold=1e-3) !note that 'x' and 'y' are reserved in Flex, so use different letters
v(threshold=1e-3)
SELECT  ngrid = 1
DEFINITIONS !!define any parameters you need in terms of the t or the "variables" s or v
m=1.9k=300s0=0.1v0=0

Fs = -k*s

Fnet = Fs
a = Fnet/m

KE=0.5*m*v^2
Us=0.5*k*s^2

INITIAL VALUES !for the "variables"
s = s0
v = v0

EQUATIONS !DEs (or PDEs) for the "variables"
s: dt(s) = v
v: dt(v) = a

BOUNDARIES       !Leave this alone 2CD4 - This is FEM stuff for defining DEs in space (i.e., instead of in time)
  REGION 1 START(0) LINE TO (1)

TIME 0 TO 0.5 ! halt(h<0)    !change this to whatever time range you need to solve for

PLOTS            !Adjust to plot what you needs
for t= 0 by endtime/50 to endtime
  history(s, v/10, a/100) at (0) !make a plot of s vs. time.
report s
report v
history(KE, Us, KE+Us) at (0)
END
