import os
import sys

# Add the project root to sys.path so we can import MCP.hive_executor
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from MCP.hive_executor import HiveExecutor

# Dictionary of categorical columns extracted from impala_tables_sample.txt
CATEGORICAL_COLUMNS = {
    'ap_citizen360.dim_citizen_identifier': ['IDENTIFIER_TYPE', 'IDENTIFIER_VALUE', 'ISSUING_AUTHORITY', 'IS_ACTIVE', 'IS_PRIMARY', 'SOURCE', 'VERIFIED_FLAG'],
    'ap_citizen360.dim_crop_sale': ['AMT_NONPADDY', 'AMT_PADDY', 'AMT_TOTAL', 'FINANCIAL_YEAR'],
    'ap_citizen360.dim_department': ['DEPARTMENT_NAME'],
    'ap_citizen360.dim_department_client': ['CLIENT_SECRET_HASH', 'IS_ACTIVE'],
    'ap_citizen360.dim_district': ['DISTRICT_NAME', 'EFFECTIVE_FROM', 'EFFECTIVE_TO', 'ELECTRICITY_CONSUMERS', 'GAS_CONNECTIONS', 'IS_CURRENT', 'LITERACY_RATE', 'PROPERTIES', 'PROPERTY_TAX_COVERAGE', 'RATION_AAY', 'RATION_CARDS_TOTAL', 'RATION_NPHH', 'RATION_OTHERS', 'RATION_PHH', 'SEX_RATIO', 'URBANIZATION_PCT', 'VEHICLES'],
    'ap_citizen360.dim_epfo_contribution': ['EMPLOYEE_CONTRIBUTION', 'EMPLOYER_CONTRIBUTION', 'EPS_CONTRIBUTION'],
    'ap_citizen360.dim_family_member': ['GENDER', 'MEMBER_NAME', 'RELATION'],
    'ap_citizen360.dim_health_profile': ['AAROGYASRI_STATUS', 'ABHA_ADDRESS', 'ANC_REGISTRATIONS', 'ASSIGNED_ASHA_WORKER', 'BLOOD_GROUP', 'BMI', 'CGHS_COVERED', 'COVID_DOSES', 'COVID_VACCINATED', 'ESI_COVERED', 'HAS_CANCER', 'HAS_DIABETES', 'HAS_HIV', 'HAS_HYPERTENSION', 'HAS_MENTAL_HEALTH_CONDITION', 'HAS_TUBERCULOSIS', 'HEIGHT_CM', 'INSTITUTIONAL_DELIVERY', 'IS_PREGNANT', 'MENTAL_HEALTH_TYPE', 'REGISTERED_PHC', 'RSBY_COVERED', 'WEIGHT_KG'],
    'ap_citizen360.dim_household': ['DWELLING_TYPE', 'HEAD_GENDER', 'HEAD_NAME', 'HOUSEHOLD_INCOME_CATEGORY', 'INCOME_BAND', 'RATION_CARD_TYPE', 'SOCIAL_CATEGORY', 'VILLAGE_NAME'],
    'ap_citizen360.dim_land': ['AADHAAR_MAPPED', 'ENCUMBRANCE_STATUS', 'EXTENT_DRY_LAND', 'EXTENT_WET_LAND', 'GUIDELINE_VALUE', 'IRRIGATION_TYPE', 'IS_ASSIGNED_LAND', 'LAND_CLASSIFICATION', 'LAND_TYPE', 'LOCATION', 'MARKET_VALUE', 'MORTGAGE_BANK', 'REVENUE_CIRCLE', 'SOIL_TYPE', 'SRO_OFFICE', 'STAMP_DUTY_PAID', 'VILLAGE_NAME'],
    'ap_citizen360.dim_mandal': ['MANDAL_NAME'],
    'ap_citizen360.dim_occupation': ['DESIGNATION', 'EMPLOYER_NAME', 'EMPLOYMENT_STATUS', 'IS_CURRENT', 'OCCUPATION_SECTOR', 'OCCUPATION_TYPE', 'OCCUPATION_YEAR', 'SOURCE'],
    'ap_citizen360.dim_person': ['CASTE_DERIVED_FLAG', 'CASTE_NAME', 'DISABILITY_PERCENTAGE', 'DISABILITY_STATUS', 'DISABILITY_TYPE', 'DOMICILE_STATUS', 'DWELLING_TYPE', 'FATHER_NAME', 'GENDER', 'GOVT_EMPLOYMENT_TYPE', 'HUSBAND_NAME', 'INCOME_BAND', 'IS_DECEASED', 'MARITAL_STATUS', 'MOTHER_NAME', 'PERSON_NAME', 'RELIGION', 'RURAL_URBAN_FLAG', 'SOCIAL_CATEGORY', 'VILLAGE_NAME'],
    'ap_citizen360.dim_property': ['AADHAAR_MAPPED', 'AREA_SQ_FT', 'BUILT_UP_AREA_SQ_FT', 'CONSTRUCTION_TYPE', 'CONSTRUCTION_YEAR', 'GUIDELINE_VALUE', 'LOCALITY', 'LOCATION', 'MARKET_VALUE', 'MUNICIPAL_BODY', 'OWNER_NAME', 'PLINTH_AREA_UNITS', 'PROPERTY_SUB_TYPE', 'PROPERTY_TYPE', 'PTIN', 'ROOF_TYPE', 'SITE_AREA_SQ_FT', 'SITE_EXTENT_UNITS', 'SRO_OFFICE', 'STREET_NAME', 'USAGE_TYPE'],
    'ap_citizen360.dim_scheme': ['BENEFIT_TYPE', 'SCHEME_NAME'],
    'ap_citizen360.dim_state': ['EFFECTIVE_FROM', 'EFFECTIVE_TO', 'ELECTRICITY_CONSUMERS', 'GROSS_STATE_INCOME_CR', 'IS_CURRENT', 'LITERACY_RATE', 'MEDIAN_AGE', 'PROPERTY_TAX_COLLECTED', 'RATION_AAY', 'RATION_CARDS_TOTAL', 'RATION_NPHH', 'RATION_OTHERS', 'RATION_PHH', 'SEX_RATIO', 'STATE_NAME', 'URBANIZATION_PCT'],
    'ap_citizen360.dim_student': ['AADHAAR_SEEDED', 'ACADEMIC_YEAR', 'CLASS_CURRENTLY_ENROLLED', 'DIGITAL_LITERACY_LEVEL', 'DROPOUT_REASON', 'EDUCATION_BOARD', 'EDUCATION_LEVEL', 'HIGHEST_QUALIFICATION', 'IS_CURRENT_LEVEL', 'IS_DROPOUT', 'MEDIUM_OF_INSTRUCTION', 'NTR_VIDYA_DEEVENA', 'POST_MATRIC_SCHOLARSHIP', 'PRE_MATRIC_SCHOLARSHIP', 'SCHOOL_NAME', 'STUDENT_PEN', 'THALLIKI_VANDANAM'],
    'ap_citizen360.dim_tax_profile': ['GST_PAID_ANNUAL', 'INCOME_TAX_PAID'],
    'ap_citizen360.dim_utility_connection': ['DISCOM_NAME', 'ELECTRICITY_STATUS', 'ELECTRICITY_STATUS_UPDATED_ON', 'GAS_CONNECTION_STATUS', 'WATER_CONNECTION_STATUS'],
    'ap_citizen360.dim_vehicle': ['COLOR', 'DATA_SOURCE', 'FUEL_TYPE', 'LADEN_WEIGHT_KG', 'MAKE', 'MODEL', 'OWNER_NAME', 'RTO_OFFICE', 'SEATING_CAPACITY', 'UNLADEN_WEIGHT_KG', 'VEHICLE_CLASS', 'VEHICLE_TYPE', 'YEAR_OF_MANUFACTURE'],
    'ap_citizen360.dim_vehicle_compliance': ['CHALLAN_PENDING', 'FINANCER_NAME', 'FITNESS_VALID_TO', 'GREEN_TAX_DUE', 'HSRP_ISSUED', 'HYPOTHECATION_STATUS', 'INSURANCE_COMPANY', 'INSURANCE_VALID_TO', 'LOAN_OUTSTANDING', 'PERMIT_TYPE', 'PERMIT_VALID_TO', 'PUC_VALID_TO', 'REGISTRATION_VALID_TO', 'TAX_PAID_UPTO'],
    'ap_citizen360.dim_village': ['VILLAGE_NAME'],
    'ap_citizen360.fact_entitlement': ['ANNUAL_BENEFIT', 'ENROLLMENT_STATUS'],
    'ap_citizen360.fact_population_hierarchy': ['GENDER', 'GEO_LEVEL', 'SOCIAL_CATEGORY'],
    'ap_citizen360.fact_scheme_disbursement': ['AMOUNT_BC', 'AMOUNT_OC', 'AMOUNT_OTHERS', 'AMOUNT_SC', 'AMOUNT_ST', 'BENEFICIARIES', 'FISCAL_YEAR', 'GEO_LEVEL', 'TOTAL_CRORES'],
    'ap_community360.dim_facility': ['ADDRESS_LINE', 'BOUNDARY_WKT', 'CONTACT_EMAIL', 'CONTACT_PHONE', 'FACILITY_CATEGORY', 'FACILITY_NAME', 'FACILITY_SHORT_NAME', 'GEOHASH', 'GOLDEN_SOURCE', 'H3_INDEX', 'IS_CURRENT', 'LOCALITY', 'MANAGING_AUTHORITY', 'OPERATIONAL_STATUS', 'OWNERSHIP_TYPE', 'RECORD_STATUS', 'SOURCE_SYSTEM', 'VALID_FROM', 'VALID_TO', 'VERIFICATION_STATUS', 'WEBSITE'],
    'ap_community360.dim_facility_anganwadi': ['BUILDING_TYPE', 'CENTER_TYPE', 'HAS_DRINKING_WATER', 'HAS_ELECTRICITY', 'HAS_KITCHEN', 'HAS_PRESCHOOL_KIT', 'HAS_TOILET', 'HELPER_PRESENT', 'PROJECT_NAME', 'RECORD_STATUS', 'REGISTERED_CHILDREN', 'REGISTERED_LACTATING_MOTHERS', 'REGISTERED_PREGNANT_WOMEN', 'SECTOR_NAME', 'SERVES_HOT_MEAL', 'SOURCE_SYSTEM', 'WORKER_PRESENT'],
    'ap_community360.dim_facility_identifier': ['CONFIDENCE_SCORE', 'IDENTIFIER_TYPE', 'IDENTIFIER_VALUE_HASH', 'ID_CLASS', 'IS_ACTIVE', 'MATCH_METHOD', 'RECORD_STATUS', 'SOURCE_SYSTEM', 'VALID_FROM', 'VALID_TO'],
    'ap_community360.dim_facility_school': ['ACADEMIC_SESSION', 'BOARD_AFFILIATION', 'BUILDING_STATUS', 'CLASSROOMS_GOOD_CONDITION', 'GENDER_TYPE', 'HAS_BOUNDARY_WALL', 'HAS_BOYS_TOILET', 'HAS_COMPUTER_LAB', 'HAS_CWSN_TOILET', 'HAS_DRINKING_WATER', 'HAS_ELECTRICITY', 'HAS_GIRLS_TOILET', 'HAS_LIBRARY', 'HAS_MIDDAY_MEAL', 'HAS_PLAYGROUND', 'HAS_RAMP', 'HAS_SMART_CLASSROOM', 'HIGHEST_CLASS', 'INTERNET_AVAILABLE', 'LOWEST_CLASS', 'MEDIUM_OF_INSTRUCTION', 'RECORD_STATUS', 'SANCTIONED_TEACHERS', 'SCHOOL_CATEGORY', 'SCHOOL_MANAGEMENT', 'SOURCE_SYSTEM', 'STUDENT_TEACHER_RATIO', 'TOTAL_BOYS', 'TOTAL_CLASSROOMS', 'TOTAL_GIRLS', 'TOTAL_STUDENTS', 'TOTAL_TEACHERS'],
    'ap_community360.dim_facility_type': ['DESCRIPTION', 'GOVERNING_DEPARTMENT', 'IS_ACTIVE', 'RECORD_STATUS', 'SECTOR', 'SERVICE_NORM_RADIUS_KM', 'SOURCE_SYSTEM', 'SUBTYPE_TABLE', 'TYPE_CATEGORY', 'TYPE_NAME'],
    'ap_community360.dim_geography': ['AREA_SQKM', 'ASSEMBLY_CONSTITUENCY', 'BOUNDARY_WKT', 'DISTRICT_NAME', 'GEO_BUSINESS_KEY', 'GEO_LEVEL', 'GRAM_PANCHAYAT', 'MANDAL_NAME', 'PARLIAMENT_CONSTITUENCY', 'RECORD_STATUS', 'REVENUE_DIVISION', 'SOURCE_SYSTEM', 'STATE_NAME', 'ULB_NAME', 'ULB_TYPE', 'VILLAGE_HABITATION', 'WARD_NAME'],
    'ap_community360.fact_facility_service': ['BENEFICIARIES_SERVED', 'OCCUPANCY_PCT', 'PERIOD_GRAIN', 'SOURCE_SYSTEM', 'THROUGHPUT_UNITS', 'UTILIZATION_INDEX'],
}


