'''
Energy Demand Model
=================

Contains all calculation steps necessary to run the
energy demand module.

The model has been developped within the MISTRAL
project. A previous model has been developped within
NISMOD by Pranab et al..(MOREINFO) HIRE develops this model
further into a high temporal and spatial model.abs

Key contributers are:
    - Sven Eggimann
    - Nick Eyre
    -

    note,tip,warning,

More information can be found here:

    - Eggimann et al. (2018): Paper blablabla

build, git, docs, .eggs, .coverage, .cache, hire, scripts, data

pip install autopep8
autopep8 -i myfile.py # <- the -i flag makes the changes "in-place"
import time   fdf
#logging.debug("..TIME A: {}".format(time.time() - start))
TODO: Make end year more explicit with yearliy number
TODO: REMOVE HEAT BOILER
    Quetsiosn for Tom
    ----------------
    - Cluster?
    - scripts in ed?
    - path rel/abs
    - nested scripts

Todo: Clan in data / data_scripts and data / model_output
'''
import os
import sys
import logging
import numpy as np
from pyinstrument import Profiler
import energy_demand.energy_model as energy_model
from energy_demand.assumptions import assumptions
from energy_demand.read_write import data_loader
from energy_demand.read_write import write_data
from energy_demand.read_write import read_data
from energy_demand.dwelling_stock import dw_stock
from energy_demand.basic import testing_functions as testing
from energy_demand.basic import date_handling
from energy_demand.validation import lad_validation
from energy_demand.validation import elec_national_data
from energy_demand.plotting import plotting_results
from energy_demand.basic import logger_setup as log
#!python3.6

def energy_demand_model(data):
    """Main function of energy demand model to calculate yearly demand

    Arguments
    ----------
    data : dict
        Data container

    Returns
    -------
    result_dict : dict
        A nested dictionary containing all data for energy supply model with
        timesteps for every hour in a year.
        [fuel_type : region : timestep]
    model_run_object : dict
        Object of a yearly model run

    Note
    ----
    This function is executed in the wrapper
    """
    fuel_in, fuel_in_elec, _ = testing.test_function_fuel_sum(data)

    # Add all region instances as an attribute (region name) into the class `EnergyModel`
    model_run_object = energy_model.EnergyModel(
        region_names=data['lu_reg'],
        data=data,
    )

    # Total fuel of country
    fueltot = model_run_object.sum_uk_fueltypes_enduses_y

    # Fuel per region
    logging.info("================================================")
    logging.info("Simulation year:     " + str(model_run_object.curr_yr))
    logging.info("Number of regions    " + str(len(data['lu_reg'])))
    logging.info("Fuel input:          " + str(fuel_in))
    logging.info("Fuel output:         " + str(fueltot))
    logging.info("FUEL DIFFERENCE:     " + str(round((fueltot - fuel_in), 4)))
    logging.info("elec fuel in:        " + str(fuel_in_elec))
    logging.info("elec fuel out:       " + str(np.sum(model_run_object.all_submodels_sum_uk_specfuelype_enduses_y[2])))
    logging.info("ele fueld diff:      " + str(round(fuel_in_elec - np.sum(model_run_object.all_submodels_sum_uk_specfuelype_enduses_y[2]), 4))) #ithout transport
    logging.info("================================================")
    for fff in range(8):
        logging.debug("FF: " + str(np.sum(model_run_object.all_submodels_sum_uk_specfuelype_enduses_y[fff])))

    logging.debug("...finished energy demand model simulation")
    return _, model_run_object

