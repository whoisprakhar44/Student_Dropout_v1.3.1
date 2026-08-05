
-- ────────────────────────────────────────────────────────────────
-- GEOGRAPHY
-- ────────────────────────────────────────────────────────────────


CREATE TABLE ap_citizen360.dim_state ( 
  state_id STRING NULL COMMENT 'Primary key', 
  state_name STRING NULL COMMENT 'e.g. Andhra Pradesh', 
  population BIGINT NULL, 
  households BIGINT NULL, 
  literacy_rate DOUBLE NULL, 
  sex_ratio BIGINT NULL, 
  districts_count BIGINT NULL, 
  mandals_count BIGINT NULL, 
  villages_count BIGINT NULL, 
  median_age DOUBLE NULL, 
  urbanization_pct DOUBLE NULL, 
  gross_state_income_cr BIGINT NULL COMMENT 'In crores', 
  electricity_consumers BIGINT NULL, 
  avg_monthly_kwh BIGINT NULL, 
  property_tax_collected BIGINT NULL, 
  agri_land_acres BIGINT NULL, 
  ration_cards_total BIGINT NULL, 
  ration_aay BIGINT NULL, 
  ration_phh BIGINT NULL, 
  ration_nphh BIGINT NULL, 
  ration_others BIGINT NULL, 
  effective_from DATE NULL COMMENT 'SCD Type-2 tracking', 
  effective_to DATE NULL, 
  is_current BOOLEAN NULL )  
 COMMENT 'State-level aggregated profile (SCD-2)' 
 STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/dim_state' 
 TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD,EXTWRITE', 
'engine.hive.enabled'='true', 
'external.table.purge'='TRUE', 
'table_type'='ICEBERG', 
'write.format.default'='parquet');

-
CREATE TABLE ap_citizen360.dim_district ( 
  district_id STRING NULL, 
  district_name STRING NULL, 
  state_id STRING NULL, 
  population BIGINT NULL, 
  households BIGINT NULL, 
  literacy_rate DOUBLE NULL, 
  sex_ratio INT NULL, 
  urbanization_pct DOUBLE NULL, 
  ration_cards_total BIGINT NULL, 
  ration_aay BIGINT NULL, 
  ration_phh BIGINT NULL, 
  ration_nphh BIGINT NULL, 
  ration_others BIGINT NULL, 
  vehicles BIGINT NULL, 
  land_acres BIGINT NULL, 
  agri_land_acres BIGINT NULL, 
  properties BIGINT NULL, 
  gas_connections BIGINT NULL, 
  electricity_consumers BIGINT NULL, 
  avg_monthly_kwh INT NULL, 
  property_tax_coverage INT NULL, 
  effective_from DATE NULL, 
  effective_to DATE NULL, 
  is_current BOOLEAN NULL ) 
  STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/dim_district' 
  TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD,EXTWRITE', 
'engine.hive.enabled'='true', 
'external.table.purge'='TRUE', 
'impala.lastComputeStatsTime'='1785126458', 
'table_type'='ICEBERG', 
'write.format.default'='parquet');

CREATE TABLE ap_citizen360.dim_mandal ( 
   mandal_id STRING NULL, 
   mandal_name STRING NULL, 
   district_id STRING NULL ) 
   STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/dim_mandal' 
   TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD, EXTWRITE', 
 'engine.hive.enabled'='true', 
 'external.table.purge'='TRUE', 
 'table_type'='ICEBERG', 
 'write.format.default'='parquet');

CREATE TABLE ap_citizen360.dim_secretariat (
  secretariat_code STRING NULL, 
  secretariat_name STRING NULL, 
  mandal_id STRING NULL ) 
  STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/dim_secretariat' 
  TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD,EXTWRITE', 
'engine.hive.enabled'='true', 
'external.table.purge'='TRUE', 
'table_type'='ICEBERG', 
'write.format.default'='parquet');

CREATE TABLE ap_citizen360.dim_village ( 
  village_id STRING NULL, 
  village_name STRING NULL, 
  mandal_id STRING NULL ) 
  PARTITIONED BY SPEC ( BUCKET(32, mandal_id) ) 
  STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/dim_village' 
TBLPROPERTIES ('STATS_GENERATED'='TASK', 
'engine.hive.enabled'='true', 
'impala.lastComputeStatsTime'='1784179463', 
'owner'='alis', 
'parquet.compression'='SNAPPY', 
'table_type'='ICEBERG', 
'write.delete.mode'='merge-on-read', 
'write.format.default'='parquet', 
'write.merge.mode'='merge-on-read', 
'write.update.mode'='merge-on-read');

-- ────────────────────────────────────────────────────────────────
-- PERSON / HOUSEHOLD / IDENTITY
-- ────────────────────────────────────────────────────────────────

CREATE TABLE ap_citizen360.dim_person (
 person_id STRING NULL, 
  person_name STRING NULL, 
  age INT NULL, 
  date_of_birth DATE NULL, 
  gender STRING NULL, 
  social_category STRING NULL, 
  phone STRING NULL, 
  income_band STRING NULL, 
  dwelling_type STRING NULL, 
  address STRING NULL, 
  district_id STRING NULL, 
  mandal_id STRING NULL, 
  village_name STRING NULL, 
  household_id STRING NULL, 
  created_at TIMESTAMP NULL, 
  updated_at TIMESTAMP NULL, 
  religion STRING NULL, 
  caste_name STRING NULL, 
  caste_derived_flag BOOLEAN NULL, 
  caste_base_certificate_no STRING NULL, 
  door_no STRING NULL, 
  secretariat_code STRING NULL, 
  constituency_code STRING NULL, 
  rural_urban_flag STRING NULL, 
  cluster_id STRING NULL, 
  domicile_status BOOLEAN NULL, 
  marital_status STRING NULL, 
  govt_employment_type STRING NULL, 
  is_deceased STRING NULL, 
  father_name STRING NULL, 
  father_person_id STRING NULL, 
  mother_name STRING NULL, 
  mother_person_id STRING NULL, 
  husband_name STRING NULL, 
  husband_person_id STRING NULL, 
  ration_card_no BIGINT NULL, 
  disability_type STRING NULL, 
  disability_percentage INT NULL, 
  disability_status STRING NULL ) 
  PARTITIONED BY SPEC ( district_id ) 
  STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/dim_person' 
  TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD,EXTWRITE', 
