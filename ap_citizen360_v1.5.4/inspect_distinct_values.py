#!/usr/bin/env python3
import argparse
import os
import sys
import yaml
from pathlib import Path

# Add the project root to sys.path so we can import MCP.hive_executor
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from MCP.hive_executor import HiveExecutor

# Dictionary of categorical & dimensional columns for all 38 tables in ap_citizen360
CATEGORICAL_COLUMNS = {
    'ap_citizen360.dim_agriculture_profile': [
        'AADHAAR_MAPPED', 'CROP_SEASON', 'DEPARTMENT_ID', 'FARMER_TYPE',
        'FPO_NAME', 'IRRIGATION_SOURCE', 'KCC_BANK', 'MARKET_LINKAGE',
        'PMFBY_ENROLLED', 'PM_KISAN_BENEFICIARY', 'PRIMARY_CROP', 'RYTHU_BHAROSA_BENEFICIARY',
        'SECONDARY_CROP'
    ],
    'ap_citizen360.dim_citizen_identifier': [
        'IDENTIFIER_TYPE', 'IDENTIFIER_VALUE', 'ISSUING_AUTHORITY', 'IS_ACTIVE',
        'IS_PRIMARY', 'SOURCE', 'VERIFIED_FLAG'
    ],
    'ap_citizen360.dim_consent': [
        'IS_REVOCABLE', 'VALID_FROM', 'VALID_TO'
    ],
    'ap_citizen360.dim_crop_sale': [
        'AMT_NONPADDY', 'AMT_PADDY', 'AMT_TOTAL', 'FINANCIAL_YEAR'
    ],
    'ap_citizen360.dim_department': [
        'DEPARTMENT_ID', 'DEPARTMENT_NAME'
    ],
    'ap_citizen360.dim_department_client': [
        'CLIENT_SECRET_HASH', 'DEPARTMENT_ID', 'IS_ACTIVE'
    ],
    'ap_citizen360.dim_district': [
        'DISTRICT_NAME', 'EFFECTIVE_FROM', 'EFFECTIVE_TO', 'ELECTRICITY_CONSUMERS',
        'GAS_CONNECTIONS', 'IS_CURRENT', 'LITERACY_RATE', 'PROPERTIES',
        'PROPERTY_TAX_COVERAGE', 'RATION_AAY', 'RATION_CARDS_TOTAL', 'RATION_NPHH',
        'RATION_OTHERS', 'RATION_PHH', 'SEX_RATIO', 'URBANIZATION_PCT', 'VEHICLES'
    ],
    'ap_citizen360.dim_driving_licence': [
        'DC_COVCD', 'TRANSPORT_VALIDITY_FROM', 'VE_CATG'
    ],
    'ap_citizen360.dim_epfo_contribution': [
        'EMPLOYEE_CONTRIBUTION', 'EMPLOYER_CONTRIBUTION', 'EPS_CONTRIBUTION', 'SECRETARIAT_CODE'
    ],
    'ap_citizen360.dim_family_member': [
        'GENDER', 'MEMBER_NAME', 'RELATION'
    ],
    'ap_citizen360.dim_health_profile': [
        'AAROGYASRI_STATUS', 'ABHA_ADDRESS', 'ANC_REGISTRATIONS', 'ASSIGNED_ASHA_WORKER',
        'BLOOD_GROUP', 'BMI', 'CGHS_COVERED', 'COVID_DOSES', 'COVID_VACCINATED',
        'DEPARTMENT_ID', 'ESI_COVERED', 'HAS_CANCER', 'HAS_DIABETES', 'HAS_HIV',
        'HAS_HYPERTENSION', 'HAS_MENTAL_HEALTH_CONDITION', 'HAS_TUBERCULOSIS', 'HEIGHT_CM',
        'INSTITUTIONAL_DELIVERY', 'IS_PREGNANT', 'MENTAL_HEALTH_TYPE', 'REGISTERED_PHC',
        'RSBY_COVERED', 'WEIGHT_KG'
    ],
    'ap_citizen360.dim_household': [
        'DWELLING_TYPE', 'HEAD_GENDER', 'HEAD_NAME', 'HOUSEHOLD_INCOME_CATEGORY',
        'INCOME_BAND', 'RATION_CARD_TYPE', 'SOCIAL_CATEGORY', 'VILLAGE_NAME'
    ],
    'ap_citizen360.dim_land': [
        'AADHAAR_MAPPED', 'ENCUMBRANCE_STATUS', 'EXTENT_DRY_LAND', 'EXTENT_WET_LAND',
        'GUIDELINE_VALUE', 'IRRIGATION_TYPE', 'IS_ASSIGNED_LAND', 'LAND_CLASSIFICATION',
        'LAND_TYPE', 'LOCATION', 'MARKET_VALUE', 'MORTGAGE_BANK', 'REVENUE_CIRCLE',
        'SOIL_TYPE', 'SRO_OFFICE', 'STAMP_DUTY_PAID', 'VILLAGE_NAME'
    ],
    'ap_citizen360.dim_mandal': [
        'MANDAL_NAME'
    ],
    'ap_citizen360.dim_occupation': [
        'DESIGNATION', 'EMPLOYER_NAME', 'EMPLOYMENT_STATUS', 'IS_CURRENT',
        'OCCUPATION_SECTOR', 'OCCUPATION_TYPE', 'OCCUPATION_YEAR', 'SOURCE'
    ],
    'ap_citizen360.dim_person': [
        'CASTE_DERIVED_FLAG', 'CASTE_NAME', 'DISABILITY_PERCENTAGE', 'DISABILITY_STATUS',
        'DISABILITY_TYPE', 'DOMICILE_STATUS', 'DWELLING_TYPE', 'FATHER_NAME',
        'GENDER', 'GOVT_EMPLOYMENT_TYPE', 'HUSBAND_NAME', 'INCOME_BAND',
        'IS_DECEASED', 'MARITAL_STATUS', 'MOTHER_NAME', 'PERSON_NAME',
        'RELIGION', 'RURAL_URBAN_FLAG', 'SECRETARIAT_CODE', 'SOCIAL_CATEGORY', 'VILLAGE_NAME'
    ],
    'ap_citizen360.dim_property': [
        'AADHAAR_MAPPED', 'AREA_SQ_FT', 'BUILT_UP_AREA_SQ_FT', 'CONSTRUCTION_TYPE',
        'CONSTRUCTION_YEAR', 'GUIDELINE_VALUE', 'LOCALITY', 'LOCATION',
        'MARKET_VALUE', 'MUNICIPAL_BODY', 'OWNER_NAME', 'PLINTH_AREA_UNITS',
        'PROPERTY_SUB_TYPE', 'PROPERTY_TYPE', 'PTIN', 'ROOF_TYPE',
        'SITE_AREA_SQ_FT', 'SITE_EXTENT_UNITS', 'SRO_OFFICE', 'STREET_NAME', 'USAGE_TYPE'
    ],
    'ap_citizen360.dim_property_tax': [
        'ASSESSMENT_YEAR', 'DEPARTMENT_ID', 'EXEMPTION_CATEGORY', 'MUNICIPAL_BODY',
        'PAYMENT_MODE', 'TAX_STATUS'
    ],
    'ap_citizen360.dim_scheme': [
        'BENEFIT_TYPE', 'DEPARTMENT_ID', 'SCHEME_NAME'
    ],
    'ap_citizen360.dim_scheme_main_mapping': [
        'MAIN_SCHEME_ID', 'SCHEME_ID'
    ],
    'ap_citizen360.dim_secretariat': [
        'SECRETARIAT_CODE', 'SECRETARIAT_NAME'
    ],
    'ap_citizen360.dim_social_welfare': [
        'BC_WELFARE_SCHEME', 'DEEPAM_BENEFICIARY', 'DEPARTMENT_ID', 'DISABILITY_PERCENTAGE',
        'DISABILITY_TYPE', 'IS_DISABLED', 'NTR_BHAROSA_FLAG', 'PENSION_BANK',
        'PENSION_STATUS', 'PENSION_TYPE', 'SHG_NAME', 'SHG_ROLE'
    ],
    'ap_citizen360.dim_state': [
        'EFFECTIVE_FROM', 'EFFECTIVE_TO', 'ELECTRICITY_CONSUMERS', 'GROSS_STATE_INCOME_CR',
        'IS_CURRENT', 'LITERACY_RATE', 'MEDIAN_AGE', 'PROPERTY_TAX_COLLECTED',
        'RATION_AAY', 'RATION_CARDS_TOTAL', 'RATION_NPHH', 'RATION_OTHERS',
        'RATION_PHH', 'SEX_RATIO', 'STATE_NAME', 'URBANIZATION_PCT'
    ],
    'ap_citizen360.dim_student': [
        'AADHAAR_SEEDED', 'ACADEMIC_YEAR', 'CLASS_CURRENTLY_ENROLLED', 'DIGITAL_LITERACY_LEVEL',
        'DROPOUT_REASON', 'EDUCATION_BOARD', 'EDUCATION_LEVEL', 'HIGHEST_QUALIFICATION',
        'IS_CURRENT_LEVEL', 'IS_DROPOUT', 'MEDIUM_OF_INSTRUCTION', 'NTR_VIDYA_DEEVENA',
        'POST_MATRIC_SCHOLARSHIP', 'PRE_MATRIC_SCHOLARSHIP', 'SCHOOL_NAME', 'STUDENT_PEN',
        'THALLIKI_VANDANAM'
    ],
    'ap_citizen360.dim_tax_profile': [
        'GST_PAID_ANNUAL', 'INCOME_TAX_PAID'
    ],
    'ap_citizen360.dim_utility_connection': [
        'DISCOM_NAME', 'ELECTRICITY_STATUS', 'ELECTRICITY_STATUS_UPDATED_ON',
        'GAS_CONNECTION_STATUS', 'WATER_CONNECTION_STATUS'
    ],
    'ap_citizen360.dim_vehicle': [
        'COLOR', 'DATA_SOURCE', 'FUEL_TYPE', 'LADEN_WEIGHT_KG',
        'MAKE', 'MODEL', 'OWNER_NAME', 'RTO_OFFICE',
        'SEATING_CAPACITY', 'UNLADEN_WEIGHT_KG', 'VEHICLE_CLASS', 'VEHICLE_TYPE',
        'YEAR_OF_MANUFACTURE'
    ],
    'ap_citizen360.dim_vehicle_compliance': [
        'CHALLAN_PENDING', 'FINANCER_NAME', 'FITNESS_VALID_TO', 'GREEN_TAX_DUE',
        'HSRP_ISSUED', 'HYPOTHECATION_STATUS', 'INSURANCE_COMPANY', 'INSURANCE_VALID_TO',
        'LOAN_OUTSTANDING', 'PERMIT_TYPE', 'PERMIT_VALID_TO', 'PUC_VALID_TO',
        'REGISTRATION_VALID_TO', 'TAX_PAID_UPTO'
    ],
    'ap_citizen360.dim_village': [
        'VILLAGE_NAME'
    ],
    'ap_citizen360.fact_benefit_transaction': [
        'DEPARTMENT_ID', 'DISTRICT_ID', 'SCHEME_ID', 'TRANSACTION_DATE'
    ],
    'ap_citizen360.fact_entitlement': [
        'ANNUAL_BENEFIT', 'DISTRICT_ID', 'ENROLLED_DATE', 'ENROLLMENT_STATUS', 'SCHEME_ID'
    ],
    'ap_citizen360.fact_event_acknowledgement': [
        'ACKNOWLEDGED_AT', 'DEPARTMENT_ID'
    ],
    'ap_citizen360.fact_event_details': [
        'DEPARTMENT_ID', 'DETECTED_AT', 'DISTRICT_ID', 'EVENT_TYPE',
        'LINKED_SCHEME_IDS', 'MANDAL_ID', 'RESOLUTION_STATUS', 'SEVERITY',
        'SUB_EVENT_TYPE', 'VILLAGE_NAME'
    ],
    'ap_citizen360.fact_event_index': [
        'DEPARTMENT_ID'
    ],
    'ap_citizen360.fact_event_request_registry': [
        'DEPARTMENT_ID'
    ],
    'ap_citizen360.fact_event_status_update': [
        'PROCESSING_STATUS', 'SOURCE'
    ],
    'ap_citizen360.fact_population_hierarchy': [
        'GENDER', 'GEO_LEVEL', 'SOCIAL_CATEGORY'
    ],
    'ap_citizen360.fact_scheme_disbursement': [
        'AMOUNT_BC', 'AMOUNT_OC', 'AMOUNT_OTHERS', 'AMOUNT_SC',
        'AMOUNT_ST', 'BENEFICIARIES', 'DEPARTMENT_ID', 'FISCAL_YEAR',
        'GEO_LEVEL', 'SCHEME_ID', 'TOTAL_CRORES'
    ],
}


