TITLE 'Projectile Motion'
COORDINATES cartesian2
VARIABLES
vx(threshold=0.1)  !velocity in x
vy(threshold=0.1)
!velocity in y
xd(threshold=0.1)
!x-displacement
yd(threshold=0.1)   !y-displacement
SELECT
ngrid = 1 !since we're not using spatial dependence within the
object we don't need a dense mesh
DEFINITIONS
xi=0 !initial coordinates
yi=0
vi = 21
!initial velocity
theta_i = 60*pi/180 !initial angle
g  = 9.8
ax = 0
ay = -g !acceleration due to gravity only
INITIAL VALUES
vx = vi*cos(theta_i)
vy = vi*sin(theta_i)
xd = xi
yd = yi
EQUATIONS
vx: dt(vx) = ax
vy: dt(vy) = ay
xd: dt(xd) = vx
yd: dt(yd) = vy
BOUNDARIES       { The domain definition }
  REGION 1       { For each material region }
    START(0,0)   { Walk the domain boundary }
    LINE TO (1,0) TO (1,1) TO (0,1) TO CLOSE
TIME 0 TO 50 halt yd<0    { if time dependent }
PLOTS
for t = 0 by 0.1 to endtime
history(xd,yd) at (0,0)
SUMMARY
report val(xd,0,0) as 'xd'
report val(yd,0,0) as 'yd'
report t
END