'engine.hive.enabled'='true', 
'external.table.purge'='TRUE', 
'table_type'='ICEBERG', 
'write.format.default'='parquet');

CREATE TABLE ap_citizen360.dim_household ( 
  household_id STRING NULL, 
  head_person_id STRING NULL, 
  head_name STRING NULL, 
  head_gender STRING NULL, 
  members_count INT NULL, 
  social_category STRING NULL, 
  ration_card_no STRING NULL, 
  ration_card_type STRING NULL, 
  income_band STRING NULL, 
  village_name STRING NULL, 
  mandal_id STRING NULL, 
  district_id STRING NULL, 
  latitude DOUBLE NULL, 
  longitude DOUBLE NULL, 
  pincode STRING NULL, 
  address STRING NULL, 
  dwelling_type STRING NULL, 
  phone STRING NULL, 
  household_income_category STRING NULL, 
  updated_at TIMESTAMP NULL ) 
  STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/dim_household' 
  TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD,EXTWRITE', 
'engine.hive.enabled'='true', 
'external.table.purge'='TRUE', 
'table_type'='ICEBERG', 
'write.format.default'='parquet');

CREATE TABLE ap_citizen360.dim_family_member (   
  family_member_id STRING NULL, 
  person_id STRING NULL, 
  household_id STRING NULL, 
  member_name STRING NULL, 
  relation STRING NULL, 
  age INT NULL, 
  gender STRING NULL, 
  updated_at TIMESTAMP NULL ) 
  STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/dim_family_member' 
  TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD,EXTWRITE', 
'engine.hive.enabled'='true', 
'external.table.purge'='TRUE', 
'table_type'='ICEBERG', 
'write.format.default'='parquet');

CREATE TABLE ap_citizen360.dim_citizen_identifier (   
  identifier_id STRING NULL, 
  person_id STRING NULL, 
  identifier_type STRING NULL, 
  identifier_value STRING NULL, 
  is_primary BOOLEAN NULL, 
  issuing_authority STRING NULL, 
  issued_date DATE NULL, 
  expiry_date DATE NULL, 
  is_active BOOLEAN NULL, 
  verified_flag BOOLEAN NULL, 
  source STRING NULL ) 
  STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/dim_citizen_identifier' 
  TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD,EXTWRITE', 
'engine.hive.enabled'='true', 
'external.table.purge'='TRUE', 
'impala.lastComputeStatsTime'='1783592589', 
'table_type'='ICEBERG', 
'write.format.default'='parquet');

CREATE TABLE ap_citizen360.dim_consent (   
  consent_id STRING NULL, 
  person_id STRING NULL, 
  allowed_purposes ARRAY<STRING> NULL, 
  valid_from DATE NULL, 
  valid_to DATE NULL, 
  is_revocable BOOLEAN NULL, 
  created_at TIMESTAMP NULL, 
  revoked_at TIMESTAMP NULL, 
  updated_at TIMESTAMP NULL ) 
  STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/dim_consent' 
  TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD,EXTWRITE', 
'engine.hive.enabled'='true', 
'external.table.purge'='TRUE', 
'table_type'='ICEBERG', 
'write.format.default'='parquet');

CREATE TABLE ap_citizen360.dim_tax_profile (   
  person_id STRING NULL, 
  gst_paid_annual DECIMAL(38,2) NULL, 
  income_tax_paid BOOLEAN NULL, 
  updated_at TIMESTAMP NULL ) 
  PARTITIONED BY SPEC ( BUCKET(32,updated_at) ) 
  STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/dim_tax_profile' 
  TBLPROPERTIES ('engine.hive.enabled'='true', 
'owner'='annapurnav', 
'parquet.compression'='SNAPPY', 
'table_type'='ICEBERG', 
'write.delete.mode'='merge-on-read', 
'write.format.default'='parquet', 
'write.merge.mode'='merge-on-read', 
'write.update.mode'='merge-on-read');

-- ────────────────────────────────────────────────────────────────
-- EMPLOYMENT / OCCUPATION — dim_occupation (multiple concurrent occupations per person)
-- ────────────────────────────────────────────────────────────────

CREATE TABLE ap_citizen360.dim_occupation (   
  occupation_record_id STRING NULL, 
  person_id STRING NULL, 
  occupation_type STRING NULL, 
  occupation_sector STRING NULL, 
  employer_name STRING NULL, 
  designation STRING NULL, 
  employment_status STRING NULL, 
  source STRING NULL, 
  occupation_year STRING NULL, 
  is_current BOOLEAN NULL, 
  updated_at TIMESTAMP NULL ) 
  STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/dim_occupation' 
  TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD,EXTWRITE', 
'engine.hive.enabled'='true', 
'external.table.purge'='TRUE', 
'table_type'='ICEBERG', 
'write.format.default'='parquet');

