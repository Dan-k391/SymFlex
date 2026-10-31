{ SOURCE: lab4 block 07 (para 110) - L22 coupled resonators FlexPDE IVP }
TITLE 'IVP numeric Solver'     !optional title
COORDINATES cartesian1 !Leave this alone for 2CD4 - this has to do with boundaries, not whether the particle moves in 2D
VARIABLES       !"variables" in Flex are only the ones that need to be defined with a DE
  	st(threshold=1e-3) !note that 'x' and 'y' are reserved in Flex, so use different letters
	vt(threshold=1e-3)
  	sb(threshold=1e-3) !note that 'x' and 'y' are reserved in Flex, so use different letters
	vb(threshold=1e-3)
SELECT  ngrid = 1
DEFINITIONS !!define any parameters you need in terms of the t or the "variables" s or v
mt=1000		mb=1		fres=1		omega0=2*pi*fres		kt=mt*omega0^2		kb=mb*omega0^2
Qt=10		Qb=20		bt=sqrt(mt*kt)/Qt		bb=sqrt(mb*kb)/Qb

Tres=1/fres
sf=1e-3*cos(omega0*t)

Fnb = -kb*(sb-st)-bb*vb
Fnt = -kt*(st-sf)-bt*vt+kb*(sb-st)

INITIAL VALUES !for the "variables"

EQUATIONS !DEs (or PDEs) for the "variables"
st: dt(st) = vt
vt: dt(vt) = Fnt/mt
sb: dt(sb)=vb
vb: dt(vb)=Fnb/mb

BOUNDARIES       !Leave this alone 2CD4 - This is FEM stuff for defining DEs in space (i.e., instead of in time)
  REGION 1 START(0) LINE TO (1)

TIME 0 TO Tres*30  ! halt(h<0)    !change this to whatever time range you need to solve for

PLOTS            !Adjust to plot what you needs
for t= 0 by endtime/50 to endtime
  	history(sf, st, sb) at (0)
  	history(sf*100, st*10, sb) at (0) window(Tres*25,Tres*30) !make a plot of s vs. time.

END