def main():
    print("=" * 80)
    print("🔍 DISTINCT VALUES EXTRACTOR (CATEGORICAL COLUMNS)")
    print("=" * 80)
    
    try:
        executor = HiveExecutor()
        print("Successfully initialized Impala connection.\n")
        # Increase memory limit directly on the connection bypassing the SELECT validator
        conn = executor._get_connection()
        cursor = conn.cursor()
        cursor.execute("SET MEM_LIMIT='5g'")
        cursor.close()
        print("Memory limit increased to 5g.")
    except Exception as e:
        print(f"Failed to initialize HiveExecutor: {e}")
        return

    output_file = "impala_distinct_values.txt"
    total_queries = sum(len(cols) for cols in CATEGORICAL_COLUMNS.values())
    current_query = 0
    
    with open(output_file, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("DISTINCT VALUES REPORT\n")
        f.write("=" * 80 + "\n\n")
        
        conn = executor._get_connection()
        cursor = conn.cursor()
        cursor.execute("SET MEM_LIMIT='4g'")
        
        for table, columns in CATEGORICAL_COLUMNS.items():
            f.write("-" * 80 + "\n")
            f.write(f"Table: {table}\n")
            f.write("-" * 80 + "\n")
            
            for col in columns:
                current_query += 1
                print(f"[{current_query}/{total_queries}] Querying {table}.{col} ...", end=" ", flush=True)
                
                query = f"SELECT {col}, COUNT(*) as cnt FROM {table} GROUP BY {col} ORDER BY cnt DESC LIMIT 200"
                try:
                    cursor.execute(query)
                
                    raw_rows = cursor.fetchall()
                
                    if not raw_rows:
                        f.write(f"\nColumn: {col}\n")
                        f.write("  (No data or table empty)\n")
                        print("Empty")
                    else:
                        f.write(f"\nColumn: {col} (Top distinct values by frequency):\n")
                
                        for value, cnt in raw_rows:
                            if value is None:
                                value = "NULL"
                
                            f.write(f"  - {value}: {cnt}\n")
                
                        if len(raw_rows) == 200:
                            f.write("  ... (Truncated to top 200 values)\n")
                
                        print("Done")
                
                except Exception as e:
                    f.write(f"\nColumn: {col}\n")
                    f.write(f"  Error querying: {str(e)}\n")
                    print("Error")
  
            f.write("\n")
        cursor.close()

    print("\n" + "=" * 80)
    print(f"Done. Results written to {output_file}")
    print("=" * 80)

if __name__ == "__main__":
    main()
