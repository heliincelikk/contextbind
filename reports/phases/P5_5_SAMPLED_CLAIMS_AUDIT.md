# ContextBind — Phase P5.5 Natural Claims Quality Audit (50 Sampled Claims)

Sampled deterministically using seed `20261004` across Task S1–S4.

| # | Task | Split | Template ID | Ground Truth | Natural Agent Justification Text |
|---|---|---|---|---|---|
| 1 | S1 | TRAIN | NAT_S1_2 | `SUPPORTED` | Serial laboratory testing indicates that Magnesium levels have consistently increased over the patient's past 3 recorded outpatient encounters. |
| 2 | S1 | TRAIN | NAT_S1_3 | `CONTRADICTED` | Review of consecutive diagnostic workups demonstrates a steady upward progression in Body mass index (BMI) across the prior three visits. |
| 3 | S4 | TRAIN | NAT_S4_3 | `SUPPORTED` | According to the EHR summary, the active recorded finding for Carbon dioxide, total is 25.12 mmol/L. |
| 4 | S2 | TRAIN | NAT_S2_1 | `SUPPORTED` | Clinical records verify that Encounter for symptom (procedure) was documented ahead of Acetaminophen 325 MG Oral Tablet. |
| 5 | S2 | TRAIN | NAT_S2_2 | `SUPPORTED` | According to the encounter timeline, General examination of patient (procedure) took place prior to the start of Encounter for symptom (procedure). |
| 6 | S2 | TRAIN | NAT_S2_2 | `CONTRADICTED` | According to the encounter timeline, Total score took place subsequent to the completion of Encounter for symptom (procedure). |
| 7 | S3 | TRAIN | NAT_S3_2 | `CONTRADICTED` | Diagnostic assessment shows that the most recently documented Bilirubin.total drops below the prior encounter's result. |
| 8 | S1 | TRAIN | NAT_S1_1 | `CONTRADICTED` | The patient's longitudinal EHR chart reveals a progressively rising trajectory in Chloride across three recent clinical evaluations. |
| 9 | S4 | TRAIN | NAT_S4_4 | `CONTRADICTED` | The latest clinical evaluation confirms Triglyceride measuring 100.54 mg/dL. |
| 10 | S4 | TRAIN | NAT_S4_2 | `CONTRADICTED` | The most recent laboratory panel documents active Calcium at 10.03 mg/dL. |
| 11 | S3 | TRAIN | NAT_S3_3 | `SUPPORTED` | Evaluating recent trends reveals that current Ketones levels are higher relative to the earlier measurement. |
| 12 | S3 | TRAIN | NAT_S3_1 | `CONTRADICTED` | Compared against baseline measurements from the preceding visit, the patient's current Patient Health Questionnaire 2 item (PHQ-2) total score demonstrates an attenuated reading. |
| 13 | S1 | TRAIN | NAT_S1_1 | `CONTRADICTED` | The patient's longitudinal EHR chart reveals a downward trajectory in Heart rate across three recent clinical evaluations. |
| 14 | S2 | TRAIN | NAT_S2_4 | `CONTRADICTED` | In the patient's care sequence, Patient Health Questionnaire 2 item (PHQ-2) total score is registered as preceding Generalized anxiety disorder 7 item (GAD-7) total score. |
| 15 | S1 | TRAIN | NAT_S1_3 | `SUPPORTED` | Review of consecutive diagnostic workups demonstrates a steady upward progression in Left ventricular Ejection fraction across the prior three visits. |
| 16 | S4 | TRAIN | NAT_S4_1 | `SUPPORTED` | Based on active chart documentation, the patient's current Patient Health Questionnaire 2 item (PHQ-2) total score is confirmed at 2.0 {score}. |
| 17 | S3 | TRAIN | NAT_S3_4 | `CONTRADICTED` | The active reading for Potassium reflects a rise in value compared to the previous clinical record. |
| 18 | S2 | TRAIN | NAT_S2_3 | `SUPPORTED` | Longitudinal documentation establishes that Total score chronologically antedated Encounter for check up (procedure). |
| 19 | S1 | TRAIN | NAT_S1_3 | `CONTRADICTED` | Review of consecutive diagnostic workups demonstrates a steady upward progression in Cholesterol across the prior three visits. |
| 20 | S1 | TRAIN | NAT_S1_3 | `CONTRADICTED` | Review of consecutive diagnostic workups demonstrates a steady decline in Glucose across the prior three visits. |
| 21 | S1 | TRAIN | NAT_S1_4 | `SUPPORTED` | Longitudinal monitoring confirms that Body Weight measurements have been trending downward over the course of the last 3 checkups. |
| 22 | S2 | TRAIN | NAT_S2_4 | `SUPPORTED` | In the patient's care sequence, Protocol for Responding to and Assessing Patients' Assets, Risks, and Experiences is registered as preceding Total score. |
| 23 | S4 | TRAIN | NAT_S4_3 | `SUPPORTED` | According to the EHR summary, the active recorded finding for Glucose is 0.6503 mg/dL. |
| 24 | S1 | TRAIN | NAT_S1_2 | `CONTRADICTED` | Serial laboratory testing indicates that Bilirubin.total levels have consistently increased over the patient's past 3 recorded outpatient encounters. |
| 25 | S2 | TRAIN | NAT_S2_1 | `CONTRADICTED` | Clinical records verify that Pain severity - 0-10 verbal numeric rating was documented in the aftermath of Protocol for Responding to and Assessing Patients' Assets, Risks, and Experiences. |
| 26 | S2 | TRAIN | NAT_S2_4 | `CONTRADICTED` | In the patient's care sequence, General examination of patient (procedure) is registered as following Emergency room admission (procedure). |
| 27 | S2 | TRAIN | NAT_S2_4 | `CONTRADICTED` | In the patient's care sequence, Protocol for Responding to and Assessing Patients' Assets, Risks, and Experiences is registered as following Total score. |
| 28 | S1 | TRAIN | NAT_S1_1 | `SUPPORTED` | The patient's longitudinal EHR chart reveals a downward trajectory in Chloride across three recent clinical evaluations. |
| 29 | S1 | TRAIN | NAT_S1_2 | `SUPPORTED` | Serial laboratory testing indicates that Albumin levels have consistently increased over the patient's past 3 recorded outpatient encounters. |
| 30 | S3 | TRAIN | NAT_S3_4 | `SUPPORTED` | The active reading for Glomerular filtration rate reflects a rise in value compared to the previous clinical record. |
| 31 | S2 | TRAIN | NAT_S2_4 | `CONTRADICTED` | In the patient's care sequence, Protocol for Responding to and Assessing Patients' Assets, Risks, and Experiences is registered as preceding Tobacco smoking status. |
| 32 | S4 | TRAIN | NAT_S4_3 | `SUPPORTED` | According to the EHR summary, the active recorded finding for Potassium is 4.58 mmol/L. |
| 33 | S1 | TRAIN | NAT_S1_1 | `CONTRADICTED` | The patient's longitudinal EHR chart reveals a progressively rising trajectory in Generalized anxiety disorder 7 item (GAD-7) total score across three recent clinical evaluations. |
| 34 | S1 | TRAIN | NAT_S1_3 | `CONTRADICTED` | Review of consecutive diagnostic workups demonstrates a steady upward progression in Left ventricular Ejection fraction across the prior three visits. |
| 35 | S2 | TRAIN | NAT_S2_4 | `SUPPORTED` | In the patient's care sequence, Consultation for treatment (procedure) is registered as following Encounter for check up (procedure). |
| 36 | S2 | TRAIN | NAT_S2_1 | `CONTRADICTED` | Clinical records verify that Body Height was documented in the aftermath of Protocol for Responding to and Assessing Patients' Assets, Risks, and Experiences. |
| 37 | S1 | TRAIN | NAT_S1_1 | `CONTRADICTED` | The patient's longitudinal EHR chart reveals a progressively rising trajectory in Glucose across three recent clinical evaluations. |
| 38 | S2 | TRAIN | NAT_S2_2 | `SUPPORTED` | According to the encounter timeline, Total score took place prior to the start of Encounter for check up (procedure). |
| 39 | S4 | TRAIN | NAT_S4_4 | `CONTRADICTED` | The latest clinical evaluation confirms Body mass index (BMI) measuring 27.9 kg/m2. |
| 40 | S1 | TRAIN | NAT_S1_4 | `SUPPORTED` | Longitudinal monitoring confirms that Ketones measurements have been trending downward over the course of the last 3 checkups. |
| 41 | S1 | TRAIN | NAT_S1_1 | `SUPPORTED` | The patient's longitudinal EHR chart reveals a progressively rising trajectory in Iron across three recent clinical evaluations. |
| 42 | S2 | TRAIN | NAT_S2_2 | `CONTRADICTED` | According to the encounter timeline, Cholesterol took place subsequent to the completion of Protocol for Responding to and Assessing Patients' Assets, Risks, and Experiences. |
| 43 | S4 | TRAIN | NAT_S4_2 | `SUPPORTED` | The most recent laboratory panel documents active Body Weight at 88.1 kg. |
| 44 | S3 | TRAIN | NAT_S3_4 | `SUPPORTED` | The active reading for Protein reflects a rise in value compared to the previous clinical record. |
| 45 | S2 | TRAIN | NAT_S2_1 | `SUPPORTED` | Clinical records verify that Total score was documented in the aftermath of Generalized anxiety disorder 7 item (GAD-7) total score. |
| 46 | S4 | TRAIN | NAT_S4_4 | `SUPPORTED` | The latest clinical evaluation confirms Glucose measuring 0.6503 mg/dL. |
| 47 | S3 | TRAIN | NAT_S3_2 | `SUPPORTED` | Diagnostic assessment shows that the most recently documented Glucose surpasses the prior encounter's result. |
| 48 | S2 | TRAIN | NAT_S2_3 | `CONTRADICTED` | Longitudinal documentation establishes that Total score chronologically antedated Patient Health Questionnaire 2 item (PHQ-2) total score. |
| 49 | S4 | TRAIN | NAT_S4_2 | `CONTRADICTED` | The most recent laboratory panel documents active Body Weight at 95.6 kg. |
| 50 | S2 | TRAIN | NAT_S2_3 | `SUPPORTED` | Longitudinal documentation establishes that Encounter for check up (procedure) chronologically succeeded Total score. |
