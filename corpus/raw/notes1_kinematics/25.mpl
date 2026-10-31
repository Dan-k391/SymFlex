restart;
p_eqn:=M*vi=M*vf1+m*vf2:
E_eqn:=M*vi^2=M*vf1^2+m*vf2^2:
solve({p_eqn,E_eqn}, [vf1,vf2]);
