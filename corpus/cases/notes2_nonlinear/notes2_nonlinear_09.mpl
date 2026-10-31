# SOURCE: notes2_nonlinear block 09 (page 11) - piecewise booster mass that detaches at t=60
# NOTE: in the document this line is meant to replace the mbooster definition in block 04/05; it is tested standalone; ends with ":" so it prints nothing
mbooster:=piecewise(t<60, 400000-3500*t, t>=60, 0):
