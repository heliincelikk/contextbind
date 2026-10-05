# ContextBind — Phase P4 Deterministic Quality Audit (50 Sampled Claims)

Sampled deterministically using seed `20261004` across Train, Val-ID, and Val-OOD.

| # | Task | Split | Template Family | Ground Truth | Claim Text |
|---|---|---|---|---|---|
| 1 | S2 | TRAIN | S2_TF3_DOCUMENTATION | `CONTRADICTED` | The documentation of Well child visit (procedure) succeeded General examination of patient (procedure). |
| 2 | S1 | TRAIN | S1_TF1_ACTIVE | `SUPPORTED` | The Troponin I.cardiac level has decreased across the last 3 measurements. |
| 3 | S4 | VAL-ID | S4_TF1_DIRECT_CURRENT | `CONTRADICTED` | The patient's current Bilirubin.total is 0.53708 mg/dL. |
| 4 | S3 | TRAIN | S3_TF1_COMPARATIVE_ADJ | `CONTRADICTED` | The latest Pain severity - 0-10 verbal numeric rating reading is higher than the previous measurement. |
| 5 | S3 | TRAIN | S3_TF3_ENCOUNTER_SHIFT | `SUPPORTED` | Compared to the preceding encounter, the current Carbon dioxide, total is elevated. |
| 6 | S2 | TRAIN | S2_TF3_DOCUMENTATION | `SUPPORTED` | The documentation of Well child visit (procedure) succeeded Acetaminophen 160 MG Chewable Tablet. |
| 7 | S4 | TRAIN | S4_TF1_DIRECT_CURRENT | `SUPPORTED` | The patient's current Urea nitrogen is 12.85 mg/dL. |
| 8 | S2 | TRAIN | S2_TF2_SEQUENCE | `CONTRADICTED` | Encounter for check up (procedure) occurred prior to Emergency hospital admission (procedure). |
| 9 | S3 | VAL-OOD | S3_TF4_MAGNITUDE_HELD_OUT | `CONTRADICTED` | The current measurement of Potassium is greater than the value from the prior evaluation. |
| 10 | S4 | VAL-ID | S4_TF2_MOST_RECENT | `CONTRADICTED` | The most recently documented Potassium is 4.32 mmol/L. |
| 11 | S3 | VAL-ID | S3_TF1_COMPARATIVE_ADJ | `CONTRADICTED` | The latest Generalized anxiety disorder 7 item (GAD-7) total score reading is higher than the previous measurement. |
| 12 | S2 | VAL-ID | S2_TF2_SEQUENCE | `CONTRADICTED` | Consultation for treatment (procedure) occurred prior to Encounter for check up (procedure). |
| 13 | S1 | TRAIN | S1_TF3_COURSE | `CONTRADICTED` | Patient Health Questionnaire 2 item (PHQ-2) total score has exhibited a rising course over recent visits. |
| 14 | S4 | TRAIN | S4_TF3_RECORDED_FINDING | `CONTRADICTED` | Latest recorded Platelet distribution width stands at 15.941 fL. |
| 15 | S1 | TRAIN | S1_TF1_ACTIVE | `SUPPORTED` | The pH of Urine by Test strip level has decreased across the last 3 measurements. |
| 16 | S3 | TRAIN | S3_TF2_EXCEEDS_FALLS | `CONTRADICTED` | The most recent Protein falls below the prior value. |
| 17 | S1 | VAL-ID | S1_TF3_COURSE | `SUPPORTED` | Body Height has exhibited a rising course over recent visits. |
| 18 | S3 | TRAIN | S3_TF1_COMPARATIVE_ADJ | `CONTRADICTED` | The latest Pain severity - 0-10 verbal numeric rating reading is lower than the previous measurement. |
| 19 | S2 | TRAIN | S2_TF1_STANDARD | `CONTRADICTED` | Ibuprofen 100 MG Oral Tablet was recorded after Well child visit (procedure). |
| 20 | S2 | TRAIN | S2_TF3_DOCUMENTATION | `CONTRADICTED` | The documentation of General examination of patient (procedure) preceded Prenatal visit (regime/therapy). |
| 21 | S1 | TRAIN | S1_TF1_ACTIVE | `SUPPORTED` | The Glucose level has decreased across the last 3 measurements. |
| 22 | S2 | TRAIN | S2_TF1_STANDARD | `CONTRADICTED` | Encounter for check up (procedure) was recorded after Emergency room admission (procedure). |
| 23 | S2 | TRAIN | S2_TF3_DOCUMENTATION | `SUPPORTED` | The documentation of Encounter for symptom (procedure) succeeded Encounter for check up (procedure). |
| 24 | S2 | TRAIN | S2_TF2_SEQUENCE | `SUPPORTED` | Emergency room admission (procedure) occurred following Encounter for problem (procedure). |
| 25 | S3 | TRAIN | S3_TF2_EXCEEDS_FALLS | `CONTRADICTED` | The most recent Chloride exceeds the prior value. |
| 26 | S2 | TRAIN | S2_TF2_SEQUENCE | `CONTRADICTED` | Protocol for Responding to and Assessing Patients' Assets, Risks, and Experiences occurred prior to Tobacco smoking status. |
| 27 | S2 | TRAIN | S2_TF1_STANDARD | `CONTRADICTED` | General examination of patient (procedure) was recorded before NDA020800 0.3 ML Epinephrine 1 MG/ML Auto-Injector. |
| 28 | S2 | TRAIN | S2_TF3_DOCUMENTATION | `CONTRADICTED` | The documentation of Prenatal visit (regime/therapy) preceded Emergency room admission (procedure). |
| 29 | S2 | VAL-ID | S2_TF1_STANDARD | `CONTRADICTED` | Loratadine 5 MG Chewable Tablet was recorded before Encounter for problem (procedure). |
| 30 | S2 | TRAIN | S2_TF3_DOCUMENTATION | `SUPPORTED` | The documentation of Encounter for check up (procedure) succeeded Urgent care clinic (environment). |
| 31 | S3 | VAL-OOD | S3_TF4_MAGNITUDE_HELD_OUT | `CONTRADICTED` | The current measurement of MCH is less than the value from the prior evaluation. |
| 32 | S1 | TRAIN | S1_TF3_COURSE | `SUPPORTED` | Cholesterol has exhibited a rising course over recent visits. |
| 33 | S1 | TRAIN | S1_TF1_ACTIVE | `CONTRADICTED` | The Hemoglobin A1c/Hemoglobin.total in Blood level has increased across the last 3 measurements. |
| 34 | S3 | TRAIN | S3_TF3_ENCOUNTER_SHIFT | `CONTRADICTED` | Compared to the preceding encounter, the current Urea nitrogen is elevated. |
| 35 | S3 | TRAIN | S3_TF2_EXCEEDS_FALLS | `SUPPORTED` | The most recent Chloride falls below the prior value. |
| 36 | S2 | TRAIN | S2_TF3_DOCUMENTATION | `CONTRADICTED` | The documentation of Well child visit (procedure) succeeded Urgent care clinic (environment). |
| 37 | S3 | TRAIN | S3_TF1_COMPARATIVE_ADJ | `CONTRADICTED` | The latest Pain severity - 0-10 verbal numeric rating reading is lower than the previous measurement. |
| 38 | S1 | TRAIN | S1_TF3_COURSE | `SUPPORTED` | Heart rate has exhibited a rising course over recent visits. |
| 39 | S2 | TRAIN | S2_TF3_DOCUMENTATION | `CONTRADICTED` | The documentation of General examination of patient (procedure) preceded {28 (norethindrone 0.35 MG Oral Tablet) } Pack. |
| 40 | S3 | TRAIN | S3_TF1_COMPARATIVE_ADJ | `CONTRADICTED` | The latest Chloride reading is higher than the previous measurement. |
| 41 | S3 | VAL-OOD | S3_TF4_MAGNITUDE_HELD_OUT | `SUPPORTED` | The current measurement of Head Occipital-frontal circumference is greater than the value from the prior evaluation. |
| 42 | S4 | VAL-ID | S4_TF2_MOST_RECENT | `CONTRADICTED` | The most recently documented Glucose is 92.24 mg/dL. |
| 43 | S3 | TRAIN | S3_TF2_EXCEEDS_FALLS | `SUPPORTED` | The most recent Aspartate aminotransferase falls below the prior value. |
| 44 | S3 | VAL-ID | S3_TF2_EXCEEDS_FALLS | `SUPPORTED` | The most recent Erythrocyte falls below the prior value. |
| 45 | S3 | TRAIN | S3_TF2_EXCEEDS_FALLS | `SUPPORTED` | The most recent Heart rate exceeds the prior value. |
| 46 | S3 | VAL-OOD | S3_TF4_MAGNITUDE_HELD_OUT | `CONTRADICTED` | The current measurement of Hemoglobin is greater than the value from the prior evaluation. |
| 47 | S2 | TRAIN | S2_TF2_SEQUENCE | `CONTRADICTED` | Encounter for symptom (procedure) occurred following Well child visit (procedure). |
| 48 | S3 | VAL-OOD | S3_TF4_MAGNITUDE_HELD_OUT | `CONTRADICTED` | The current measurement of Pain severity - 0-10 verbal numeric rating is less than the value from the prior evaluation. |
| 49 | S3 | TRAIN | S3_TF3_ENCOUNTER_SHIFT | `SUPPORTED` | Compared to the preceding encounter, the current Respiratory rate is elevated. |
| 50 | S4 | VAL-OOD | S4_TF4_ACTIVE_STATE_HELD_OUT | `CONTRADICTED` | As of the current evaluation, the active Weight-for-length Per age and sex measurement is 68.93 %. |
