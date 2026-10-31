restart;
plot(x^2, x=0..1);  #Plot y = x^2 from x = 0 to x = 1
plot([x^2, x, sqrt(x)], x=0..1); #plot 3 functions
MyList := [x^2, x, sqrt(x)]; #Square brackets mean a list, round brackets mean a
function's argument
plot(MyList, x=-1..1); #Just like giving the plot command the function list directly