if __name__ == "__main__":
    """
    """

    instrument_profiler = True

    # Paths
    path_main = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    local_data_path = os.path.join('Y:\Data_NISMOD', 'data_energy_demand')

    # Initialise logger
    log.set_up_logger(os.path.join(local_data_path, "logging_energy_demand.log"))
    logging.info("... start local energy demand calculations")
    logging.info(" ")

    # Load data
    data = {}
    data['paths'] = data_loader.load_paths(path_main)
    data['local_paths'] = data_loader.load_local_paths(local_data_path)
    data['lookups'] = data_loader.load_basic_lookups()
    data['fuels'] = data_loader.load_fuels(data)
    data['tech_load_profiles'] = data_loader.load_data_profiles(data['paths'], data['local_paths'])
    data['sim_param'], data['assumptions'] = assumptions.load_assumptions(data, False)
    data['assumptions'] = assumptions.update_assumptions(data['assumptions'])
    data['weather_stations'], data['temperature_data'] = data_loader.load_data_temperatures(data['local_paths'])
    data = data_loader.dummy_data_generation(data)



    logging.info("Start Energy Demand Model with python version: " + str(sys.version))
    logging.info("Info model run")
    logging.info("--------------")
    logging.info("main path {}".format(path_main))
    print("--------")
    # Load data from script calculations
    data = read_data.load_script_data(data)

    # Generate dwelling stocks over whole simulation period
    data['rs_dw_stock'] = dw_stock.rs_dw_stock(data['lu_reg'], data)
    data['ss_dw_stock'] = dw_stock.ss_dw_stock(data['lu_reg'], data)

    results_every_year = []
    for sim_yr in data['sim_param']['sim_period']:
        data['sim_param']['curr_yr'] = sim_yr

        logging.debug("-------------------------- ")
        logging.debug("SIM RUN:  " + str(sim_yr))
        logging.debug("-------------------------- ")

        #-------------PROFILER
        if instrument_profiler:
            profiler = Profiler(use_signal=False)
            profiler.start()

        _, model_run_object = energy_demand_model(data)

        if instrument_profiler:
            profiler.stop()
            logging.debug("Profiler Results")
            print(profiler.output_text(unicode=True, color=True))

        results_every_year.append(model_run_object)

        # FUEL PER REGION SCRAP
        out_to_supply = model_run_object.fuel_individual_regions

        # ---------------------------------------------------
        # Validation of national electrictiy demand for base year
        # ---------------------------------------------------
        winter_week = list(range(date_handling.convert_date_to_yearday(2015, 1, 12), date_handling.convert_date_to_yearday(2015, 1, 19))) #Jan
        spring_week = list(range(date_handling.convert_date_to_yearday(2015, 5, 11), date_handling.convert_date_to_yearday(2015, 5, 18))) #May
        summer_week = list(range(date_handling.convert_date_to_yearday(2015, 7, 13), date_handling.convert_date_to_yearday(2015, 7, 20))) #Jul
        #spring_week = list(range(date_handling.convert_date_to_yearday(2015, 5, 18), date_handling.convert_date_to_yearday(2015, 5, 26))) #May
        #summer_week = list(range(date_handling.convert_date_to_yearday(2015, 7, 20), date_handling.convert_date_to_yearday(2015, 7, 28))) #Jul
        autumn_week = list(range(date_handling.convert_date_to_yearday(2015, 10, 12), date_handling.convert_date_to_yearday(2015, 10, 19))) #Oct

        days_to_plot = winter_week + spring_week + summer_week + autumn_week
        days_to_plot_full_year = list(range(0, 365))

        # ---------------------------------------------------------------------------------------------
        # Compare total gas and electrictiy shape with Elexon Data for Base year for different regions
        # ---------------------------------------------------------------------------------------------
        validation_elec_data_2015_INDO, validation_elec_data_2015_ITSDO = elec_national_data.read_raw_elec_2015_data(
            data['local_paths']['folder_validation_national_elec_data'])

        logging.debug("Loaded validation data elec demand. ND:  {}   TSD: {}".format(np.sum(validation_elec_data_2015_INDO), np.sum(validation_elec_data_2015_ITSDO)))
        logging.debug("--ECUK Elec_demand  {} ".format(np.sum(model_run_object.all_submodels_sum_uk_specfuelype_enduses_y[2])))
        logging.debug("--ECUK Gas Demand   {} ".format(np.sum(model_run_object.all_submodels_sum_uk_specfuelype_enduses_y[1])))
        diff_factor_TD_ECUK_Input = (1.0 / np.sum(validation_elec_data_2015_INDO)) * np.sum(model_run_object.all_submodels_sum_uk_specfuelype_enduses_y[2]) # 1.021627962194478
        logging.debug("FACTOR: " + str(diff_factor_TD_ECUK_Input))

        INDO_factoreddata = diff_factor_TD_ECUK_Input * validation_elec_data_2015_INDO
        logging.debug("CORRECTED DEMAND:  {} ".format(np.sum(INDO_factoreddata)))

        #GET SPECIFIC REGION

        # Compare different models
        elec_national_data.compare_results('plot_figure_01.pdf', data, validation_elec_data_2015_INDO, validation_elec_data_2015_ITSDO, INDO_factoreddata, model_run_object.all_submodels_sum_uk_specfuelype_enduses_y[2], 'all_submodels', days_to_plot_full_year)
        #elec_national_data.compare_results('plot_figure_01.pdf', data, validation_elec_data_2015_INDO, validation_elec_data_2015_ITSDO, INDO_factoreddata, model_run_object.all_submodels_sum_uk_specfuelype_enduses_y[2], 'all_submodels', days_to_plot)
        #elec_national_data.compare_results('plot_figure_01.pdf', data, validation_elec_data_2015_INDO, validation_elec_data_2015_ITSDO, INDO_factoreddata, model_run_object.rs_sum_uk_specfuelype_enduses_y[2], 'rs_model', days_to_plot)
        #elec_national_data.compare_results('plot_figure_01.pdf', data, validation_elec_data_2015_INDO, validation_elec_data_2015_ITSDO, INDO_factoreddata, model_run_object.ss_sum_uk_specfuelype_enduses_y[2], 'ss_model', days_to_plot)
        #elec_national_data.compare_results('plot_figure_01.pdf', data, validation_elec_data_2015_INDO, validation_elec_data_2015_ITSDO, INDO_factoreddata, model_run_object.is_sum_uk_specfuelype_enduses_y[2], 'is_model', days_to_plot)
        #elec_national_data.compare_results('plot_figure_01.pdf', data, validation_elec_data_2015_INDO, validation_elec_data_2015_ITSDO, INDO_factoreddata, model_run_object.ts_sum_uk_specfuelype_enduses_y[2], 'ts_model', days_to_plot)

        logging.debug("FUEL gwh TOTAL  validation_elec_data_2015_INDO:  {} validation_elec_data_2015_ITSDO: {}  MODELLED DATA:  {} ".format(np.sum(validation_elec_data_2015_INDO), np.sum(validation_elec_data_2015_ITSDO), np.sum(model_run_object.all_submodels_sum_uk_specfuelype_enduses_y[2])))
        logging.debug("FUEL ktoe TOTAL  validation_elec_data_2015_INDO: {} validation_elec_data_2015_ITSDO: {}  MODELLED DATA:  {} ".format(np.sum(validation_elec_data_2015_INDO)/11.63, np.sum(validation_elec_data_2015_ITSDO)/11.63, np.sum(model_run_object.all_submodels_sum_uk_specfuelype_enduses_y[2])/11.63))

        # ---------------------------------------------------
        # Validation of spatial disaggregation
        # ---------------------------------------------------
        lad_infos_shapefile = data_loader.load_LAC_geocodes_info(
            data['local_paths']['path_dummy_regions']
        )
        lad_validation.compare_lad_regions(
            'compare_lad_regions.pdf',
            data,
            lad_infos_shapefile,
            model_run_object,
            data['lookups']['nr_of_fueltypes'],
            data['lookups']['fueltype'],
            data['lu_reg']
            )

        # ---------------------------------------------------
        # Validation of national electrictiy demand for peak
        # ---------------------------------------------------
        logging.debug("...compare peak from data")
        peak_month = 2 #Feb
        peak_day = 18 #Day
        elec_national_data.compare_peak(
            "peak_comparison_01.pdf",
            data,
            validation_elec_data_2015_INDO,
            model_run_object.all_submodels_sum_uk_specfuelype_enduses_y[peak_month][peak_day]
            )

        logging.debug("...compare peak from max peak factors")
        elec_national_data.compare_peak(
            "peak_comparison_02.pdf",
            data,
            validation_elec_data_2015_INDO,
            model_run_object.peak_all_models_all_enduses_fueltype[2])

        # ---------------------------------------------------
        # Validate boxplots for every hour
        # ---------------------------------------------------
        elec_national_data.compare_results_hour_boxplots(
            "hourly_boxplots_01.pdf",
            data,
            validation_elec_data_2015_INDO,
            model_run_object.all_submodels_sum_uk_specfuelype_enduses_y[2])

    # ------------------------------
    # Plotting
    # ------------------------------
    # Plot load factors
    ##pf.plot_load_curves_fueltype(results_every_year, data)

    # Plot total fuel (y) per enduse
    plotting_results.plot_stacked_Country_end_use("figure_stacked_country01.pdf", data, results_every_year, data['enduses']['rs_all_enduses'], 'rs_tot_fuel_y_enduse_specific_h')
    plotting_results.plot_stacked_Country_end_use("figure_stacked_country02.pdf", data, results_every_year, data['enduses']['ss_all_enduses'], 'ss_tot_fuel_enduse_specific_h')

    # Plot total fuel (y) per fueltype
    plotting_results.plot_fuels_tot_all_enduses("figure_tot_all_enduse01.pdf", results_every_year, data, 'rs_tot_fuels_all_enduses_y')
    plotting_results.plot_fuels_tot_all_enduses("figure_tot_all_enduse02.pdf", results_every_year, data, 'rs_tot_fuels_all_enduses_y')

    # Plot peak demand (h) per fueltype
    plotting_results.plot_fuels_peak_hour(results_every_year, data, 'rs_tot_fuel_y_max_allenduse_fueltyp')
    plotting_results.plot_fuels_peak_hour(results_every_year, data, 'ss_tot_fuel_y_max_allenduse_fueltyp')

    # Plot a full week
    plotting_results.plot_fuels_tot_all_enduses_week("figure_tot_all_enduse03.pdf", results_every_year, data, 'rs_tot_fuels_all_enduses_y')
    plotting_results.plot_fuels_tot_all_enduses_week("figure_tot_all_enduse04.pdf", results_every_year, data, 'rs_tot_fuels_all_enduses_y')

    # Plot all enduses
    plotting_results.plot_stacked_Country_end_use("figure_stacked_country_final.pdf", data, results_every_year, data['enduses']['rs_all_enduses'], 'all_models_tot_fuel_y_enduse_specific_h')

    logging.debug("... Finished running Energy Demand Model")
    print("... Finished running Energy Demand Model")
