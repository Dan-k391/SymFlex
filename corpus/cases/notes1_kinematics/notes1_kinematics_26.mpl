# SOURCE: notes1_kinematics block 26 (page 56) - Springzan and Jane: numbers given, m = M/2
# DEPENDS: notes1_kinematics_25
# NOTE: doc output: [[vf1 = vi, vf2 = 0], [vf1 = vi/3, vf2 = 4*vi/3]]
restart;
p_eqn:=M*vi=M*vf1+m*vf2:
E_eqn:=M*vi^2=M*vf1^2+m*vf2^2:
solve({p_eqn,E_eqn}, [vf1,vf2]);
subs(m=M/2, %);
