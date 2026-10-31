# SOURCE: notes1_kinematics block 14 (page 43) - Block in a halfpipe, Option A: Maple does the integrating-factor integral
# NOTE: doc output: -exp(-2*mu_k*theta)*gr*(2*mu_k^2*cos(theta)-3*mu_k*sin(theta)-cos(theta))/(4*mu_k^2+1)
simplify(int(exp(-2*mu_k*theta)*gr*(mu_k*cos(theta)-sin(theta)), theta));
