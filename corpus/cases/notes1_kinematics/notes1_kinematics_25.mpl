# SOURCE: notes1_kinematics block 25 (page 55) - Springzan and Jane: elastic collision
# NOTE: doc output: [[vf1 = vi, vf2 = 0], [vf1 = vi*(-m+M)/(m+M), vf2 = 2*M*vi/(m+M)]]
restart;
p_eqn:=M*vi=M*vf1+m*vf2:
E_eqn:=M*vi^2=M*vf1^2+m*vf2^2:
solve({p_eqn,E_eqn}, [vf1,vf2]);