def load_from_yamls(yaml_dir: Path) -> dict:
    """Auto-discover categorical and dimensional columns directly from YAML files."""
    cols_map = {}
    skip_cols = {
        'payload_json', 'eventdata', 'client_secret_hash', 'payload_hash',
        'metadata', 'details'
    }
    for p in sorted(yaml_dir.glob('*.yaml')):
        doc = yaml.safe_load(p.read_text(encoding='utf-8'))
        if not doc or not doc.get('table'):
            continue
        tname = f"ap_citizen360.{doc['table']}"
        cols = []
        for c in doc.get('columns', []):
            name = c.get('name', '')
            if name and name.lower() not in skip_cols:
                cols.append(name.upper())
        if cols:
            cols_map[tname] = sorted(cols)
    return cols_map


def main():
    parser = argparse.ArgumentParser(
        description="Inspect distinct values for categorical columns in Impala tables."
    )
    parser.add_argument(
        "--from-yamls", action="store_true",
        help="Dynamically load categorical columns from schema YAMLs instead of hardcoded list"
    )
    parser.add_argument(
        "--limit", type=int, default=200,
        help="Maximum distinct values to return per column (default: 200)"
    )
    parser.add_argument(
        "--output", type=str, default="impala_distinct_values.txt",
        help="Output report file path (default: impala_distinct_values.txt)"
    )
    args = parser.parse_args()

    yaml_tables_dir = PROJECT_ROOT / "schema" / "curated_datamodels" / "tables" / "ap_citizen360"
    if args.from_yamls:
        if not yaml_tables_dir.exists():
            print(f"Error: YAML directory not found: {yaml_tables_dir}")
            sys.exit(1)
        target_columns = load_from_yamls(yaml_tables_dir)
        print(f"Loaded {len(target_columns)} tables dynamically from schema YAMLs.")
    else:
        target_columns = CATEGORICAL_COLUMNS

    print("=" * 80)
    print("🔍 DISTINCT VALUES EXTRACTOR (CATEGORICAL COLUMNS)")
    print(f"Target Tables: {len(target_columns)}")
    print(f"Output File:   {args.output}")
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

    total_queries = sum(len(cols) for cols in target_columns.values())
    current_query = 0

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("DISTINCT VALUES REPORT\n")
        f.write("=" * 80 + "\n\n")

        conn = executor._get_connection()
        cursor = conn.cursor()
        cursor.execute("SET MEM_LIMIT='4g'")

        for table, columns in target_columns.items():
            f.write("-" * 80 + "\n")
            f.write(f"Table: {table}\n")
            f.write("-" * 80 + "\n")

            for col in columns:
                current_query += 1
                print(f"[{current_query}/{total_queries}] Querying {table}.{col} ...", end=" ", flush=True)

                query = f"SELECT {col}, COUNT(*) as cnt FROM {table} GROUP BY {col} ORDER BY cnt DESC LIMIT {args.limit}"
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

                        if len(raw_rows) == args.limit:
                            f.write(f"  ... (Truncated to top {args.limit} values)\n")

                        print("Done")

                except Exception as e:
                    f.write(f"\nColumn: {col}\n")
                    f.write(f"  Error querying: {str(e)}\n")
                    print("Error")

            f.write("\n")
        cursor.close()

    print("\n" + "=" * 80)
    print(f"Done. Results written to {args.output}")
    print("=" * 80)


if __name__ == "__main__":
    main()
