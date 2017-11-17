"""This scripts reads the national electricity data for the base year"""
import os
import csv
import logging
import numpy as np
import matplotlib.pyplot as plt
from energy_demand.basic import date_prop
from energy_demand.basic import conversions
from energy_demand.plotting import plotting_program
from energy_demand.basic import basic_functions

def read_raw_elec_2015(path_to_csv, year=2015):
    """Read in national electricity values provided
    in MW and convert to GWh

    Arguments
    ---------
    path_to_csv : str
        Path to csv file
    year : int
        Year of data

    Returns
    -------
    elec_data_indo : array
        Hourly INDO electricity in GWh (INDO - National Demand)
    elec_data_itsdo : array
        Hourly ITSDO electricity in GWh (Transmission System Demand)

    Note
    -----
    Half hourly measurements are aggregated to hourly values

    Necessary data preparation: On 29 March and 25 Octobre
    there are 46 and 48 values because of the changing of the clocks
    The 25 Octobre value is omitted, the 29 March hour interpolated
    in the csv file

    Source
    ------
    http://www2.nationalgrid.com/uk/Industry-information/electricity-transmission-operational-data/
    For more information on INDO and ISTDO see DemandData Field Descriptions file:
    http://www2.nationalgrid.com/WorkArea/DownloadAsset.aspx?id=8589934632

    National Demand is calculated as a sum
    of generation based on National Grid
    operational generation metering
    """
    elec_data_indo = np.zeros((365, 24), dtype=float)
    elec_data_itsdo = np.zeros((365, 24), dtype=float)

    with open(path_to_csv, 'r') as csvfile:
        read_lines = csv.reader(csvfile, delimiter=',')
        _headings = next(read_lines)

        hour = 0
        counter_half_hour = 0

        for line in read_lines:
            month = basic_functions.get_month_from_string(line[0].split("-")[1])
            day = int(line[0].split("-")[0])

            # Get yearday
            yearday = date_prop.date_to_yearday(year, month, day)

            if counter_half_hour == 1:
                counter_half_hour = 0

                # Sum value of first and second half hour
                hour_elec_demand_INDO = half_hour_demand_indo + float(line[2])
                hour_elec_demand_ITSDO = half_hour_demand_itsdo + float(line[4]) 

                # Convert MW to GWH (input is MW aggregated for two half
                # hourly measurements, therfore divide by 0.5)
                elec_data_indo[yearday][hour] = conversions.mw_to_gwh(hour_elec_demand_INDO, 0.5)
                elec_data_itsdo[yearday][hour] = conversions.mw_to_gwh(hour_elec_demand_ITSDO, 0.5)

                hour += 1
            else:
                counter_half_hour += 1

                half_hour_demand_indo = float(line[2]) # INDO - National Demand
                half_hour_demand_itsdo = float(line[4]) # Transmission System Demand

            if hour == 24:
                hour = 0

    return elec_data_indo, elec_data_itsdo

