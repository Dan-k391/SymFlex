{ SOURCE: notes2_nonlinear block 11 (page 14) - FlexPDE misaligned shuttle booster: solve for angles }
title "RocketMisaligned" !Script made 5 Sep 2016 by Minnick for Rocketry intro
SELECT
ngrid=1
COORDINATES
cartesian2
VARIABLES {Lists the dependent variables we have DEs for, and some tolerance
thresholds (sort of lists how accurate we need them determined)}
      q (threshold=0.1)
      w (threshold = 0.1)
DEFINITIONS
Lb=10

{Variables; write constants and expressions used in DE solving}
t0 = 0.0
g = 9.8       {acceleration due to gravity}

xb=6
mb = 400e3-3500*t
mst = 22400+760e3
mtotal = mb+mst
xcm = xb*mb/mtotal      !centre of mass
L = 47       !length of shuttle = length of booster

FB = 13.8e6 !booster force
torque = (xb-xcm)*FB
MoI = mtotal*L^2/12 + xcm^2*mst + (6-xcm)^2*mb !moment of inertia
alpha = torque/MoI
INITIAL VALUES    {For the DE}
q = 0
w = 0
EQUATIONS   {The DEs. dt(w) means "derivative of w with respect to t" in
FlexPDE}
w: dt(w) = alpha
q: dt(q) = w

BOUNDARIES
      Region 1
            START(-Lb,0)
                  line to (Lb,0)
                  line to (Lb,Lb)
                  line to (-Lb,Lb)
            line to close

Time 0 by 0.1 to 60 halt (mb<0)
PLOTS {Things to plot after solving}
  for t=t0 by 1 to endtime
history (w) at (0,0) as "angular velocity"
history (q) at (0,0) as "angle"

SUMMARY
      report t as "Time to stop [s]"
      report eval(w,0,0) as "Final angle Velocity"
      report eval(q,0,0) as  "Final position"
end
