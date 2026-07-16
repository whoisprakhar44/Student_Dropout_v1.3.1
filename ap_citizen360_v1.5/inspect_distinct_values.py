import os
import sys

# Add the project root to sys.path so we can import MCP.hive_executor
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from MCP.hive_executor import HiveExecutor

# Dictionary of categorical columns extracted from impala_tables_sample.txt
CATEGORICAL_COLUMNS = {
    "ap_citizen360.dim_agriculture_profile": [
        "AADHAAR_MAPPED",
        "CROP_SEASON",
        "FARMER_TYPE",
        "IRRIGATION_SOURCE",
        "KCC_BANK",
        "MARKET_LINKAGE",
        "PMFBY_ENROLLED",
        "PM_KISAN_BENEFICIARY",
        "PRIMARY_CROP",
        "RYTHU_BHAROSA_BENEFICIARY",
        "SECONDARY_CROP"
    ],
    "ap_citizen360.dim_citizen_identifier": [
        "IDENTIFIER_TYPE",
        "IS_ACTIVE",
        "IS_PRIMARY",
        "SOURCE",
        "VERIFIED_FLAG"
    ],
    "ap_citizen360.dim_consent": [
        "is_revocable"
    ],
    "ap_citizen360.dim_department_client": [
        "IS_ACTIVE"
    ],
    "ap_citizen360.dim_district": [
        "IS_CURRENT"
    ],
    "ap_citizen360.dim_family_member": [
        "GENDER"
    ],
    "ap_citizen360.dim_health_profile": [
        "AAROGYASRI_STATUS",
        "BLOOD_GROUP",
        "CGHS_COVERED",
        "COVID_DOSES",
        "COVID_VACCINATED",
        "ESI_COVERED",
        "HAS_CANCER",
        "HAS_DIABETES",
        "HAS_HIV",
        "HAS_HYPERTENSION",
        "HAS_MENTAL_HEALTH_CONDITION",
        "HAS_TUBERCULOSIS",
        "INSTITUTIONAL_DELIVERY",
        "IS_PREGNANT",
        "MENTAL_HEALTH_TYPE",
        "RSBY_COVERED"
    ],
    "ap_citizen360.dim_household": [
        "DWELLING_TYPE",
        "HEAD_GENDER",
        "HOUSEHOLD_INCOME_CATEGORY",
        "INCOME_BAND",
        "RATION_CARD_TYPE",
        "SOCIAL_CATEGORY"
    ],
    "ap_citizen360.dim_land": [
        "AADHAAR_MAPPED",
        "ENCUMBRANCE_STATUS",
        "IRRIGATION_TYPE",
        "IS_ASSIGNED_LAND",
        "LAND_TYPE",
        "SOIL_TYPE"
    ],
    "ap_citizen360.dim_occupation": [
        "EMPLOYMENT_STATUS",
        "IS_CURRENT",
        "OCCUPATION_TYPE",
        "SOURCE"
    ],
    "ap_citizen360.dim_person": [
        "CASTE_DERIVED_FLAG",
        "CASTE_NAME",
        "DOMICILE_STATUS",
        "DWELLING_TYPE",
        "GENDER",
        "GOVT_EMPLOYMENT_TYPE",
        "INCOME_BAND",
        "IS_DECEASED",
        "MARITAL_STATUS",
        "RELIGION",
        "RURAL_URBAN_FLAG",
        "SOCIAL_CATEGORY"
    ],
    "ap_citizen360.dim_property": [
        "AADHAAR_MAPPED",
        "CONSTRUCTION_TYPE",
        "MUNICIPAL_BODY",
        "PROPERTY_SUB_TYPE",
        "PROPERTY_TYPE",
        "ROOF_TYPE",
        "USAGE_TYPE"
    ],
    "ap_citizen360.dim_property_tax": [
        "exemption_category",
        "municipal_body",
        "payment_mode",
        "tax_status"
    ],
    "ap_citizen360.dim_scheme": [
        "BENEFIT_TYPE"
    ],
    "ap_citizen360.dim_social_welfare": [
        "disability_type",
        "is_disabled",
        "ntr_bharosa_flag",
        "pension_status",
        "pension_type",
        "shg_role"
    ],
    "ap_citizen360.dim_state": [
        "IS_CURRENT"
    ],
    "ap_citizen360.dim_student": [
        "AADHAAR_SEEDED",
        "DIGITAL_LITERACY_LEVEL",
        "DROPOUT_REASON",
        "EDUCATION_LEVEL",
        "IS_CURRENT_LEVEL",
        "IS_DROPOUT",
        "MEDIUM_OF_INSTRUCTION",
        "NTR_VIDYA_DEEVENA",
        "POST_MATRIC_SCHOLARSHIP",
        "PRE_MATRIC_SCHOLARSHIP",
        "THALLIKI_VANDANAM"
    ],
    "ap_citizen360.dim_tax_profile": [
        "GST_PAID_ANNUAL"
    ],
    "ap_citizen360.dim_utility_connection": [
        "ELECTRICITY_STATUS",
        "ELECTRICITY_STATUS_UPDATED_ON",
        "GAS_CONNECTION_STATUS",
        "WATER_CONNECTION_STATUS"
    ],
    "ap_citizen360.dim_vehicle": [
        "COLOR",
        "DATA_SOURCE",
        "FUEL_TYPE",
        "MAKE",
        "MODEL",
        "RTO_OFFICE",
        "VEHICLE_TYPE"
    ],
    "ap_citizen360.dim_vehicle_compliance": [
        "CHALLAN_PENDING",
        "HSRP_ISSUED",
        "HYPOTHECATION_STATUS",
        "INSURANCE_COMPANY",
        "PERMIT_TYPE"
    ],
    "ap_citizen360.fact_entitlement": [
        "ENROLLMENT_STATUS"
    ],
    "ap_citizen360.fact_population_hierarchy": [
        "GENDER",
        "GEO_LEVEL",
        "SOCIAL_CATEGORY"
    ],
    "ap_citizen360.fact_scheme_disbursement": [
        "GEO_LEVEL"
    ],
    "ap_community360.dim_facility": [
        "FACILITY_CATEGORY",
        "GOLDEN_SOURCE",
        "IS_CURRENT",
        "OPERATIONAL_STATUS",
        "OWNERSHIP_TYPE",
        "RECORD_STATUS",
        "SOURCE_SYSTEM",
        "VERIFICATION_STATUS"
    ],
    "ap_community360.dim_facility_anganwadi": [
        "building_type",
        "center_type",
        "has_drinking_water",
        "has_electricity",
        "has_kitchen",
        "has_preschool_kit",
        "has_toilet",
        "record_status",
        "source_system"
    ],
    "ap_community360.dim_facility_community_center": [
        "center_type",
        "has_ac",
        "has_kitchen",
        "has_parking",
        "has_power_backup",
        "has_stage",
        "has_toilets",
        "is_disabled_friendly",
        "record_status",
        "source_system"
    ],
    "ap_community360.dim_facility_hospital": [
        "facility_level",
        "has_ambulance",
        "has_blood_bank",
        "has_diagnostic_lab",
        "has_emergency_services",
        "has_operation_theatre",
        "has_pharmacy",
        "is_24x7",
        "is_aarogyasri_empanelled",
        "is_pmjay_empanelled",
        "record_status",
        "source_system"
    ],
    "ap_community360.dim_facility_identifier": [
        "IDENTIFIER_TYPE",
        "IS_ACTIVE",
        "RECORD_STATUS",
        "SOURCE_SYSTEM"
    ],
    "ap_community360.dim_facility_park": [
        "has_childrens_play_area",
        "has_drinking_water",
        "has_lighting",
        "has_open_gym",
        "has_parking",
        "has_seating",
        "has_toilets",
        "has_walking_track",
        "has_water_body",
        "is_free_entry",
        "park_type",
        "record_status",
        "source_system"
    ],
    "ap_community360.dim_facility_school": [
        "BOARD_AFFILIATION",
        "BUILDING_STATUS",
        "GENDER_TYPE",
        "HAS_BOUNDARY_WALL",
        "HAS_BOYS_TOILET",
        "HAS_COMPUTER_LAB",
        "HAS_CWSN_TOILET",
        "HAS_DRINKING_WATER",
        "HAS_ELECTRICITY",
        "HAS_GIRLS_TOILET",
        "HAS_LIBRARY",
        "HAS_MIDDAY_MEAL",
        "HAS_PLAYGROUND",
        "HAS_RAMP",
        "HAS_SMART_CLASSROOM",
        "INTERNET_AVAILABLE",
        "MEDIUM_OF_INSTRUCTION",
        "RECORD_STATUS",
        "SCHOOL_CATEGORY",
        "SOURCE_SYSTEM"
    ],
    "ap_community360.dim_facility_type": [
        "IS_ACTIVE",
        "RECORD_STATUS",
        "SOURCE_SYSTEM",
        "SUBTYPE_TABLE",
        "TYPE_CATEGORY",
        "TYPE_CODE"
    ],
    "ap_community360.dim_geography": [
        "GEO_LEVEL",
        "RECORD_STATUS",
        "SOURCE_SYSTEM",
        "ULB_TYPE"
    ],
    "ap_community360.fact_facility_access": [
        "is_nearest_of_type",
        "source_system"
    ],
    "ap_community360.fact_facility_service": [
        "source_system"
    ]
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