-- ────────────────────────────────────────────────────────────────
-- EDUCATION — dim_student (level-wise: Primary/Secondary/Intermediate/Polytechnic/Degree/PostGraduate)
-- ────────────────────────────────────────────────────────────────

CREATE TABLE ap_citizen360.dim_student (   
  student_record_id STRING, 
  person_id STRING, 
  education_level STRING, 
  highest_qualification STRING, 
  institution_id STRING, 
  institution_code STRING, 
  school_name STRING, 
  education_board STRING , 
  class_currently_enrolled INT , 
  academic_year STRING , 
  is_current_level BOOLEAN , 
  is_dropout BOOLEAN , 
  dropout_reason STRING , 
  medium_of_instruction STRING , 
  aadhaar_seeded BOOLEAN , 
  has_apaar_id BOOLEAN , 
  apaar_id STRING , 
  student_id STRING , 
  aposs_id STRING , 
  epass_id STRING , 
  epass_amount DECIMAL(10,2) , 
  thalliki_vandanam BOOLEAN , 
  ntr_vidya_deevena BOOLEAN , 
  pre_matric_scholarship BOOLEAN , 
  post_matric_scholarship BOOLEAN , 
  digital_literacy_level STRING , 
  scholarship_scheme_ids ARRAY<STRING> , 
  updated_at TIMESTAMP,
  student_pen STRING) 
  PARTITIONED BY SPEC(class_currently_enrolled)
  STORED AS ICEBERG
  TBLPROPERTIES (
  'format-version'='2',
  'write.format.default'='parquet',
  'write.parquet.compression-codec'='SNAPPY',
  'write.parquet.target-file-size-bytes'='134217728'
);

CREATE TABLE ap_citizen360.dim_vehicle (   
  vehicle_id STRING NULL, 
  person_id STRING NULL, 
  vehicle_type STRING NULL, 
  vehicle_class STRING NULL, 
  reg_no STRING NULL, 
  make STRING NULL, 
  model STRING NULL, 
  year_of_manufacture INT NULL, 
  fuel_type STRING NULL, 
  chassis_no STRING NULL, 
  engine_no STRING NULL, 
  color STRING NULL, 
  seating_capacity INT NULL, 
  unladen_weight_kg INT NULL, 
  laden_weight_kg INT NULL, 
  registration_date DATE NULL, 
  rto_office STRING NULL, 
  owner_name STRING NULL, 
  owner_mobile_number STRING NULL, 
  data_source STRING NULL, 
  updated_at TIMESTAMP NULL ) 
  STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/dim_vehicle' 
  TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD,EXTWRITE', 
'engine.hive.enabled'='true', 
'external.table.purge'='TRUE', 
'table_type'='ICEBERG', 
'write.format.default'='parquet');

CREATE TABLE ap_citizen360.dim_vehicle_compliance (   
 person_id STRING NULL, 
 reg_no STRING NULL, 
 insurance_valid_to DATE NULL, 
 insurance_company STRING NULL, 
 policy_no STRING NULL, 
 fitness_valid_to DATE NULL, 
 registration_valid_to DATE NULL, 
 puc_valid_to DATE NULL, 
 permit_type STRING NULL, 
 permit_valid_to DATE NULL, 
 tax_paid_upto DATE NULL, 
 green_tax_due BOOLEAN NULL, 
 financer_name STRING NULL, 
 hypothecation_status STRING NULL, 
 loan_outstanding DECIMAL(12,2) NULL, 
 hsrp_issued BOOLEAN NULL, 
 challan_pending BOOLEAN NULL, 
 updated_at TIMESTAMP NULL ) 
 STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/dim_vehicle_compliance' 
 TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD,EXTWRITE', 
 'engine.hive.enabled'='true', 
 'external.table.purge'='TRUE', 
 'table_type'='ICEBERG', 
 'write.format.default'='parquet');

-- ────────────────────────────────────────────────────────────────
-- ASSETS — LAND & PROPERTY
-- ────────────────────────────────────────────────────────────────

CREATE TABLE ap_citizen360.dim_land (   
  land_id STRING NULL, 
  person_id STRING NULL, 
  land_type STRING NULL, 
  land_classification STRING NULL, 
  acres DOUBLE NULL, 
  survey_no STRING NULL, 
  sub_survey_no STRING NULL, 
  hissa_no STRING NULL, 
  khata_no STRING NULL, 
  location STRING NULL, 
  district_id STRING NULL, 
  mandal_id STRING NULL, 
  village_name STRING NULL, 
  revenue_circle STRING NULL, 
  sro_office STRING NULL, 
  registration_no STRING NULL, 
  pattadar_passbook_no STRING NULL, 
  registration_date DATE NULL, 
  mutation_date DATE NULL, 
  market_value DECIMAL(12,2) NULL, 
  guideline_value DECIMAL(12,2) NULL, 
  stamp_duty_paid DECIMAL(10,2) NULL, 
  soil_type STRING NULL, 
  irrigation_type STRING NULL, 
  encumbrance_status STRING NULL, 
  mortgage_bank STRING NULL, 
  mortgage_amount DECIMAL(12,2) NULL, 
  is_assigned_land BOOLEAN NULL, 
  extent_wet_land DOUBLE NULL, 
  extent_dry_land DOUBLE NULL, 
  updated_at TIMESTAMP NULL, 
  aadhaar_mapped STRING NULL ) 
  STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/dim_land' 
  TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD,EXTWRITE', 
'engine.hive.enabled'='true', 
'external.table.purge'='TRUE', 
'table_type'='ICEBERG', 
'write.format.default'='parquet');

