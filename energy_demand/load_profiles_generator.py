""" These functions read in raw csv files to generate load functions """
import numpy as np
import os
import csv
import main_functions as mf

from datetime import date
import unittest
import matplotlib.pyplot as plt

# Yearly 

# Daily load profiles
# dtype, hour, data
# 
#



'''

def get_max_daily_load(main_dict_dayyear):
    result_max = {0: None, 1: None}
    # Iterate days to get maximum day
    for daytape in main_dict_dayyear:
        max_p_demand_of_an_hour = 0 

        for day in main_dict_dayyear[daytape]:
            daily_max = max(main_dict_dayyear[daytape][day])

            if max_p_demand_of_an_hour < daily_max:
                daytype_max = day
        
        result_max[daytape] = main_dict_dayyear[daytape][daytype_max]
    
    return result_max

'''
'''
def ABSOLUTE (main_dict_dayyear_absolute):
    """
    This function creates the shape of the base year heating demand over the full year

    """

    # Initilaise array to store all values for a year
    daytype, year_days, hours = 2, 365, 24

    # Get hourly distribution (Sansom Data)
    # ------------------------------------
    hourly_hd = np.zeros((1, hours), dtype=float)

    # List storing all
    yeardays_percent = np.zeros((year_days, hours), dtype=float)

    # Initialise dictionary with every day and hour
    hd_data = np.zeros((daytype, year_days, hours), dtype=float)

    for yearday in main_dict_dayyear_absolute:
        #_info = main_dict_dayyear_absolute[yearday].timetuple() # Get date
        #yearday_python = _info[7] - 1    # - 1 because in _info: 1.Jan = 1
        #weekday = _info[6]                # 0: Monday

        year_raw_values[yearday] = main_dict_dayyear_absolute[yearday] # Copy all values into

        # Distribute daily deamd into hourly demand
        if weekday == 5 or weekday == 6:
            _data = hourly_gas_shape_wkend * heating_demand_correlation
            hd_data[yearday_python] = _data  # DATA ARRAY
        else:
            _data = hourly_gas_shape_wkday * heating_demand_correlation
            hd_data[yearday_python] = _data  # DATA ARRAY

    # Convert yearly data into percentages (create shape). Calculate Shape of the eletrictiy distribution of the appliances by assigning percent values each
    total_y_hd = hd_data.sum()  # Calculate yearly total demand over all day years and all appliances
    shape_hd = np.zeros((len(year_days), len(hours)), dtype=float)
    shape_hd = (1.0/total_y_hd) * hd_data

    return shape_hd
'''

