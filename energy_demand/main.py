'''Main file containing the energy demand model main function
#
# Description: Energy Demand Model - Run one year
# Authors: Sven Eggimann, ... Aurthors: Pranab Baruah; Scott Thacker
#
# Abbreviations:
# -------------
# rs = Residential Sector
# ss = service Sector
# ts = transportation Sector
#
# bd = Base demand
# by = Base year
# cy = Current year
# dw = dwelling
# p  = Percent
# e  = electricitiy
# g  = gas
# lu = look up
# h = hour
# hp = heat pump
# tech = technology
# temp = temperature
# d = day
# y = year
# yearday = Day in a year ranging from 0 to 364

# Shapes
# ------
# yd = for every year the day
# yh = for every hour in a year
# dh = every hour in day

# y = for total year
# y_dh = for every day in a year, the dh is provided

# -fitting scipy
# -speed with many regions

Down the line
- data centres (ICT about %, 3/4 end-use devices, network and data centres 1/4 NIC 2017)
- Heat recycling/reuse in percentage (lower heating demand accordingly)
- "scenario teller": istead of diffusion path, type in known path
- "storage heaters": Night, classical, New, daily...
TODO: Maybe take heat pump profiles from here instead of samson:
http://www.networkrevolution.co.uk/wp-content/uploads/2015/01/CLNR-L091-Insight-Report-Domestic-Heat-Pumps.pdf

The docs can be found here: http://ed.readthedocs.io
'''
# pylint: disable=I0011,C0321,C0301,C0103,C0325,no-member

#!python3.6
import os
import sys
import numpy as np
import energy_demand.energy_model as energy_model
from energy_demand.scripts_plotting import plotting_results
import energy_demand.building_stock_generator as bg
import energy_demand.assumptions as assumpt
import energy_demand.national_dissaggregation as nd
import energy_demand.data_loader as dl
from energy_demand.scripts_data import write_data
from energy_demand.scripts_technologies import diffusion_technologies as diffusion
from energy_demand.scripts_technologies import fuel_service_switch
from energy_demand.scripts_calculations import enduse_scenario
from energy_demand.scripts_data import read_data
from energy_demand.scripts_basic import testing_functions as testing
from energy_demand.scripts_validation import elec_national_data as validation
from energy_demand.scripts_basic import date_handling
print("Start Energy Demand Model with python version: " + str(sys.version))

def energy_demand_model(data):
    """Main function of energy demand model to calculate yearly demand

    This function is executed in the wrapper.

    Parameters
    ----------
    data : dict
        Contains all data not provided externally

    Returns
    -------
    result_dict : dict
        A nested dictionary containing all data for energy supply model with
        timesteps for every hour in a year.
        [fuel_type : region : timestep]
    """

    # -------------------------
    # Model main function
    # --------------------------
    fuel_in, fuel_in_elec, _ = testing.test_function_fuel_sum(data) #SCRAP_ TEST FUEL SUM

    # Add all region instances as an attribute (region name) into the class `EnergyModel`
    model_run_object = energy_model.EnergyModel(
        reg_names=data['lu_reg'],
        data=data,
    )

    # ----------------------------
    # Summing
    # ----------------------------
    fueltot = model_run_object.sum_uk_fueltypes_enduses_y # Total fuel of country

    #fueltot_specific_fueltype = model_run_object.sum_uk_specfuelype_enduses_y[2] #Elec
    print("================================================")
    print(np.sum(model_run_object.ts_sum_uk_specfuelype_enduses_y))
    print(np.sum(model_run_object.ts_sum_uk_specfuelype_enduses_y[2]))
    print("Fuel input:          " + str(fuel_in))
    print("Fuel output:         " + str(fueltot))
    print("FUEL DIFFERENCE:     " + str(round((fueltot - fuel_in), 4)))
    print("elec fuel in:        " + str(fuel_in_elec))
    print("elec fuel out:       " + str(np.sum(model_run_object.all_submodels_sum_uk_specfuelype_enduses_y[2])))
    print("ele fueld diff:      " + str(round(fuel_in_elec - np.sum(model_run_object.all_submodels_sum_uk_specfuelype_enduses_y[2]), 4))) #ithout transport
    print("================================================")

    # Convert data according to region and fueltype
    result_dict = read_data.convert_out_format_es(data, model_run_object, ['ss_submodel', 'rs_submodel'])

    # --- Write to csv and YAML
    #write_data.write_final_result(data, result_dict, model_run_object.curr_yr, data['lu_reg'], False)

    # -----------------------------------------
    # VALIDATE ELEC WITH NATIONAL ELEC DEMAND
    # -----------------------------------------
    # Read in 2015 base elec national data
    print("FINAL Fueltype:  " + str(len(result_dict)))
    print("FINAL timesteps*regions: " + str(len(result_dict['electricity'])))
    print("Finished energy demand model")
    return result_dict, model_run_object

