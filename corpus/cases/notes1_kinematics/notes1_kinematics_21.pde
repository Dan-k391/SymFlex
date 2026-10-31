{ SOURCE: notes1_kinematics block 21 (page 47) - Option C: Solving Block in a Turnpike with FlexPDE }
{ NOTE: doc SUMMARY output: Time to stop [s]= 0.341440, Final angle Velocity= 0.048291, Final position= -0.527508 }
{ NOTE: FlexPDE 8 Lite runs cleanly (no errors, 197 steps, "Halt on User Condition") but reports Time to stop [s]= 0.342949, Final position= -0.527350 - slightly different from the document (older FlexPDE version). }
TITLE "Turnpike"
!This is a single line comment
 {This is a multi-line
 comment.
Script made 31 Aug 2016 by Minnick for Lecture 6 of EP 2P04 2016}
  SELECT      {Not important - FEM Stuff}
     ngrid=1
COORDINATES{Not important - FEM Stuff}
 cartesian2
VARIABLES {Lists the dependent variables we have DEs for, and some tolerance thresholds (sort of lists how accurate we need them determined)}
     q (threshold=0.01)
       w (threshold = 0.01)
DEFINITIONS
  Lb=10 {Not important - FEM Stuff}


{Variables; write constants and expressions used in DE solving}
    t0 = 0.0
       g = 9.8       {acceleration due to gravity}
    r=0.1
       muk=0.3

  INITIAL VALUES    {For the DE}
    q = 3.14159/2
       w = 0
  EQUATIONS   {The DEs.   dt(w) means "derivative of w with respect to t" in FlexPDE}
     w: dt(w) =muk*(w^2+g/r*cos(q))-g/r*sin(q)
        q: dt(q) = w

 BOUNDARIES {Not important - FEM Stuff}
     Region 1
        start(-Lb,0)
         line to (Lb,0)
        line to (Lb,Lb)
        line to (-Lb,Lb)
        line to close

  time 0 to 600 halt ((w > 0) or (q < -3.14159/2))  {halt condition set to be when w stops being negative (which is better than w=0 for numeric solutions) or q < -Pi/2 (off the turnpike)}


  PLOTS {Things to plot after solving}

  for t=t0 by 0.1 to endtime

history (w) at (0,0) as "angular velocity"
history (q) at (0,0) as "angle"

SUMMARY
report t as "Time to stop [s]"
report eval(w,0,0) as "Final angle Velocity"
report eval(q,0,0) as  "Final position"
end