def read_in_non_residential_load_curves():
    """
    Folder with all csv files stored
    """
    # Dictionary: month, daytype, hour
    #
    # 0. Find what day it is (with date function). Then define daytype and month
    # 1. Calculate total demand of every day
    # 2. Assign percentag of total daily demand to each hour

    # out_dict_av: Every daily measurment is taken from all files and averaged
    # out_dict_not_average: Every measurment of of every file is plotted

    #folder_path = r'C:\Users\cenv0553\Dropbox\00-Office_oxford\07-Data\09_Carbon_Trust_advanced_metering_trial_(owen)\_all_gas' #Community
    folder_path = r'C:\Users\cenv0553\Dropbox\00-Office_oxford\07-Data\09_Carbon_Trust_advanced_metering_trial_(owen)\__OWN_SEWAGE' #Community

    all_csv_in_folder = os.listdir(folder_path) # Get all files in folder

    # Initialize dict with list for every hour dict = {daytype: {month: {}}
    main_dict = {0: {}, 1: {}}
    for i in main_dict:
        month_dict = {}
        for f in range(12):
            day_dict = {k: [] for k in range(24)}
            month_dict[f] = day_dict
        main_dict[i] = month_dict

    # Initialise yearday dict
    main_dict_dayyear_absolute = {}
    for f in range(365):
        day_dict_h = {k: [] for k in range(24)}
        main_dict_dayyear_absolute[f] = day_dict_h



    # Dict
    dict_result = {0: {}, 1: {}}

    # Initial dict
    #array_results = np.zeros((2, 12, 24), dtype = float) # datyape, month, hours

    nr_of_line_entries = 0

    # Itreateu folder with csv files
    for path_csv_file in all_csv_in_folder:
        path_csv_file = os.path.join(folder_path, path_csv_file)
        print("path: " + str(path_csv_file))

        # Read csv file
        with open(path_csv_file, 'r') as csv_file:            # Read CSV file
            read_lines = csv.reader(csv_file, delimiter=',')  # Read line
            _headings = next(read_lines)                      # Skip first row

            # Iterate day
            for row in read_lines:

                # Test if file has correct form
                if len(row) != 49: # Skip row
                    continue

                # Test if file has 365 entries:

                
                #try:
                # Convert all values except date into float values
                row[1:] = map(float, row[1:])

                #e xcept ValueError:
                #    # Something is wrong with original raw file...()
                #    continue

                # Total daily sum
                daily_sum = sum(row[1:])

                if daily_sum == 0: # Skip row if no demand of the day
                    print("TOTAL SUM IS 0")
                    continue

                # Nr of lines added
                nr_of_line_entries += 1

                day = int(row[0].split("/")[0])
                month = int(row[0].split("/")[1])
                year = int(row[0].split("/")[2])

                date_row = date(year, month, day)

                # Daytype
                daytype = mf.get_weekday_type(date_row)

                # Get Dayyear
                _info = date_row.timetuple()
                yearday_python = _info[7] - 1    # - 1 because in _info: 1.Jan = 1

                # Month Python
                month_python = month - 1

                # Iterate hours
                cnt, h_day, control_sum = 0, 0, 0 

                for half_hour_val in row[1:]:  # Skip date
                    cnt += 1
                    if cnt == 2:
                        control_sum += abs(first_half_hour + half_hour_val)
                        main_dict[daytype][month_python][h_day].append((first_half_hour + half_hour_val) * (100 / daily_sum)) # Calc percent of total daily demand

                        # Add to day_dict absolute numbers
                        #main_dict_dayyear_absolute[yearday_python][h_day].append((first_half_hour + half_hour_val)) # Calc percent of total daily demand

                        cnt = 0
                        h_day += 1

                    first_half_hour = half_hour_val # must be at this position

                # Check if 100 %
                assertions = unittest.TestCase('__init__')
                assertions.assertAlmostEqual(control_sum, daily_sum, places=7, msg=None, delta=None)


    # Get min and max daily load curve over the full year
    #(main_dict_dayyear_absolute)

    #max_loads = get_max_daily_load(main_dict_dayyear) # Funkt nicht
    #print(max_loads)
    #prnt("..")
    # -----------------------------------------------
    # Calculate average and add to overall dictionary
    # -----------------------------------------------

    # -- Calculate each value
    out_dict_not_av = {0: {}, 1: {}}

    # Initialise out_dict_not_av
    for daytype in out_dict_not_av:
        month_dict = {}
        for f in range(12): # hours

            # Add all daily values into a list (not average)
            day_dict = {k: [] for k in range(24)}
            month_dict[f] = day_dict
        out_dict_not_av[daytype] = month_dict

    # copy values from main_dict
    for daytype in main_dict:
        for month_python in main_dict[daytype]:
            for h_day in main_dict[daytype][month_python]:
                out_dict_not_av[daytype][month_python][h_day] = main_dict[daytype][month_python][h_day]

    # -- Average (initialise dict)
    out_dict_av = {0: {}, 1: {}}
    for dtype in out_dict_av:
        month_dict = {}
        for month in range(12):
            month_dict[month] = {k: 0 for k in range(24)}
        out_dict_av[dtype] = month_dict

    # Iterate daytype
    for daytype in main_dict:

        # Iterate month
        for _month in main_dict[daytype]:

            # Iterate hour
            for _hr in main_dict[daytype][_month]:
                nr_of_entries = len(main_dict[daytype][_month][_hr]) # nr of added entries

                if nr_of_entries != 0: # Because may not contain data because not available in the csv files
                    out_dict_av[daytype][_month][_hr] = sum(main_dict[daytype][_month][_hr]) / nr_of_entries

    # Test to for summing
    for daytype in out_dict_av:
        for month in out_dict_av[daytype]:
            test_sum = sum(map(abs, out_dict_av[daytype][month].values())) # Sum absolute values
            assertions = unittest.TestCase('__init__')
            assertions.assertAlmostEqual(test_sum, 100.0, places=2, msg=None, delta=None)

    return out_dict_av, out_dict_not_av

out_dict_average, out_dict_not_average = read_in_non_residential_load_curves()

# --------------------------------------------------------
# Calculate average daily load shape for all mongth (averaged)
# --------------------------------------------------------
# Initiate
yearly_averaged_load_curve = {0: {}, 1: {}}
for daytype in yearly_averaged_load_curve:
    yearly_averaged_load_curve[daytype] = {k: 0 for k in range(24)}

for daytype in out_dict_average:

    # iterate month
    for hour in range(24):
        h_average_y = 0

        # Get every hour of all months
        for month in range(12):
            h_average_y += out_dict_average[daytype][month][hour]

        h_average_y = h_average_y / 12
        yearly_averaged_load_curve[daytype][hour] = h_average_y

print("Result yearly averaged:")
print(yearly_averaged_load_curve)



# -------------------
# plot
# -------------------
plot_average = True


x_values = range(24)

#-- plot yearly average
print("Yearly Average over all measurements")
for daytype in yearly_averaged_load_curve:

    # y-values
    y_values = list(yearly_averaged_load_curve[daytype].values())
    print("y_values")
    print(y_values)
    plt.plot(x_values, y_values, label = 'daytype %s'%daytype)

plt.xlabel("hours")
plt.ylabel("percentage of daily demand")
plt.title("Plotting all month for the daytype {}".format(daytype))
plt.legend()
plt.show()


# --- if average is calculated
if plot_average == True:

    # plot all month
    for month in range(12):

        # y-values
        y_values = list(out_dict_average[daytype][month].values())
        plt.plot(x_values, y_values, label = 'Month %s'%month)

    plt.xlabel("hours")
    plt.ylabel("percentage of daily demand")
    plt.title("Plotting all month for the daytype {}".format(daytype))
    plt.legend()
    plt.show()


# --- if individual days are plotted
if plot_average == False:

    month = 3
    daytype = 1 # Daytaoe

    # y-values
    y_values = list(out_dict_not_average[daytype][month].values()) #) # daytype = 0, January = 0

    plt.plot(x_values, y_values)
    plt.xlabel("hours")
    plt.ylabel("percentage of daily demand")
    plt.title("Plotting the Month of {} for the daytype {}".format(month, daytype))
    plt.show()

print("Finished loead profiles generator")