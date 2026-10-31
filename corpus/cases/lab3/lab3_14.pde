{ SOURCE: lab3 block 14 (para 362) - L18 linear damper FlexPDE }
{ NOTE: Word soft line breaks were lost in extraction (e.g. "m=1.9k=300..."); joined definitions were split back onto separate lines }
{ EXPECT: error }
{ NOTE: FlexPDE 8.01 aborts: 'Line N Col 8: A Scalar Evaluation has encountered a Field value with no Location Specified' at the first bare-field REPORT ('report s'). Doc was made with FlexPDE 6/7 Student which accepted it. With 'report val(X,0)' FlexPDE 8 runs: t=1.0227 (=2*Td) s=6.789458e-3 v=2.965219e-4 Etotal/Etotal0=4.609729e-3 (doc image68 is only a thumbnail) }
TITLE 'IVP numeric Solver'     !optional title
COORDINATES cartesian1 !Leave this alone for 2CD4 - this has to do with boundaries, not whether the particle moves in 2D
VARIABLES       !"variables" in Flex are only the ones that need to be defined with a DE
  s(threshold=1e-3) !note that 'x' and 'y' are reserved in Flex, so use different letters
v(threshold=1e-3)
SELECT  ngrid = 1
DEFINITIONS !!define any parameters you need in terms of the t or the "variables" s or v
m=1.9
k=300
b=10
s0=0.1
v0=0

Fs = -k*s
Fd = -b*v

omega0=sqrt(k/m)
T0=2*pi/omega0

zeta=b/(2*sqrt(m*k))
omegad = omega0*sqrt(1-zeta^2)
Td = 2*pi/omegad

Fnet = Fs + Fd
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

TIME 0 TO Td*2 ! halt(h<0)    !change this to whatever time range you need to solve for

PLOTS            !Adjust to plot what you needs
for t= 0 by endtime/50 to endtime
  history(s, v/10, a/100) at (0) !make a plot of s vs. time.
report s
report v
history(KE, Us, KE+Us) at (0)
report Etotal/Etotal0
END
