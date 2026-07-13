import os
import sys

# Add the project root to sys.path so we can import MCP.hive_executor
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from MCP.hive_executor import HiveExecutor

# Dictionary of categorical columns extracted from impala_tables_sample.txt
CATEGORICAL_COLUMNS = {
    'curated_datamodels.absent_reason_dim': ['IS_ACTIVE', 'IS_CURRENT', 'IS_GOVT_APPROVED', 'REASON_CATEGORY', 'REASON_CODE'],
    'curated_datamodels.assessment_dim': ['assessment_code', 'assessment_type', 'board_code', 'grade_scheme', 'is_active', 'is_current', 'is_summative'],
    'curated_datamodels.beneficiary_type_dim': ['beneficiary_type_code', 'is_active', 'is_current'],
    'curated_datamodels.benefit_type_dim': ['benefit_type_code', 'delivery_mode', 'is_active', 'is_current', 'is_monetary'],
    'curated_datamodels.citizen_address_master': ['ADDRESS_STATUS_CODE', 'ADDRESS_TYPE', 'IS_PRIMARY', 'LGD_DIST_CODE', 'LGD_MANDAL_CODE', 'PIN_CODE', 'RURAL_URBAN_FLAG', 'SECRETARIAT_CODE'],
    'curated_datamodels.citizen_address_master_test': ['is_current', 'is_deleted', 'is_primary', 'pin_code'],
    'curated_datamodels.citizen_agriculture_land': ['CROP_TYPE', 'CULTIVATOR_TYPE', 'VILLAGE_CODE'],
    'curated_datamodels.citizen_asset_electricity': ['CATEGORY_DESCRIPTION', 'METER_TYPE'],
    'curated_datamodels.citizen_asset_vaahan': ['FUEL_TYPE', 'MODEL'],
    'curated_datamodels.citizen_asset_vaahan_type': ['CLASS_DESCRIPTION', 'CLASS_TYPE', 'CONVERTIBLE_CLASSES', 'TRANSPORT_CATEGORY'],
    'curated_datamodels.citizen_bank_accounts': ['bank_ifsc_code', 'bank_type'],
    'curated_datamodels.citizen_consent': ['is_revocable'],
    'curated_datamodels.citizen_document': ['STATUS', 'UID_FLAG'],
    'curated_datamodels.citizen_document_testing': ['STATUS', 'UID_FLAG'],
    'curated_datamodels.citizen_education': ['CURRENT_QUALIFICATION_FLAG', 'INSTITUTION_CODE', 'MEDIUM_OF_INSTRUCTION', 'MODE_OF_STUDY', 'QUALIFICATION_LEVEL', 'SCHOLARSHIP_SCHEME'],
    'curated_datamodels.citizen_family_master': ['HH_UPDATE_STATUS', 'IS_HOFAMILY', 'IS_MARRIED', 'IS_MEMBERADDED', 'IS_MEMBERDELETED'],
    'curated_datamodels.citizen_health_schemes_master': ['CATEGORY', 'SCHEME_ACTIVE_STATUS', 'SCHEME_BENEFITS', 'SCHEME_CODE', 'SCHEME_TYPE', 'SUB_CATEGORY'],
    'curated_datamodels.citizen_idty_type': ['CITIZEN_IDTY_TYPE', 'IDTY_DESCRIPTION'],
    'curated_datamodels.citizen_land': ['encumbrance_status', 'irrigation_type', 'land_type', 'soil_type'],
    'curated_datamodels.citizen_master': ['CASTE', 'GENDER', 'MARITAL_STATUS', 'RELIGION', 'RESIDENCY_STATUS', 'STATUS_CODE'],
    'curated_datamodels.citizen_property': ['owner_type', 'property_type'],
    'curated_datamodels.citizen_school': ['BUILDING_STATUS', 'DISTRICT_LGD_CODE', 'DRINKING_WATER_AVAILABILITY_FLAG', 'ELECTRICITY_AVAILABILITY_FLAG', 'FIRE_SAFETY_FLAG', 'FUNCTIONAL_STATUS', 'HEALTH_SAFETY_FLAG', 'ICT_ENABLED_FLAG', 'IS_CURRENT', 'MANDAL_LGD_CODE', 'MAX_CLASS', 'MIN_CLASS', 'NOC_AVAILABLE_FLAG', 'NOC_REQUIRED_FLAG', 'PLAYGROUND_FLAG', 'PRE_PRIMARY_FLAG', 'SCHOOL_DEPT_CODE', 'SCHOOL_UDISE_CODE', 'TOILET_BOYS_FLAG', 'TOILET_GIRLS_FLAG', 'URBAN_RURAL_FLAG', 'VILLAGE_LGD_CODE', 'VOCATIONAL_FLAG'],
    'curated_datamodels.citizen_school_teacher': ['DISABILITY_CATEGORY', 'EMPLOYMENT_TYPE', 'GENDER', 'IS_CURRENT', 'IS_SINGLE_PARENT', 'NATIONAL_TEACHER_CODE', 'PRESENT_DESIGNATION_TEACHING_TYPE', 'SERVICE_STATUS', 'SUBJECT_SPECIALIZATION_KEY', 'TET_PASSED_FLAG'],
    'curated_datamodels.citizen_student': ['ADMISSION_FLAG', 'DISABILITY_FLAG', 'GENDER', 'IS_CURRENT', 'IS_CURRENT_FLAG', 'MEDIUM_KEY', 'MINORITY_STATUS', 'SOCIAL_CATEGORY', 'STATUS_LEVEL_1', 'STATUS_LEVEL_2'],
    'curated_datamodels.citizen_utility_connection': ['ELECTRICITY_CONNECTION_STATUS', 'GAS_CONNECTION_STATUS', 'WATER_CONNECTION_STATUS'],
    'curated_datamodels.citizen_welfare_schemes_master': ['CATEGORY', 'SCHEME_ACTIVE_STATUS', 'SCHEME_BENEFITS', 'SCHEME_CODE', 'SCHEME_ELIGIBILITY_CONDITION1', 'SCHEME_ELIGIBILITY_CONDITION2', 'SUB_CATEGORY'],
    'curated_datamodels.core_temple_auvs_summary_tab_test_dummy': ['DELETED_FLAG'],
    'curated_datamodels.core_temple_ddns': ['DELETED_FLAG'],
    'curated_datamodels.core_temple_ddrf_test_dummy': ['DELETED_FLAG'],
    'curated_datamodels.gsws_sec_secretariat_master': ['IS_CMS_ENABLED', 'IS_FLOOD', 'IS_P4', 'LGD_DIST_CODE', 'LGD_MANDAL_CODE', 'OLD_LGD_DIST_CODE', 'RURAL_URBAN_FLAG', 'SECRETARIAT_CODE'],
    'curated_datamodels.health_scheme_code': ['health_scheme_code'],
    'curated_datamodels.infrastructure_category_dim': ['infra_category_code', 'is_active', 'is_current'],
    'curated_datamodels.infrastructure_component_dim': ['infra_component_code', 'is_active', 'is_current', 'is_functional_track', 'unit_type'],
    'curated_datamodels.meal_type_dim': ['IS_ACTIVE', 'IS_COMPULSORY', 'IS_CURRENT', 'MEAL_TYPE_CODE', 'MEAL_TYPE_NAME'],
    'curated_datamodels.mid_day_meal_serving_fact': ['FOOD_TASTED_FLAG', 'GEO_TAGGED_FLAG', 'HYGIENE_COMPLIANT_FLAG', 'INSPECTION_REMARKS_CODE', 'MEAL_NOT_SERVED_REASON_CODE', 'MEAL_SERVED_FLAG', 'MEDICAL_INCIDENT_REPORTED_FLAG', 'PHOTO_CAPTURED_FLAG', 'SUPPLY_SHORTAGE_FLAG', 'TEACHER_SUPERVISED_FLAG'],
    'curated_datamodels.nutrition_item_dim': ['is_active', 'is_current', 'item_code', 'nutrition_category'],
    'curated_datamodels.ration_card_citizen': ['STATUS_CODE'],
    'curated_datamodels.ration_card_citizen_reason': ['reason_code', 'reason_description'],
    'curated_datamodels.ration_card_family': ['CARD_TYPE_CODE', 'FPS_CODE', 'ISSUING_DISTRICT_CODE', 'STATUS_CODE'],
    'curated_datamodels.ration_card_type': ['CARD_TYPE_CODE', 'CARD_TYPE_DESCRIPTION', 'RATION_CARD_TYPE_NAME'],
    'curated_datamodels.scheme_benefits_fact': ['aadhaar_seeded_flag', 'attendance_eligible_flag', 'bank_account_verified_flag', 'benefit_delivered_flag', 'benefit_disbursed_flag', 'benefit_rejected_flag', 'benefit_sanctioned_flag', 'benefit_withheld_flag', 'bgm_eligible_flag', 'cwsn_flag', 'delivery_mode', 'eligible_beneficiary_flag', 'eligible_flag', 'girl_child_flag', 'kyc_completed_flag', 'payment_failure_reason_code', 'rejection_reason_code', 'scheme_uptake_rate', 'social_category'],
    'curated_datamodels.school_academic_performance_fact': ['ABSENT_FLAG', 'EVALUATION_TYPE', 'EXAM_TYPE', 'FAIL_FLAG', 'MEDIUM_OF_EXAM', 'PASS_FLAG', 'WITHHELD_FLAG', 'YEAR_ON_YEAR_IMPROVEMENT_FLAG'],
    'curated_datamodels.school_category': ['CATEGORY_CODE', 'CATEGORY_TYPE', 'MAX_CLASS', 'MIN_CLASS', 'UDISE_TYPE'],
    'curated_datamodels.school_infra_category_dim': ['is_active', 'is_current', 'school_infra_category_code'],
    'curated_datamodels.school_infra_component_dim': ['component_code', 'is_active', 'is_current', 'is_digital', 'measurement_type'],
    'curated_datamodels.school_infrastructure_progress_fact': ['delay_reason_code', 'geo_tagged_flag', 'inspection_remarks_code', 'is_functional_flag', 'is_safety_compliant_flag', 'is_structurally_certified_flag', 'maintenance_required_flag', 'work_status'],
    'curated_datamodels.school_meal_menu_dim': ['is_active', 'is_current', 'is_planned', 'weekday_code'],
    'curated_datamodels.school_medium': ['MEDIUM_CODE'],
    'curated_datamodels.school_scheme_master': ['applicable_level', 'delivery_mode', 'is_active', 'is_current', 'scheme_category', 'scheme_code', 'scheme_status'],
    'curated_datamodels.school_student_attendance_fact': ['ABSENT_FLAG', 'ATTENDANCE_REASON_CODE', 'ATTENDANCE_STATUS_CODE', 'CHIKKI_ELIGIBLE_FLAG', 'EGGS_ELIGIBLE_FLAG', 'HALF_DAY_FLAG', 'HM_APPROVAL_FLAG', 'IMAGE_AVAILABLE_FLAG', 'MARKED_BY_ROLE', 'MDM_ELIGIBLE_FLAG', 'MEALS_CONSUMED_FLAG', 'PRESENT_FLAG', 'RAGI_JAVA_ELIGIBLE_FLAG'],
    'curated_datamodels.school_subject_master': ['BOARD_CODE', 'IS_COMPULSORY_FLAG', 'IS_SKILL_SUBJECT_FLAG', 'IS_VOCATIONAL_FLAG', 'MARKS_SCHEME', 'MAX_CLASS', 'MIN_CLASS', 'SUBJECT_CATEGORY', 'SUBJECT_CODE', 'SUBJECT_STATUS', 'SUBJECT_TYPE'],
    'curated_datamodels.school_teacher_attendance_fact': ['approval_role', 'approval_status_code', 'approved_leave_flag', 'attendance_status_code', 'image_available_flag', 'late_flag', 'leave_type', 'on_duty_flag', 'on_leave_flag', 'present_flag'],
    'curated_datamodels.source_department_code': ['source_department_code'],
    'curated_datamodels.student_class_dim': ['CLASS_CODE', 'CLASS_NAME', 'IS_ACTIVE']
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