CREATE TABLE ap_citizen360.dim_property (   
  property_id STRING NULL, 
   person_id STRING NULL, 
   property_type STRING NULL, 
   property_sub_type STRING NULL, 
   door_no STRING NULL, 
   ward_no STRING NULL, 
   block_no STRING NULL, 
   plot_no STRING NULL, 
   street_name STRING NULL, 
   locality STRING NULL, 
   location STRING NULL, 
   pincode STRING NULL, 
   district_id STRING NULL, 
   area_sq_ft INT NULL, 
   built_up_area_sq_ft INT NULL, 
   site_area_sq_ft INT NULL, 
   construction_type STRING NULL, 
   roof_type STRING NULL, 
   usage_type STRING NULL, 
   registration_no STRING NULL, 
   registration_date DATE NULL, 
   market_value DECIMAL(12,2) NULL, 
   guideline_value DECIMAL(12,2) NULL, 
   ptin STRING NULL, 
   municipal_no STRING NULL, 
   municipal_body STRING NULL, 
   sro_office STRING NULL, 
   construction_year INT NULL, 
   floor_count INT NULL, 
   assessment_no STRING NULL, 
   owner_name STRING NULL, 
   plinth_area_units STRING NULL, 
   site_extent_units STRING NULL, 
   updated_at TIMESTAMP NULL, 
   aadhaar_mapped STRING NULL ) 
   STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/dim_property' 
   TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD,EXTWRITE', 
 'engine.hive.enabled'='true', 
 'external.table.purge'='TRUE', 
 'table_type'='ICEBERG', 
 'write.format.default'='parquet');

CREATE TABLE ap_citizen360.dim_property_tax (   
   person_id STRING NULL, 
   ptin STRING NULL, 
   assessment_year STRING NULL, 
   annual_demand_rs DECIMAL(12,2) NULL, 
   arrears_rs DECIMAL(12,2) NULL, 
   total_due_rs DECIMAL(12,2) NULL, 
   amount_paid_rs DECIMAL(12,2) NULL, 
   tax_status STRING NULL, 
   last_paid_date DATE NULL, 
   payment_mode STRING NULL, 
   exemption_category STRING NULL, 
   municipal_body STRING NULL, 
   department_id STRING NULL, 
   updated_at TIMESTAMP NULL ) 
   STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/dim_property_tax' 
   TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD, 
EXTWRITE', 
 'engine.hive.enabled'='true', 
 'external.table.purge'='TRUE', 
 'table_type'='ICEBERG', 
 'write.format.default'='parquet');
 
 -- ────────────────────────────────────────────────────────────────
-- HEALTH
-- ────────────────────────────────────────────────────────────────

CREATE TABLE ap_citizen360.dim_health_profile (   
  person_id STRING NULL, 
  abdm_id STRING NULL, 
  abha_address STRING NULL, 
  aarogyasri_card_no STRING NULL, 
  aarogyasri_status STRING NULL, 
  pmjay_beneficiary_id STRING NULL, 
  pmjay_family_id STRING NULL, 
  blood_group STRING NULL, 
  height_cm INT NULL, 
  weight_kg DOUBLE NULL, 
  bmi DOUBLE NULL, 
  conditions ARRAY<STRING> NULL, 
  has_diabetes BOOLEAN NULL, 
  has_hypertension BOOLEAN NULL, 
  has_tuberculosis BOOLEAN NULL, 
  has_hiv BOOLEAN NULL, 
  has_cancer BOOLEAN NULL, 
  registered_phc STRING NULL, 
  assigned_asha_worker STRING NULL, 
  is_pregnant BOOLEAN NULL, 
  lmp_date DATE NULL, 
  edd_date DATE NULL, 
  anc_registrations INT NULL, 
  institutional_delivery BOOLEAN NULL, 
  covid_vaccinated BOOLEAN NULL, 
  covid_doses INT NULL, 
  esi_covered BOOLEAN NULL, 
  cghs_covered BOOLEAN NULL, 
  rsby_covered BOOLEAN NULL, 
  has_mental_health_condition BOOLEAN NULL, 
  mental_health_type STRING NULL, 
  last_encounter_date DATE NULL, 
  linked_scheme_ids ARRAY<STRING> NULL, 
  department_id STRING NULL, 
  updated_at TIMESTAMP NULL ) 
  STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/dim_health_profile' 
  TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD,EXTWRITE', 
'engine.hive.enabled'='true', 
'external.table.purge'='TRUE', 
'table_type'='ICEBERG', 
'write.format.default'='parquet');

-- ────────────────────────────────────────────────────────────────
-- AGRICULTURE
-- ────────────────────────────────────────────────────────────────

CREATE TABLE ap_citizen360.dim_agriculture_profile (   
person_id STRING NULL, 
  farmer_id STRING NULL, 
  farmer_type STRING NULL, 
  total_land_acres DOUBLE NULL, 
  irrigated_land_acres DOUBLE NULL, 
  dry_land_acres DOUBLE NULL, 
  primary_crop STRING NULL, 
  secondary_crop STRING NULL, 
  crop_season STRING NULL, 
  crop_types ARRAY<STRING> NULL, 
  land_reg_nos ARRAY<STRING> NULL, 
  soil_health_card_no STRING NULL, 
  irrigation_source STRING NULL, 
  pump_set_hp DOUBLE NULL, 
  kcc_bank STRING NULL, 
  kcc_account_no STRING NULL, 
  kcc_limit DECIMAL(12,2) NULL, 
  pm_kisan_beneficiary BOOLEAN NULL, 
  rythu_bharosa_beneficiary BOOLEAN NULL, 
  pmfby_enrolled BOOLEAN NULL, 
  market_linkage STRING NULL, 
  fpo_name STRING NULL, 
  last_yield_qtl_acre DOUBLE NULL, 
  linked_scheme_ids ARRAY<STRING> NULL, 
  department_id STRING NULL, 
  updated_at TIMESTAMP NULL, 
  aadhaar_mapped STRING NULL ) 
  STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/dim_agriculture_profile' 
  TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD,EXTWRITE', 
