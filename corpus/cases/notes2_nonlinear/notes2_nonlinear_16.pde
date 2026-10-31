{ SOURCE: notes2_nonlinear block 16 (page 26) - vector field visualization of the PP1.7 wind field }
{ Fill in the following sections (removing comment marks ! if necessary),
  and delete those that are unused.}
TITLE 'New Problem'     { the problem identification }
COORDINATES cartesian2  { coordinate system, 1D,2D,3D, etc }
select
ngrid = 13
VARIABLES        { system variables }
  u              { choose your own names }
! SELECT         { method controls }
DEFINITIONS    { parameter definitions }
vwind= 6*exp(-sqrt(r/50))*Vector(x, -y/(x^2+.01)+r/2)
! INITIAL VALUES
EQUATIONS        { PDE's, one for each variable }
  div(grad(u))=0 { one possibility }
! CONSTRAINTS    { Integral constraints }
BOUNDARIES       { The domain definition }
  REGION 1       { For each material region }
    START(0,0)   { Walk the domain boundary }
    LINE TO (2,0) TO (2,3) TO (0,3) TO CLOSE
! TIME 0 TO 1    { if time dependent }
MONITORS         { show progress }
PLOTS            { save result displays }
!  CONTOUR(u)
vector(vwind) norm
vector(vwind)
END
