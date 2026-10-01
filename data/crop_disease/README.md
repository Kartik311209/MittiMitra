# Crop-disease training data (local only)

Put a reviewed, licence-compatible labelled dataset here after downloading it
yourself. Do not commit raw images to Git.

Expected structure:

```text
data/crop_disease/raw/
  Tomato___healthy/
    image-001.jpg
  Tomato___Early_blight/
    image-002.jpg
  Potato___healthy/
    image-003.jpg
```

The first baseline needs at least two classes and three readable images per
class. Before training, record the dataset URL, version, licence, class list,
and whether commercial use is allowed. Use the command below from the project
root:

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.venv\Scripts\python.exe -m soil_npk.crop_disease --dataset-dir .\data\crop_disease\raw
```

The produced model is a preliminary image-similarity baseline. Validate it on
held-out, India-relevant field photos before relying on it, and never treat its
result as a pesticide prescription.

## Indian field-photo dataset preparation (September 2026)

Five source ZIP files are stored locally under `sources/` and are ignored by
Git. `python -m soil_npk.prepare_crop_datasets` prepares them into
`prepared/{train,val,test}/<crop___finding>/` and writes
`prepared/manifest.json`. Source ZIP files are left untouched. Rice and
sugarcane have nested 7z/RAR archives; those were unpacked to the ignored
`staging/` folder on the local development machine before preparation.

The prepared images represent selected Indian regions and crops, **not all
Indian agro-climatic zones**. The rice source does not include a healthy class;
SoyNet only distinguishes healthy from unspecified disease; wheat nitrogen
deficiency is nutrient stress, not disease. The Multi-Crop page is marked
CC BY 4.0 while its bundled Roboflow YAML says `license: Private`. Clarify
that discrepancy before redistribution or production use. Random splits for
rice, sugarcane and SoyNet may contain near-duplicate field views across
splits, so a held-out farm/district evaluation is required.

For a local research-only candidate, train to a **different** model path so
the portal remains unchanged until evaluation:

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.venv\Scripts\python.exe -m soil_npk.crop_disease --dataset-dir .\data\crop_disease\prepared --model-path .\artifacts\crop_disease_candidate.npz
.\.venv\Scripts\python.exe -m soil_npk.evaluate_crop_disease --model-path .\artifacts\crop_disease_candidate.npz --test-dir .\data\crop_disease\prepared\test --report-path .\artifacts\crop_disease_candidate_evaluation.json
```

Do not interpret the baseline's softmax similarity as calibrated medical or
agronomic confidence. A field-validated, crop-aware model and expert-reviewed
labels are needed before farmer-facing disease predictions are enabled.