def compare_results(
        name_fig,
        path_result,
        y_real_array_indo,
        y_real_array_itsdo,
        y_factored_indo,
        y_calculated_array,
        title_left,
        days_to_plot
    ):
    """Compare national electrictiy demand data with model results

    Note
    ----
    RMSE fit criteria : Lower values of RMSE indicate better fit
    https://stackoverflow.com/questions/17197492/root-mean-square-error-in-python

    https://matplotlib.org/examples/lines_bars_and_markers/marker_fillstyle_reference.html
    """
    logging.debug("...compare elec results")
    nr_of_h_to_plot = len(days_to_plot) * 24

    x_data = range(nr_of_h_to_plot)

    y_real_indo = []
    y_real_itsdo = []
    y_real_indo_factored = []
    y_calculated = []

    for day in days_to_plot:
        for hour in range(24):
            y_real_indo.append(y_real_array_indo[day][hour])
            y_real_itsdo.append(y_real_array_itsdo[day][hour])
            y_calculated.append(y_calculated_array[day][hour])
            y_real_indo_factored.append(y_factored_indo[day][hour])

    # RMSE
    rmse_val_indo = basic_functions.rmse(np.array(y_real_indo), np.array(y_calculated))
    rmse_val_itsdo = basic_functions.rmse(np.array(y_real_itsdo), np.array(y_calculated))
    rmse_val_corrected = basic_functions.rmse(np.array(y_real_indo_factored), np.array(y_calculated))
    #rmse_val_own_factor_correction = basic_functions.rmse(np.array(y_real_indo), np.array(y_calculated))

    # R squared
    #slope, intercept, r_value, p_value, std_err = stats.linregress(np.array(y_real_indo), np.array(y_calculated))

    # plot points
    plt.plot(x_data, y_real_indo, color='black', label='TD')
    plt.plot(x_data, y_real_itsdo, color='grey', label='TSD')
    plt.plot(x_data, y_real_indo_factored, color='green', label='TD_factored')
    plt.plot(x_data, y_calculated, color='red', label='modelled')
    #plt.plot(x_data, y_real_indo_factored, color='gray', fillstyle='full', markeredgewidth=0.5, marker='o', markersize=10, label='TD_factored')
    #plt.plot(x_data, y_calculated, color='white', fillstyle='none', markeredgewidth=0.5, marker='o', markersize=10, label='modelled')

    plt.xlim([0, 8760])
    plt.margins(x=0)
    plt.axis('tight')

    # ----------
    # Labelling
    # ----------
    font_additional_info = {'family': 'arial', 'color':  'black', 'weight': 'normal','size': 8}
    plt.title(
        'RMSE (TD): {} RMSE (TSD): {} RMSE (factored TSD): {}'.format(
            round(rmse_val_indo, 3), round(rmse_val_itsdo, 3), round(rmse_val_corrected)),
            fontsize=10,
            fontdict=font_additional_info,
            loc='right')

    plt.title(title_left, loc='left')

    plt.xlabel("hour", fontsize=10)
    plt.ylabel("uk electrictiy use [GW] for {}".format(title_left), fontsize=10)

    plt.legend(frameon=False)

    plt.savefig(os.path.join(path_result, name_fig))
    plt.close()

def compare_peak(
        name_fig,
        path_result,
        validation_elec_data_2015_peak,
        tot_peak_enduses_fueltype
    ):
    """Compare peak electricity day with calculated peak energy demand

    Arguments
    ---------
    name_fig :
    local_paths :
    validation_elec_data_2015_peak :
    tot_peak_enduses_fueltype :
    """
    logging.debug("...compare elec peak results")

    # -------------------------------
    # Compare values
    # -------------------------------
    fig = plt.figure(figsize=plotting_program.cm2inch(8, 8))

    plt.plot(range(24), tot_peak_enduses_fueltype, color='red', label='modelled')
    #plt.plot(range(24), validation_elec_data_2015[max_day], color='green', label='real')
    plt.plot(range(24), validation_elec_data_2015_peak, color='green', label='real')

    # Y-axis ticks
    plt.xlim(0, 25)
    plt.yticks(range(0, 90, 10))

    # Legend
    plt.legend()

    # Labelling
    plt.title("Peak day comparison", loc='left')
    plt.xlabel("hours")
    plt.ylabel("uk electrictiy use [GW]")

    # Tight layout
    plt.tight_layout()
    plt.margins(x=0)

    # Save fig
    plt.savefig(os.path.join(path_result, name_fig))
    plt.close()

def compare_results_hour_boxplots(
        name_fig,
        path_result,
        data_real,
        data_calculated
    ):
    """Calculate differences for every hour and plot according to hour
    for the full year
    """
    data_h_full_year = {}
    for i in range(24):
        data_h_full_year[i] = []

    for yearday_python in range(365):
        for hour in range(24):

            # Differenc in % of real value
            diff_percent = (100 / data_real[yearday_python][hour]) * data_calculated[yearday_python][hour]

            # Add differene to list of specific hour
            data_h_full_year[hour].append(diff_percent)

    fig = plt.figure()
    ax = fig.add_subplot(111)

    # Add a horizontal grid to the plot, but make it very light in color so we
    # can use it for reading data values but not be distracting
    ax.yaxis.grid(True, linestyle='-', which='major', color='lightgrey', alpha=0.5)
    ax.axhline(y=100, xmin=0, xmax=3, c="red", linewidth=1, zorder=0)

    diff_values = []
    for hour in range(24):
        diff_values.append(np.asarray(data_h_full_year[hour]))

    ax.boxplot(diff_values)

    plt.xticks(range(1, 25), range(24))
    #plt.margins(x=0) #remove white space

    plt.xlabel("hour")
    #plt.ylabel("Modelled electricity difference (real-modelled) [GWh / h]")
    plt.ylabel("Modelled electricity difference (real-modelled) [%]")

    plt.savefig(os.path.join(path_result, name_fig))
    #plt.show()
    plt.close()