'engine.hive.enabled'='true', 
'external.table.purge'='TRUE', 
'table_type'='ICEBERG', 
'write.format.default'='parquet');

CREATE TABLE ap_citizen360.dim_crop_sale (   
  person_id STRING NULL, 
  financial_year STRING NULL, 
  amt_paddy DECIMAL(14,2) NULL, 
  amt_nonpaddy DECIMAL(14,2) NULL, 
  amt_total DECIMAL(14,2) NULL, 
  updated_at TIMESTAMP NULL ) 
  STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/dim_crop_sale' 
  TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD,EXTWRITE', 
'engine.hive.enabled'='true', 
'external.table.purge'='TRUE', 
'table_type'='ICEBERG', 
'write.format.default'='parquet');

-- ────────────────────────────────────────────────────────────────
-- SOCIAL WELFARE
-- ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS dim_social_welfare (
  person_id STRING,
  pension_id STRING,
  pension_type STRING,
  monthly_amount DECIMAL(10,2),
  pension_status STRING,
  pension_bank STRING,
  pension_account_no STRING,
  is_disabled BOOLEAN,
  disability_type STRING,
  disability_percentage INT,
  udid_card_no STRING,
  bpl_card_no STRING,
  secc_family_id STRING,
  annual_family_income DECIMAL(12,2),
  deepam_beneficiary BOOLEAN,
  bc_welfare_scheme STRING,
  shg_name STRING,
  shg_role STRING,
  ntr_bharosa_flag BOOLEAN,
  department_id STRING,
  disability_certificate_date DATE,
  updated_at TIMESTAMP)
USING iceberg;

-- ────────────────────────────────────────────────────────────────
-- UTILITIES
-- ────────────────────────────────────────────────────────────────

CREATE TABLE ap_citizen360.dim_utility_connection (   
  person_id STRING NULL, 
  gas_connection_status STRING NULL, 
  electricity_status STRING NULL, 
  avg_monthly_kwh INT NULL, 
  water_connection_status STRING NULL, 
  electricity_sc_no STRING NULL, 
  discom_name STRING NULL, 
  electricity_status_updated_on DATE NULL, 
  updated_at TIMESTAMP NULL, 
  lpg_consumer_id STRING NULL ) 
  STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/dim_utility_connection' 
  TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD,EXTWRITE', 
'engine.hive.enabled'='true', 
'external.table.purge'='TRUE', 
'table_type'='ICEBERG', 
'write.format.default'='parquet');

-- ────────────────────────────────────────────────────────────────
-- EMPLOYMENT — EPFO
-- ────────────────────────────────────────────────────────────────

CREATE TABLE ap_citizen360.dim_epfo_contribution (   
  person_id STRING NULL, 
  employee_contribution DECIMAL(10,0) NULL, 
  employer_contribution DECIMAL(10,0) NULL, 
  eps_contribution DECIMAL(10,0) NULL, 
  latest_contribution_date DATE NULL, 
  secretariat_code STRING NULL, 
  establishment_id STRING NULL, 
  updated_at TIMESTAMP NULL ) 
  STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/dim_epfo_contribution' 
  TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD,EXTWRITE', 
'engine.hive.enabled'='true', 
'external.table.purge'='TRUE', 
'table_type'='ICEBERG', 
'write.format.default'='parquet');

-- ────────────────────────────────────────────────────────────────
-- SCHEMES, DEPARTMENTS & GOVERNANCE
-- ────────────────────────────────────────────────────────────────

CREATE TABLE ap_citizen360.dim_department (  
  department_id STRING NULL COMMENT 'Primary key', 
  department_name STRING NULL COMMENT 'e.g. Food & Civil Supplies' )  
  COMMENT 'Government department dimension' 
  STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/dim_department' 
  TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD,EXTWRITE', 
'engine.hive.enabled'='true', 
'external.table.purge'='TRUE', 
'table_type'='ICEBERG', 
'write.format.default'='parquet');

CREATE TABLE ap_citizen360.dim_scheme (  
  scheme_id STRING NULL COMMENT 'Primary key', 
  scheme_name STRING NULL, 
  department_id STRING NULL COMMENT 'FK → dim_department', 
  benefit_type STRING NULL COMMENT 'Direct Cash Transfer / Insurance Coverage / Fee Reimbursement / In-Kind' )  
  COMMENT 'Government scheme dimension' STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/dim_scheme' 
  TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD,EXTWRITE', 
'engine.hive.enabled'='true', 
'external.table.purge'='TRUE', 
'table_type'='ICEBERG', 
'write.format.default'='parquet');

CREATE TABLE ap_citizen360.dim_scheme_main_mapping (   
   scheme_id STRING NULL COMMENT 'Actual / leaf scheme id (from dim_scheme)', 
   main_scheme_id STRING NULL COMMENT 'Parent / main scheme id (from dim_scheme)', 
   updated_at TIMESTAMP NULL ) 
  STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/dim_scheme_main_mapping' 
   TBLPROPERTIES ( 'table_type'='ICEBERG');
  
   -- ────────────────────────────────────────────────────────────────
