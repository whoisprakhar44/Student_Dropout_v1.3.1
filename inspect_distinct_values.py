import os
import sys

# Add the project root to sys.path so we can import MCP.hive_executor
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from MCP.hive_executor import HiveExecutor

# Dictionary of categorical columns extracted from impala_tables_sample.txt
CATEGORICAL_COLUMNS = {
    'curated_datamodels.absent_reason_dim': ['REASON_CODE', 'REASON_CATEGORY', 'IS_GOVT_APPROVED', 'IS_ACTIVE', 'IS_CURRENT'],
    'curated_datamodels.citizen_address_master': ['LGD_DIST_CODE', 'LGD_MANDAL_CODE', 'SECRETARIAT_CODE', 'RURAL_URBAN_FLAG', 'PIN_CODE', 'IS_PRIMARY'],
    'curated_datamodels.citizen_agriculture_land': ['VILLAGE_CODE', 'CROP_TYPE', 'CULTIVATOR_TYPE'],
    'curated_datamodels.citizen_asset_electricity': ['METER_TYPE', 'CATEGORY_DESCRIPTION'],
    'curated_datamodels.citizen_asset_vaahan': ['MODEL', 'FUEL_TYPE'],
    'curated_datamodels.citizen_asset_vaahan_type': ['CLASS_TYPE', 'TRANSPORT_CATEGORY'],
    'curated_datamodels.citizen_document': ['STATUS', 'UID_FLAG'],
    'curated_datamodels.citizen_document_testing': ['STATUS', 'UID_FLAG'],
    'curated_datamodels.citizen_education': ['QUALIFICATION_LEVEL', 'INSTITUTION_CODE', 'SCHOLARSHIP_SCHEME', 'CURRENT_QUALIFICATION_FLAG', 'MODE_OF_STUDY', 'MEDIUM_OF_INSTRUCTION'],
    'curated_datamodels.citizen_family_master': ['IS_HOFAMILY', 'IS_MEMBERADDED', 'IS_MEMBERDELETED', 'IS_MARRIED', 'HH_UPDATE_STATUS'],
    'curated_datamodels.citizen_health_schemes_master': ['SCHEME_TYPE', 'CATEGORY', 'SUB_CATEGORY', 'SCHEME_CODE', 'SCHEME_ACTIVE_STATUS', 'SCHEME_BENEFITS'],
    'curated_datamodels.citizen_master': ['GENDER', 'MARITAL_STATUS', 'RESIDENCY_STATUS', 'STATUS_CODE', 'RELIGION', 'CASTE'],
    'curated_datamodels.citizen_school': ['SCHOOL_DEPT_CODE', 'SCHOOL_UDISE_CODE', 'DISTRICT_LGD_CODE', 'MANDAL_LGD_CODE', 'VILLAGE_LGD_CODE', 'URBAN_RURAL_FLAG', 'FUNCTIONAL_STATUS', 'PRE_PRIMARY_FLAG', 'VOCATIONAL_FLAG', 'BUILDING_STATUS', 'ELECTRICITY_AVAILABILITY_FLAG', 'DRINKING_WATER_AVAILABILITY_FLAG', 'TOILET_BOYS_FLAG', 'TOILET_GIRLS_FLAG', 'ICT_ENABLED_FLAG', 'PLAYGROUND_FLAG', 'FIRE_SAFETY_FLAG', 'HEALTH_SAFETY_FLAG', 'IS_CURRENT'],
    'curated_datamodels.citizen_school_teacher': ['NATIONAL_TEACHER_CODE', 'GENDER', 'EMPLOYMENT_TYPE', 'IS_SINGLE_PARENT', 'DISABILITY_CATEGORY', 'TET_PASSED_FLAG', 'SERVICE_STATUS', 'PRESENT_DESIGNATION_TEACHING_TYPE', 'IS_CURRENT'],
    'curated_datamodels.citizen_student': ['GENDER', 'SOCIAL_CATEGORY', 'DISABILITY_FLAG', 'ADMISSION_FLAG', 'MEDIUM_KEY', 'IS_CURRENT', 'IS_CURRENT_FLAG'],
    'curated_datamodels.citizen_utility_connection': ['GAS_CONNECTION_STATUS', 'ELECTRICITY_CONNECTION_STATUS', 'WATER_CONNECTION_STATUS'],
    'curated_datamodels.citizen_welfare_schemes_master': ['CATEGORY', 'SUB_CATEGORY', 'SCHEME_CODE', 'SCHEME_ACTIVE_STATUS', 'SCHEME_BENEFITS', 'SCHEME_ELIGIBILITY_CONDITION1', 'SCHEME_ELIGIBILITY_CONDITION2'],
    'curated_datamodels.meal_type_dim': ['MEAL_TYPE_CODE', 'IS_COMPULSORY', 'IS_ACTIVE', 'IS_CURRENT'],
    'curated_datamodels.mid_day_meal_serving_fact': ['MEAL_SERVED_FLAG', 'HYGIENE_COMPLIANT_FLAG', 'FOOD_TASTED_FLAG', 'TEACHER_SUPERVISED_FLAG', 'MEDICAL_INCIDENT_REPORTED_FLAG', 'INSPECTION_REMARKS_CODE', 'GEO_TAGGED_FLAG', 'PHOTO_CAPTURED_FLAG', 'SUPPLY_SHORTAGE_FLAG'],
    'curated_datamodels.ration_card_citizen': ['STATUS_CODE'],
    'curated_datamodels.ration_card_family': ['CARD_TYPE_CODE', 'ISSUING_DISTRICT_CODE', 'FPS_CODE', 'STATUS_CODE'],
    'curated_datamodels.ration_card_type': ['CARD_TYPE_DESCRIPTION', 'CARD_TYPE_CODE'],
    'curated_datamodels.school_academic_performance_fact': ['PASS_FLAG', 'FAIL_FLAG', 'ABSENT_FLAG', 'WITHHELD_FLAG', 'EXAM_TYPE', 'EVALUATION_TYPE', 'MEDIUM_OF_EXAM', 'YEAR_ON_YEAR_IMPROVEMENT_FLAG'],
    'curated_datamodels.school_category': ['CATEGORY_CODE', 'CATEGORY_TYPE', 'UDISE_TYPE'],
    'curated_datamodels.school_medium': ['MEDIUM_CODE'],
    'curated_datamodels.school_student_attendance_fact': ['PRESENT_FLAG', 'ABSENT_FLAG', 'HALF_DAY_FLAG', 'ATTENDANCE_STATUS_CODE', 'ATTENDANCE_REASON_CODE', 'MARKED_BY_ROLE', 'MDM_ELIGIBLE_FLAG', 'MEALS_CONSUMED_FLAG', 'EGGS_ELIGIBLE_FLAG', 'CHIKKI_ELIGIBLE_FLAG', 'RAGI_JAVA_ELIGIBLE_FLAG', 'HM_APPROVAL_FLAG', 'IMAGE_AVAILABLE_FLAG'],
    'curated_datamodels.school_subject_master': ['SUBJECT_CODE', 'SUBJECT_CATEGORY', 'SUBJECT_TYPE', 'IS_VOCATIONAL_FLAG', 'IS_SKILL_SUBJECT_FLAG', 'IS_COMPULSORY_FLAG', 'BOARD_CODE', 'MARKS_SCHEME', 'SUBJECT_STATUS'],
    'curated_datamodels.student_class_dim': ['CLASS_CODE', 'IS_ACTIVE'],
    'curated_datamodels.assessment_dim': ['assessment_code', 'assessment_type', 'board_code', 'grade_scheme', 'is_summative', 'is_active', 'is_current'],
    'curated_datamodels.beneficiary_type_dim': ['beneficiary_type_code', 'is_active', 'is_current'],
    'curated_datamodels.benefit_type_dim': ['benefit_type_code', 'delivery_mode', 'is_monetary', 'is_active', 'is_current'],
    'curated_datamodels.citizen_address_master_test': ['pin_code', 'is_primary', 'is_current', 'is_deleted'],
    'curated_datamodels.citizen_bank_accounts': ['bank_type', 'bank_ifsc_code'],
    'curated_datamodels.citizen_consent': ['is_revocable'],
    'curated_datamodels.citizen_land': ['land_type', 'soil_type', 'irrigation_type', 'encumbrance_status'],
    'curated_datamodels.citizen_property': ['property_type', 'owner_type'],
    'curated_datamodels.health_scheme_code': ['health_scheme_code'],
    'curated_datamodels.infrastructure_category_dim': ['infra_category_code', 'is_active', 'is_current'],
    'curated_datamodels.infrastructure_component_dim': ['infra_component_code', 'unit_type', 'is_functional_track', 'is_active', 'is_current'],
    'curated_datamodels.nutrition_item_dim': ['item_code', 'nutrition_category', 'is_active', 'is_current'],
    'curated_datamodels.ration_card_citizen_reason': ['reason_description', 'reason_code'],
    'curated_datamodels.scheme_benefits_fact': ['social_category', 'eligible_flag', 'attendance_eligible_flag', 'benefit_delivered_flag', 'delivery_mode', 'eligible_beneficiary_flag', 'benefit_sanctioned_flag', 'benefit_disbursed_flag', 'benefit_rejected_flag', 'benefit_withheld_flag', 'rejection_reason_code', 'payment_failure_reason_code', 'aadhaar_seeded_flag', 'bank_account_verified_flag', 'kyc_completed_flag', 'girl_child_flag', 'cwsn_flag', 'bgm_eligible_flag', 'scheme_uptake_rate'],
    'curated_datamodels.school_infra_category_dim': ['school_infra_category_code', 'is_active', 'is_current'],
    'curated_datamodels.school_infra_component_dim': ['component_code', 'measurement_type', 'is_digital', 'is_active', 'is_current'],
    'curated_datamodels.school_infrastructure_progress_fact': ['work_status', 'delay_reason_code', 'is_structurally_certified_flag', 'is_safety_compliant_flag', 'is_functional_flag', 'maintenance_required_flag', 'geo_tagged_flag', 'inspection_remarks_code'],
    'curated_datamodels.school_meal_menu_dim': ['weekday_code', 'is_planned', 'is_active', 'is_current'],
    'curated_datamodels.school_scheme_master': ['scheme_code', 'scheme_category', 'applicable_level', 'delivery_mode', 'scheme_status', 'is_current', 'is_active'],
    'curated_datamodels.school_teacher_attendance_fact': ['present_flag', 'on_leave_flag', 'on_duty_flag', 'late_flag', 'leave_type', 'approved_leave_flag', 'attendance_status_code', 'image_available_flag', 'approval_status_code', 'approval_role'],
    'curated_datamodels.source_department_code': ['source_department_code']
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
        cursor.execute("SET MEM_LIMIT='4g'")
        cursor.close()
        print("Memory limit increased to 4g.")
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
                    description = cursor.description or []
                    col_names = [c[0] for c in description]
                    raw_rows = cursor.fetchall()
                    
                    if not raw_rows:
                        f.write(f"\nColumn: {col}\n")
                        f.write("  (No data or table empty)\n")
                        print("Empty")
                    else:
                        f.write(f"\nColumn: {col} (Top distinct values by frequency):\n")
                        for row in raw_rows:
                            row_dict = dict(zip(col_names, row))
                            val = row_dict.get(col)
                            cnt = row_dict.get('cnt')
                            f.write(f"  - {val}: {cnt}\n")
                        
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
