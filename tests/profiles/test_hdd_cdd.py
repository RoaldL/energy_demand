"""testing
"""
from energy_demand.profiles import hdd_cdd
import numpy as np

def test_calc_hdd():
    """testing
    """
    t_base = 15 #degree
    temp_yh = np.zeros((365, 24))
    
    for day in range(365):
        for hour in range(24):
            temp_yh[day][hour] = np.random.randint(-4, 30)

    result = hdd_cdd.calc_hdd(t_base, temp_yh)

    temp_yh[temp_yh > t_base] = t_base

    expected = np.sum(t_base - temp_yh) / 24

    # positive values
    assert round(np.sum(result), 3) == round(expected, 3)

def test_calc_cdd():
    """testing
    """
    t_base = 15 #degree
    temp_yh = np.zeros((365, 24))

    for day in range(365):
        for hour in range(24):
            temp_yh[day][hour] = np.random.randint(-4, 30)

    result = hdd_cdd.calc_cdd(t_base, temp_yh)

    temp_yh[temp_yh < t_base] = t_base

    expected = np.sum(temp_yh -t_base) / 24

    # positive values
    assert round(np.sum(result), 3) == round(expected, 3)

def test_sigm_temp():
    """
    """
    assumptions = {}
    assumptions['smart_meter_diff_params'] = {}
    assumptions['smart_meter_diff_params']['sig_midpoint'] = 0
    assumptions['smart_meter_diff_params']['sig_steeppness'] = 1

    end_yr_t_base = 13
    assumptions['rs_t_base_heating'] = {}
    assumptions['rs_t_base_heating']['base_yr'] = 15
    assumptions['rs_t_base_heating']['end_yr'] = end_yr_t_base

    base_sim_param = {
        'base_yr': 2015,
        'curr_yr': 2020,
        'end_yr': 2020}

    result = hdd_cdd.sigm_temp(base_sim_param, assumptions['smart_meter_diff_params'], assumptions['rs_t_base_heating'])

    expected = end_yr_t_base
    assert result == expected

def test_get_hdd_country():
    """testing
    """
    base_sim_param = {
        'base_yr': 2015,
        'curr_yr': 2020,
        'end_yr': 2020}

    weather_stations = {
        "weater_station_A": {
            'station_latitude': 55.8695,
            'station_longitude': -4.4}}

    regions = ['reg_A', 'reg_B']

    temp_data = {
        "weater_station_A": np.zeros((365, 24)) + 12}

    smart_meter_diff_params = {}
    smart_meter_diff_params['sig_midpoint'] = 0
    smart_meter_diff_params['sig_steeppness'] = 1
    
    reg_coord = {
        "reg_A": {
            'latitude': 59.02999742,
            'longitude': -3.4},
        "reg_B": {
            'latitude': 57.02999742,
            'longitude': -4.4}}
    
    t_base_heating = {
        'base_yr': 15.5,
        'end_yr': 15.5}

    result = hdd_cdd.get_hdd_country(
        base_sim_param,
        regions,
        temp_data,
        smart_meter_diff_params,
        t_base_heating,
        reg_coord,
        weather_stations)
    
    expected = {
        "reg_A": (15.5 - 12.0) * 8760 / 24,
        "reg_B": (15.5 - 12.0) * 8760 / 24}

    assert result['reg_A'] == expected['reg_A']
    assert result['reg_B'] == expected['reg_B']

def test_get_cdd_country():
    """testing
    """
    base_sim_param = {
        'base_yr': 2015,
        'curr_yr': 2020,
        'end_yr': 2020}

    weather_stations = {
        "weater_station_A": {
            'station_latitude': 55.8695,
            'station_longitude': -4.4}}

    regions = ['reg_A', 'reg_B']

    temp_data = {
        "weater_station_A": np.zeros((365, 24)) + 20}

    smart_meter_diff_params = {}
    smart_meter_diff_params['sig_midpoint'] = 0
    smart_meter_diff_params['sig_steeppness'] = 1
    
    reg_coord = {
        "reg_A": {
            'latitude': 59.02999742,
            'longitude': -3.4},
        "reg_B": {
            'latitude': 57.02999742,
            'longitude': -4.4}}
    
    t_base_heating = {
        'base_yr': 15.5,
        'end_yr': 15.5}

    result = hdd_cdd.get_cdd_country(
        base_sim_param,
        regions,
        temp_data,
        smart_meter_diff_params,
        t_base_heating,
        reg_coord,
        weather_stations)
    
    expected = {
        "reg_A": (20 - 15.5) * 8760 / 24,
        "reg_B": (20 - 15.5) * 8760 / 24}

    assert result['reg_A'] == expected['reg_A']
    assert result['reg_B'] == expected['reg_B']