-- DATA TRANSFER API — SECURITY / DEPARTMENT CLIENT REGISTRY (JWT auth, /auth/token)
-- ────────────────────────────────────────────────────────────────

CREATE TABLE ap_citizen360.dim_department_client (   
  department_id STRING NULL, 
  client_secret_hash STRING NULL, 
  scopes ARRAY<STRING> NULL, 
  dimensions ARRAY<STRING> NULL, 
  is_active BOOLEAN NULL, 
  created_at TIMESTAMP NULL, 
  updated_at TIMESTAMP NULL ) 
 STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/dim_department_client' 
 TBLPROPERTIES ('owner'='saibhargavid', 
'table_type'='ICEBERG', 
'write.delete.mode'='merge-on-read', 
'write.merge.mode'='merge-on-read', 
'write.update.mode'='merge-on-read');

-- ────────────────────────────────────────────────────────────────
-- DATA TRANSFER API — FACT: ENTITLEMENTS, TRANSACTIONS, DISBURSEMENTS
-- ────────────────────────────────────────────────────────────────

CREATE TABLE ap_citizen360.fact_entitlement (   
   entitlement_id STRING COMMENT 'Primary key (generated)', 
   person_id STRING COMMENT 'FK → dim_person', 
   household_id STRING COMMENT 'FK → dim_household', 
   scheme_id STRING COMMENT 'FK → dim_scheme', 
   enrollment_status STRING COMMENT 'Active / Inactive / Suspended', 
   annual_benefit DECIMAL(12,2) COMMENT 'Annual benefit amount in ₹', 
   last_disbursed_date DATE, 
   enrolled_date DATE, 
   district_id STRING COMMENT 'FK → dim_district (for partitioning)' ) 
   PARTITIONED BY SPEC(scheme_id)
   COMMENT 'Citizen-scheme enrolment fact (one row per citizen per scheme)' 
   STORED AS ICEBERG
   TBLPROPERTIES (
'format-version'='2',
'write.format.default'='parquet',
'write.parquet.compression-codec'='SNAPPY',
'write.parquet.target-file-size-bytes'='134217728'
);
 
 
/* CREATE TABLE ap_citizen360.fact_benefit_transaction (   
  transaction_id STRING COMMENT 'Primary key', 
  entitlement_id STRING COMMENT 'FK ? fact_entitlement', 
  person_id STRING COMMENT 'FK ? dim_person', 
  scheme_id STRING COMMENT 'FK ? dim_scheme', 
  amount DECIMAL(12,2) COMMENT 'Disbursed amount in ?', 
  transaction_date DATE, 
  district_id STRING COMMENT 'FK ? dim_district' ) 
  COMMENT 'Individual benefit disbursement transactions' 
  STORED AS PARQUET LOCATION 'hdfs://datalakedev/warehouse/tablespace/managed/hive/ap_citizen360.db/fact_benefit_transaction' 
  TBLPROPERTIES ('OBJCAPABILITIES'='HIVEMANAGEDINSERTREAD,HIVEMANAGEDINSERTWRITE', 
'rawDataSize'='14381407233', 
'transactional'='true', 
'transactional_properties'='insert_only');
*/

CREATE EXTERNAL TABLE ap_citizen360.fact_benefit_transaction (   
   transaction_id STRING NULL COMMENT 'Primary key', 
   entitlement_id STRING NULL COMMENT 'FK ? fact_entitlement', 
   person_id STRING NULL COMMENT 'FK ? dim_person', 
   scheme_id STRING NULL COMMENT 'FK ? dim_scheme', 
   amount DECIMAL(12,2) NULL COMMENT 'Disbursed amount in ?', 
   transaction_date DATE NULL, 
   district_id STRING NULL COMMENT 'FK ? dim_district' )  
   COMMENT 'Individual benefit disbursement transactions' 
  STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/fact_benefit_transaction' 
   TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD, EXTWRITE', 
 'engine.hive.enabled'='true', 
 'external.table.purge'='TRUE', 
 'table_type'='ICEBERG', 
 'write.format.default'='parquet')

CREATE EXTERNAL TABLE ap_citizen360.fact_entitlement (   
  entitlement_id STRING NULL COMMENT 'Primary key (generated)', 
   person_id STRING NULL COMMENT 'FK → dim_person', 
   household_id STRING NULL COMMENT 'FK → dim_household', 
   scheme_id STRING NULL COMMENT 'FK → dim_scheme', 
   enrollment_status STRING NULL COMMENT 'Active / Inactive / Suspended', 
   annual_benefit DECIMAL(12, 
2) NULL COMMENT 'Annual benefit amount in ₹', 
   last_disbursed_date DATE NULL, 
   enrolled_date DATE NULL, 
   district_id STRING NULL COMMENT 'FK → dim_district (for partitioning)' ) 
   PARTITIONED BY SPEC ( scheme_id )  
   COMMENT 'Citizen-scheme enrolment fact (one row per citizen per scheme)' 
   STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/fact_entitlement'
   TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD, EXTWRITE', 
 'engine.hive.enabled'='true', 
 'external.table.purge'='TRUE', 
 'table_type'='ICEBERG', 
 'write.delete.mode'='merge-on-read', 
 'write.format.default'='parquet', 
 'write.merge.mode'='merge-on-read', 
 'write.parquet.compression-codec'='SNAPPY', 
 'write.parquet.target-file-size-bytes'='134217728', 
 'write.update.mode'='merge-on-read')

