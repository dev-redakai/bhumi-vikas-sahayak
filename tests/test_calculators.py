from backend.app.calculators import building_permission_fee, extract_params, front_open_space, rear_open_space


def test_front_table_boundaries():
    assert front_open_space(9.0).value == 3.0      # "Up to 9.0" is inclusive
    assert front_open_space(10).value == 3.6
    assert front_open_space(12.0).value == 3.6
    assert front_open_space(15).value == 4.5
    assert front_open_space(24).value == 6.0


def test_front_above_12_5m_redirects_to_rule_42():
    r = front_open_space(9, height_m=15)
    assert r.value is None and "42" in r.sub_rule


def test_rear_table():
    assert rear_open_space(40).value == 0.0
    assert rear_open_space(150).value == 1.5
    assert rear_open_space(151).value == 2.5
    assert rear_open_space(300).value == 3.0


def test_fee_slabs_and_multipliers():
    r = building_permission_fee(180)
    assert r.inputs["permission_fee"] == 2000 and r.inputs["application_fee"] == 180
    assert building_permission_fee(180, "commercial").inputs["permission_fee"] == 3000
    assert building_permission_fee(3000).inputs["permission_fee"] == 50000
    assert building_permission_fee(1000, height_m=35).inputs["permission_fee"] == 10000  # high-rise Rs 10/sq m


def test_extract_params_en_hi():
    p = extract_params("My plot is 200 sq m on a 9 m road, 7 m tall")
    assert p["area_sqm"] == 200 and p["street_width_m"] == 9 and p["height_m"] == 7
    p = extract_params("मेरा प्लॉट 200 वर्ग मीटर का है और सामने 9 मीटर चौड़ी सड़क है")
    assert p["area_sqm"] == 200 and p["street_width_m"] == 9