# Run
if __name__ == "__main__":
    # ------------------------------------------------------------------
    # Execute only once before executing energy demand module for a year
    # ------------------------------------------------------------------
    # obs.value == 3000000
    # obs.region == 1
    # obs.interval == 2
    # obs.units == 'count'
    # External data provided from wrapper


    # DUMMY DATA GENERATION----------------------

    base_yr = 2015
    end_yr = 2020 #includes this year
    sim_years = range(base_yr, end_yr + 1)

    # dummy coordinates
    coord_dummy = {}
    coord_dummy['Wales'] = {'longitude': 52.289288, 'latitude': -3.610933}
    coord_dummy['Scotland'] = {'longitude': 56.483100, 'latitude': -4.027093}
    coord_dummy['England'] = {'longitude': 52.874205, 'latitude': -0.871205}

    pop_dummy = {}


    # Dummy service floor area
    # Newcastle: TODO REPLAE IF AVAILABLE.
    all_sectors = ['community_arts_leisure', 'education', 'emergency_services', 'health', 'hospitality', 'military', 'offices', 'retail', 'storage', 'other']
    ss_floorarea_sector_by_dummy = {}

    ss_floorarea_sector_by_dummy['Wales'] = {}
    ss_floorarea_sector_by_dummy['Scotland'] = {}
    ss_floorarea_sector_by_dummy['England'] = {}
    for sector in all_sectors:
        ss_floorarea_sector_by_dummy['Wales'][sector] = 10000 #[m2]
        #ss_floorarea_sector_by_dummy['Scotland'][sector] = 10000 #[m2]
        #ss_floorarea_sector_by_dummy['England'][sector] = 10000 #[m2]


    #a = a = 'Wales': 3000000, 'Scotland': 5300000, 'BERN': 5300000}
    a = {'Wales': 500000} #, 'Scotland': 500000, 'England': 500000}
    for i in sim_years:
        y_data = {}
        for reg in a:
            y_data[reg] = a[reg] # + (a[reg] * 1.04)
        pop_dummy[i] = y_data

    fuel_price_dummy = {}
    a = {0: 10.0, 1: 10.0, 2: 10.0, 3: 1.0, 4: 1.0, 5: 1.0, 6: 1.0, 7: 1.0}
    for i in sim_years:
        y_data = {}
        for reg in a:
            y_data[reg] = a[reg] + 0.3
        fuel_price_dummy[i] = y_data
        a = y_data
    # DUMMY DATA GENERATION----------------------


    # Reg Floor Area? Reg lookup?
    data_external = {
        'population': pop_dummy,
        'reg_coordinates': coord_dummy,
        'glob_var' : {},
        'fuel_price': fuel_price_dummy,
        'ss_sector_floor_area_by': ss_floorarea_sector_by_dummy,

        # Demand of other sectors
        'external_enduses_resid': {
            #'waste_water': {0: 0},  # Yearly fuel data
            #'ICT_model': {}
        }
    }
    data_external['end_yr'] = end_yr
    data_external['sim_period'] = range(base_yr, end_yr + 1, 1) # Alywas including last simulation year
    data_external['base_yr'] = base_yr

    data_external['fastcalculationcrit'] = True
    # ------------------- DUMMY END


    # ----------------------------------------
    # Model calculations outside main function
    # ----------------------------------------
    print("... start model calculations outside main function")
    base_data = {}

    # Copy external data into data container
    for dataset_name, external_data in data_external.items():
        base_data[str(dataset_name)] = external_data

    # Paths
    path_main = os.path.join(os.path.dirname(__file__), '..', 'data')

    # Path to local files which have restricted access
    base_data['local_data_path'] = r'Y:\01-Data_NISMOD\data_energy_demand'

    # Load data
    base_data = dl.load_data(path_main, base_data)
    print("... load assumptions")

    # Load assumptions
    base_data['assumptions'] = assumpt.load_assumptions(base_data)

    # Change temperature data according to simple assumptions about climate change
    base_data['temperature_data'] = enduse_scenario.change_temp_data_climate_change(base_data)

    # RESIDENTIAL: Convert base year fuel input assumptions to energy service
    base_data['assumptions']['rs_service_tech_by_p'], base_data['assumptions']['rs_service_fueltype_tech_by_p'], base_data['assumptions']['rs_service_fueltype_by_p'] = fuel_service_switch.get_service_fueltype_tech(
        base_data['assumptions'],
        base_data['lu_fueltype'],
        base_data['assumptions']['rs_fuel_enduse_tech_p_by'],
        base_data['rs_fuel_raw_data_enduses'], #Fuel of whole country
        base_data['assumptions']['technologies']
        )

    # SERVICE: Convert base year fuel input assumptions to energy service
    fuels_aggregated_across_sectors = fuel_service_switch.ss_summarise_fuel_enduse_sectors(base_data['ss_fuel_raw_data_enduses'], base_data['ss_all_enduses'], base_data['nr_of_fueltypes'])
    base_data['assumptions']['ss_service_tech_by_p'], base_data['assumptions']['ss_service_fueltype_tech_by_p'], base_data['assumptions']['ss_service_fueltype_by_p'] = fuel_service_switch.get_service_fueltype_tech(
        base_data['assumptions'],
        base_data['lu_fueltype'],
        base_data['assumptions']['ss_fuel_enduse_tech_p_by'],
        fuels_aggregated_across_sectors,
        base_data['assumptions']['technologies']
        )

    # INDUSTRY
    fuels_aggregated_across_sectors = fuel_service_switch.ss_summarise_fuel_enduse_sectors(base_data['is_fuel_raw_data_enduses'], base_data['is_all_enduses'], base_data['nr_of_fueltypes'])
    base_data['assumptions']['is_service_tech_by_p'], base_data['assumptions']['is_service_fueltype_tech_by_p'], base_data['assumptions']['is_service_fueltype_by_p'] = fuel_service_switch.get_service_fueltype_tech(
        base_data['assumptions'],
        base_data['lu_fueltype'],
        base_data['assumptions']['is_fuel_enduse_tech_p_by'],
        fuels_aggregated_across_sectors,
        base_data['assumptions']['technologies']
        )

    # Write out txt file with service shares for each technology per enduse
    write_data.write_out_txt(base_data['path_dict']['path_txt_service_tech_by_p'], base_data['assumptions']['rs_service_tech_by_p'])
    print("... a file has been generated which shows the shares of each technology per enduse")

    # Calculate technologies with more, less and constant service based on service switch assumptions
    base_data['assumptions']['rs_tech_increased_service'], base_data['assumptions']['rs_tech_decreased_share'], base_data['assumptions']['rs_tech_constant_share'] = fuel_service_switch.get_technology_services_scenario(base_data['assumptions']['rs_service_tech_by_p'], base_data['assumptions']['rs_share_service_tech_ey_p'])
    base_data['assumptions']['ss_tech_increased_service'], base_data['assumptions']['ss_tech_decreased_share'], base_data['assumptions']['ss_tech_constant_share'] = fuel_service_switch.get_technology_services_scenario(base_data['assumptions']['ss_service_tech_by_p'], base_data['assumptions']['ss_share_service_tech_ey_p'])
    base_data['assumptions']['is_tech_increased_service'], base_data['assumptions']['is_tech_decreased_share'], base_data['assumptions']['is_tech_constant_share'] = fuel_service_switch.get_technology_services_scenario(base_data['assumptions']['is_service_tech_by_p'], base_data['assumptions']['is_share_service_tech_ey_p'])

    # Calculate sigmoid diffusion curves based on assumptions about fuel switches

    # --Residential
    base_data['assumptions']['rs_installed_tech'], base_data['assumptions']['rs_sig_param_tech'] = diffusion.get_sig_diffusion(
        base_data,
        base_data['assumptions']['rs_service_switches'],
        base_data['assumptions']['rs_fuel_switches'],
        base_data['rs_all_enduses'],
        base_data['assumptions']['rs_tech_increased_service'],
        base_data['assumptions']['rs_share_service_tech_ey_p'],
        base_data['assumptions']['rs_enduse_tech_maxL_by_p'],
        base_data['assumptions']['rs_service_fueltype_by_p'],
        base_data['assumptions']['rs_service_tech_by_p'],
        base_data['assumptions']['rs_fuel_enduse_tech_p_by']
        )

    # --Service
    base_data['assumptions']['ss_installed_tech'], base_data['assumptions']['ss_sig_param_tech'] = diffusion.get_sig_diffusion(
        base_data,
        base_data['assumptions']['ss_service_switches'],
        base_data['assumptions']['ss_fuel_switches'],
        base_data['ss_all_enduses'],
        base_data['assumptions']['ss_tech_increased_service'],
        base_data['assumptions']['ss_share_service_tech_ey_p'],
        base_data['assumptions']['ss_enduse_tech_maxL_by_p'],
        base_data['assumptions']['ss_service_fueltype_by_p'],
        base_data['assumptions']['ss_service_tech_by_p'],
        base_data['assumptions']['ss_fuel_enduse_tech_p_by']
        )

    # --Industry
    base_data['assumptions']['is_installed_tech'], base_data['assumptions']['is_sig_param_tech'] = diffusion.get_sig_diffusion(
        base_data,
        base_data['assumptions']['is_service_switches'],
        base_data['assumptions']['is_fuel_switches'],
        base_data['is_all_enduses'],
        base_data['assumptions']['is_tech_increased_service'],
        base_data['assumptions']['is_share_service_tech_ey_p'],
        base_data['assumptions']['is_enduse_tech_maxL_by_p'],
        base_data['assumptions']['is_service_fueltype_by_p'],
        base_data['assumptions']['is_service_tech_by_p'],
        base_data['assumptions']['is_fuel_enduse_tech_p_by']
        )
    # ---------------------------------------------
    # Disaggregate national data into regional data
    # ---------------------------------------------
    base_data = nd.disaggregate_base_demand(base_data)

    # Generate building stocks over whole simulation period
    print("...created dwelling stocks for service and residential model")
    base_data['rs_dw_stock'] = bg.rs_build_stock(base_data)
    base_data['ss_dw_stock'] = bg.ss_build_stock(base_data)

    # If several years are run:
    results_every_year = []

    for sim_yr in sim_years:
        base_data['curr_yr'] = sim_yr

        print("-------------------------- ")
        print("SIM RUN:  " + str(sim_yr))
        print("-------------------------- ")
        results, model_run_object = energy_demand_model(base_data)

        results_every_year.append(model_run_object)


        # ---------------------------------------------------
        # Validation of national electrictiy demand for base year
        # ---------------------------------------------------
        winter_week = list(range(date_handling.convert_date_to_yearday(2015, 1, 12), date_handling.convert_date_to_yearday(2015, 1, 19))) #Jan
        spring_week = list(range(date_handling.convert_date_to_yearday(2015, 5, 11), date_handling.convert_date_to_yearday(2015, 5, 18))) #May
        summer_week = list(range(date_handling.convert_date_to_yearday(2015, 7, 13), date_handling.convert_date_to_yearday(2015, 7, 20))) #Jul
        autumn_week = list(range(date_handling.convert_date_to_yearday(2015, 10, 12), date_handling.convert_date_to_yearday(2015, 10, 19))) #Oct

        days_to_plot = winter_week + spring_week + summer_week + autumn_week
        days_to_plot_full_year = list(range(0, 365))

        # Compare total gas and electrictiy shape with Elexon Data for Base year for different regions
        validation_elec_data_2015_INDO, validation_elec_data_2015_ITSDO = validation.read_raw_elec_2015_data(base_data['path_dict']['folder_validation_national_elec_data'])

        print("Loaded validation data elec demand. ND:  {}   TSD: {}".format(np.sum(validation_elec_data_2015_INDO), np.sum(validation_elec_data_2015_ITSDO)))
        print("ECUK Elec_demand  {} ".format(np.sum(model_run_object.all_submodels_sum_uk_specfuelype_enduses_y[2])))

        diff_factor_TD_ECUK_Input = (1.0/np.sum(validation_elec_data_2015_INDO)) * np.sum(model_run_object.all_submodels_sum_uk_specfuelype_enduses_y[2]) # 1.021627962194478
        print("FACTOR: " + str(diff_factor_TD_ECUK_Input))

        INDO_factoreddata = diff_factor_TD_ECUK_Input * validation_elec_data_2015_INDO

        print("CORRECTED DEMAND:  {} ".format(np.sum(INDO_factoreddata)))

        # Compare different models
        validation.compare_results(validation_elec_data_2015_INDO, validation_elec_data_2015_ITSDO, INDO_factoreddata, model_run_object.all_submodels_sum_uk_specfuelype_enduses_y[2], 'all_submodels', days_to_plot_full_year)
        validation.compare_results(validation_elec_data_2015_INDO, validation_elec_data_2015_ITSDO, INDO_factoreddata, model_run_object.all_submodels_sum_uk_specfuelype_enduses_y[2], 'all_submodels', days_to_plot)
        validation.compare_results(validation_elec_data_2015_INDO, validation_elec_data_2015_ITSDO, INDO_factoreddata, model_run_object.all_submodels_sum_uk_specfuelype_enduses_y[2], 'all_submodels', days_to_plot)
        #validation.compare_results(validation_elec_data_2015, model_run_object.rs_sum_uk_specfuelype_enduses_y[2], 'rs_model', days_to_plot)
        #validation.compare_results(validation_elec_data_2015, model_run_object.ss_sum_uk_specfuelype_enduses_y[2], 'ss_model', days_to_plot)
        #validation.compare_results(validation_elec_data_2015, model_run_object.is_sum_uk_specfuelype_enduses_y[2], 'is_model', days_to_plot)
        #validation.compare_results(validation_elec_data_2015, model_run_object.ts_sum_uk_specfuelype_enduses_y[2], 'ts_model', days_to_plot)

        print("FUEL gwh TOTAL  validation_elec_data_2015_INDO:  {} validation_elec_data_2015_ITSDO: {}  MODELLED DATA:  {} ".format(np.sum(validation_elec_data_2015_INDO), np.sum(validation_elec_data_2015_ITSDO), np.sum(model_run_object.all_submodels_sum_uk_specfuelype_enduses_y[2])))
        print("FUEL ktoe TOTAL  validation_elec_data_2015_INDO: {} validation_elec_data_2015_ITSDO: {}  MODELLED DATA:  {} ".format(np.sum(validation_elec_data_2015_INDO)/11.63, np.sum(validation_elec_data_2015_ITSDO)/11.63, np.sum(model_run_object.all_submodels_sum_uk_specfuelype_enduses_y[2])/11.63))

        # ---------------------------------------------------
        # Validation of national electrictiy demand for peak
        # ---------------------------------------------------
        validation.compare_peak(validation_elec_data_2015_INDO, model_run_object.all_submodels_sum_uk_specfuelype_enduses_y[2][18]) #SCRAP: NOT PEAK BUT PEAK DAY
        validation.compare_peak(validation_elec_data_2015_INDO, model_run_object.peak_all_models_all_enduses_fueltype[2]) #for electricity only

        # ---------------------------------------------------
        # Validate boxplots for every hour
        # ---------------------------------------------------
        validation.compare_results_hour_boxplots(validation_elec_data_2015_INDO, model_run_object.all_submodels_sum_uk_specfuelype_enduses_y[2])

    # ------------------------------
    # Plotting
    # ------------------------------
    # Plot load factors
    ##pf.plot_load_curves_fueltype(results_every_year, base_data)



    # Plot total fuel (y) per enduse
    plotting_results.plot_stacked_Country_end_use(base_data, results_every_year, base_data['rs_all_enduses'], 'rs_tot_fuel_y_enduse_specific_h')
    plotting_results.plot_stacked_Country_end_use(base_data, results_every_year, base_data['ss_all_enduses'], 'ss_tot_fuel_enduse_specific_h')

    # Plot total fuel (y) per fueltype
    plotting_results.plot_fuels_tot_all_enduses(results_every_year, base_data, 'rs_tot_fuels_all_enduses_y')
    plotting_results.plot_fuels_tot_all_enduses(results_every_year, base_data, 'rs_tot_fuels_all_enduses_y')

    # Plot peak demand (h) per fueltype
    plotting_results.plot_fuels_peak_hour(results_every_year, base_data, 'rs_tot_fuel_y_max_allenduse_fueltyp')
    plotting_results.plot_fuels_peak_hour(results_every_year, base_data, 'ss_tot_fuel_y_max_allenduse_fueltyp')

    # Plot a full week
    plotting_results.plot_fuels_tot_all_enduses_week(results_every_year, base_data, 'rs_tot_fuels_all_enduses_y')
    plotting_results.plot_fuels_tot_all_enduses_week(results_every_year, base_data, 'rs_tot_fuels_all_enduses_y')

    # Plot all enduses
    plotting_results.plot_stacked_Country_end_use(base_data, results_every_year, base_data['rs_all_enduses'], 'all_models_tot_fuel_y_enduse_specific_h')

    print("Finished running Energy Demand Model")

    #-----------
    # Profiler
    #-----------
    """
    import cProfile
    import pstats
    cProfile.run('energy_demand_model(base_data)')

    stats = pstats.Stats('c://Users//cenv0553//GIT//data//model_output//rs_service_tech_by_p.txt')
    #base_data['path_dict']['path_out_stats_cProfile']

    stats.strip_dirs()
    stats.sort_stats(-1)
    stats.print_stats()

    # -------------
    # PyCallGraph
    # -------------

    from pycallgraph import PyCallGraph
    from pycallgraph.output import GraphvizOutput

    print("Run profiler....")
    #with PyCallGraph(output=GraphvizOutput()):

    graphviz = GraphvizOutput()
    graphviz.output_file = r'C:\\Users\\cenv0553\\GIT\\data\\model_output\\basic.png'

    with PyCallGraph(output=graphviz):
        energy_demand_model(base_data)
    """