-- ────────────────────────────────────────────────────────────────
-- DATA TRANSFER API — FACT: LIFECYCLE EVENTS & ANOMALIES (backs POST /datatransfer/request)
-- ────────────────────────────────────────────────────────────────

CREATE TABLE ap_citizen360.fact_lifecycle_event (   
   event_id STRING NULL, 
   person_id STRING NULL, 
   citizen_name STRING NULL, 
   event_type STRING NULL, 
   trigger_reason STRING NULL, 
   source_system STRING NULL, 
   event_timestamp TIMESTAMP NULL, 
   district_id STRING NULL, 
   mandal_id STRING NULL, 
   village_name STRING NULL, 
   details STRING NULL, 
   processing_status STRING NULL, 
   linked_scheme_ids STRING NULL, 
   metadata STRING NULL, 
   district_name STRING NULL, 
   mandal_name STRING NULL, 
   department_id STRING NULL, 
   eventdata STRING NULL ) 
   PARTITIONED BY SPEC ( MONTH(event_timestamp), district_id ) 
   STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/fact_lifecycle_event' 
   TBLPROPERTIES ( 'table_type'='ICEBERG');
   
 CREATE TABLE ap_citizen360.fact_anomaly_event (   
  anomaly_id STRING NULL, 
  person_id STRING NULL, 
  citizen_name STRING NULL, 
  anomaly_type STRING NULL, 
  severity STRING NULL, 
  detected_at TIMESTAMP NULL, 
  district_id STRING NULL, 
  mandal_id STRING NULL, 
  village_name STRING NULL, 
  summary STRING NULL, 
  resolution_status STRING NULL, 
  household_id STRING NULL, 
  metadata STRING NULL, 
  district_name STRING NULL, 
  mandal_name STRING NULL, 
  department_id STRING NULL, 
  eventdata STRING NULL ) 
  PARTITIONED BY SPEC ( MONTH(detected_at), district_id ) 
  STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/fact_anomaly_event' 
  TBLPROPERTIES ('table_type'='ICEBERG');
  
 CREATE EXTERNAL TABLE ap_citizen360.fact_anomaly_loan (   
   anomaly_loan_id STRING NULL COMMENT 'Primary key (generated)', 
   anomaly_id STRING NULL COMMENT 'FK → fact_anomaly_event', 
   loan_source STRING NULL COMMENT 'SERP / MEPMA / etc.', 
   loan_id STRING NULL, 
   amount_taken DECIMAL(12,2) NULL, 
   outstanding DECIMAL(12,2) NULL, 
   disbursed_date DATE NULL, 
   last_updated DATE NULL )  
   COMMENT 'Loan details associated with dual-loan anomalies' 
   STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/fact_anomaly_loan' 
   TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD, EXTWRITE', 
 'engine.hive.enabled'='true', 
 'external.table.purge'='TRUE', 
 'table_type'='ICEBERG', 
 'write.format.default'='parquet');
 
 CREATE TABLE ap_citizen360.fact_anomaly_pregnancy (   
   anomaly_pregnancy_id STRING NULL, 
   anomaly_id STRING NULL, 
   source_system STRING NULL, 
   registration_id STRING NULL, 
   registered_date DATE NULL, 
   lmp_date DATE NULL, 
   edd_date DATE NULL, 
   record_status STRING NULL ) 
   STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/fact_anomaly_pregnancy' 
   TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD,EXTWRITE', 
 'engine.hive.enabled'='true', 
 'external.table.purge'='TRUE', 
 'table_type'='ICEBERG', 
 'write.format.default'='parquet');
 
 -- ────────────────────────────────────────────────────────────────
-- DATA TRANSFER API — REQUEST IDEMPOTENCY, EVENT-DELIVERY INDEX, ACK/STATUS PERSISTENCE
-- Backs the request/on_request/event_status loop: fact_event_request_registry detects
-- a reused requestId with a different payload (409 CONFLICT); fact_event_index records
-- which department each event's correlationId was actually delivered to, so on_request
-- and event_status can reject an ack/status-update for an event that was never sent to
-- the calling department (404/403); fact_event_acknowledgement and fact_event_status_update
-- persist what departments actually report back.
-- ────────────────────────────────────────────────────────────────

CREATE TABLE ap_citizen360.fact_event_request_registry (   
  request_id STRING NULL, 
  payload_hash STRING NULL, 
  department_id STRING NULL, 
  event_correlation_ids STRING NULL, 
  payload_json STRING NULL, 
  created_at TIMESTAMP NULL )
  STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/fact_event_request_registry' 
  TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD,EXTWRITE', 
'engine.hive.enabled'='true', 
'external.table.purge'='TRUE', 
'table_type'='ICEBERG', 
'write.format.default'='parquet');

CREATE TABLE ap_citizen360.fact_event_index (   
  event_correlation_id STRING NULL, 
  request_id STRING NULL, 
  created_at TIMESTAMP NULL, 
  department_id STRING NULL ) 
  STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/fact_event_index' 
  TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD,EXTWRITE', 
'engine.hive.enabled'='true', 
'external.table.purge'='TRUE', 
'table_type'='ICEBERG', 
'write.format.default'='parquet');

