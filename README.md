# master-project test
Robustness of European Electricity Price Stability Estimates: A PyPSA-based Replication and Sensitivity Analysis

In this project, the power price simulation from the paper 
Power price stability and the insurance value
of renewable technologies
https://doi.org/10.1038/s41560-025-01704-0
shall be validated. Therefore, a model for the European Energy Market is implemented using PyPSA and the same input-values will be used as in the paper.

Approach:

--> Organize Input-data into different .csv-files (Use an authomatic approach as much as possible)
--> Implement a model of the grid using this data
--> Run powerflow calculations/optimize the model to retrieve price-time series
--> Compare this first price timeseries with the output of the paper (which used GenX)
--> Include variety in input data (as in the paper)
--> Do beta-sensitivity analysis
