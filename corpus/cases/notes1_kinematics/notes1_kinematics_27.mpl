# SOURCE: notes1_kinematics block 27 (page 66) - Astronauts: moment of inertia about the centre of mass
# NOTE: doc output: MoI := (M+m)*M*L^2/(2*M+m). Named MoI because I = sqrt(-1) in Maple.
restart;
xbar:=M*L/(2*M+m):
MoI:=simplify((M+m)*xbar^2+M*(L-xbar)^2);