CREATE TABLE ap_citizen360.fact_event_acknowledgement (   
  acknowledgement_id STRING NULL, 
   original_request_id STRING NULL, 
   department_id STRING NULL, 
   acknowledged_at TIMESTAMP NULL, 
   payload_json STRING NULL, 
   created_at TIMESTAMP NULL ) 
   STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/fact_event_acknowledgement' 
   TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD,EXTWRITE', 
 'engine.hive.enabled'='true', 
 'external.table.purge'='TRUE', 
 'table_type'='ICEBERG', 
 'write.format.default'='parquet');
 
 CREATE EXTERNAL TABLE ap_citizen360.fact_event_status_update (   
  event_correlation_id STRING NULL, 
   processing_status STRING NULL, 
   department_reference_id STRING NULL, 
   updated_at TIMESTAMP NULL, 
   remarks STRING NULL, 
   source STRING NULL, 
   created_at TIMESTAMP NULL ) 
  STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/fact_event_status_update' 
  TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD,EXTWRITE', 
 'engine.hive.enabled'='true', 
 'external.table.purge'='TRUE', 
 'table_type'='ICEBERG', 
 'write.format.default'='parquet');
 
-- ────────────────────────────────────────────────────────────────
-- FACT — POPULATION & UTILITY TRENDS
-- ────────────────────────────────────────────────────────────────

CREATE TABLE ap_citizen360.fact_population_hierarchy (   
  geo_level STRING NULL COMMENT 'state | district | mandal | village', 
   geo_id STRING NULL COMMENT 'ap | district_id | mandal_id | village_name', 
   gender STRING NULL COMMENT 'Male | Female | Others', 
   social_category STRING NULL COMMENT 'OC | BC | SC | ST | Others', 
   population_count BIGINT NULL COMMENT 'Census population for this cell', 
   household_count BIGINT NULL COMMENT 'Number of households headed by this gender/category', 
   ration_card_count BIGINT NULL COMMENT 'NFSA ration card holders in this gender/category cell' )
   STORED AS ICEBERG LOCATION 'hdfs://datalakedev/user/CURATED/ap_citizen360/fact_population_hierarchy' 
   TBLPROPERTIES ('OBJCAPABILITIES'='EXTREAD, EXTWRITE', 
 'engine.hive.enabled'='true', 
 'external.table.purge'='TRUE', 
 'table_type'='ICEBERG', 
 'write.format.default'='parquet');
 
 CREATE TABLE IF NOT EXISTS fact_population_age_band (
  age_band_id STRING,
  geo_level STRING,
  geo_id STRING,
  age_band STRING,
  percentage DOUBLE,
  snapshot_date DATE)
USING iceberg;

CREATE TABLE IF NOT EXISTS fact_utility_trend (
  trend_id STRING,
  geo_level STRING,
  geo_id STRING,
  trend_month DATE,
  electricity_index INT,
  gas_index INT,
  water_index INT)
USING iceberg
PARTITIONED BY (geo_level, months(trend_month));

CREATE TABLE IF NOT EXISTS fact_village_kpi (
  village_kpi_id STRING,
  village_name STRING,
  mandal_id STRING,
  district_id STRING,
  snapshot_date DATE,
  total_households INT,
  total_disbursed DECIMAL(12,2),
  avg_disbursed_per_hh DECIMAL(10,2))
USING iceberg
PARTITIONED BY (district_id, months(snapshot_date));


-- ────────────────────────────────────────────────────────────────
-- FACT — P4 (PEOPLE-PUBLIC POLICY PERFORMANCE) SCORING
-- ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS dim_p4_kpi (
  kpi_id STRING,
  thematic_area STRING,
  area_weightage DOUBLE,
  kpi_name STRING,
  description STRING,
  unit STRING,
  target_value DOUBLE,
  is_inverse BOOLEAN)
USING iceberg;

CREATE TABLE IF NOT EXISTS fact_p4_citizen_score (
  citizen_score_id STRING,
  person_id STRING,
  household_id STRING,
  district_id STRING,
  mandal_id STRING,
  village_name STRING,
  period STRING,
  is_bangaru_kutumbam BOOLEAN,
  health_nutrition_score DOUBLE,
  education_score DOUBLE,
  agriculture_livelihood_score DOUBLE,
  financial_inclusion_score DOUBLE,
  infrastructure_living_score DOUBLE,
  composite_score DOUBLE,
  upliftment_status STRING,
  created_at TIMESTAMP)
USING iceberg;

CREATE TABLE IF NOT EXISTS fact_p4_geo_score (
  score_id STRING,
  kpi_id STRING,
  geo_level STRING,
  geo_id STRING,
  period STRING,
  current_value DOUBLE,
  target_value DOUBLE,
  achievement_pct DOUBLE,
  delta_mom DOUBLE,
  created_at TIMESTAMP)
USING iceberg;

CREATE TABLE IF NOT EXISTS fact_p4_ranking (
  ranking_id STRING,
  geo_level STRING,
  geo_id STRING,
  geo_name STRING,
  period STRING,
  health_nutrition_score DOUBLE,
  education_score DOUBLE,
  agriculture_livelihood_score DOUBLE,
  financial_inclusion_score DOUBLE,
  infrastructure_living_score DOUBLE,
  composite_score DOUBLE,
  rank INT,
  previous_rank INT,
  delta_rank INT,
  bangaru_kutumbam_total INT,
  bangaru_kutumbam_uplifted INT,
  upliftment_pct DOUBLE,
  created_at TIMESTAMP)
USING iceberg;

CREATE TABLE IF NOT EXISTS fact_p4_kpi_forecast (
  forecast_id STRING,
  kpi_id STRING,
  geo_level STRING,
  geo_id STRING,
  period STRING,
  current_value DOUBLE,
  forecast_3m DOUBLE,
  forecast_6m DOUBLE,
  forecast_12m DOUBLE,
  confidence DOUBLE,
  trend STRING,
  risk_score DOUBLE,
  intervention STRING,
  priority STRING,
  created_at TIMESTAMP)
USING iceberg;
