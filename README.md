# Local Binary Pattern Benchmarking Tool

---

## Overview

Evaluate performance of Local Binary Pattern CV algorithms and similarity measures against image sets with simulated noise, illumination, scale shift, and other image transformation techniques.

This tool is designed to aid in the visualization and tuning of texture extraction pipelines which utilize local binary patterns as their primary mode of texture extraction. Specifically, it was designed to aid in development of texture extraction and texture feature comparison functionality within the Monty system developed by Thousand Brains Project.

---

## Installation

To install, clone the repo and install using pip and the included pyproject.toml file. The following commands can be used to install the tool.

**Note:** creating and using a virtual environment is not necessary, but is recommended.  
Python version 3.9 or higher is required.

```bash
git clone https://github.com/nielsleadholm/tbp.lbp_benchmark.git
cd tbp.lbp_benchmark

python -m venv .venv
```

Then activate the virtual environment.

Mac/Linux:
```bash
source .venv/bin/activate
```

Windows:
```bash
.venv\Scripts\activate
```

Finally, install the project.
```bash
pip install -e .
```

---

## How to use

The benchmark is driven by **two kinds of YAML config**, which are kept separate so that LBP algorithm parameters can be reused across many different experimental conditions:

1. **LBP config** (`config/lbp/`) — defines the texture extraction and matching parameters: `texture_extraction` and `matching`.
2. **Experiment config** (`config/experiments/`) — defines the experimental conditions: the `data` (dataset choice), `rng` (random seed), the `query_image_processing` / `target_image_processing` perturbations (noise, blur, illumination, cropping, etc.), and the `output` options.

A single run pairs **one** LBP config with **one or more** experiment configs. Each experiment config is evaluated **in series**, and the matching statistics for every experiment are written to a single aggregate CSV.

To run the benchmark, ensure that you are in a shell terminal with the project root as your current working directory, then run, for example:

```bash
python run.py \
  --lbp-config config/lbp/default_lbp.yaml \
  --experiment-config config/experiments/clean.yaml config/experiments/noisy_inputs.yaml config/experiments/illumination.yaml
```

This evaluates the `default_lbp` texture extraction + matching parameters against three experimental conditions (clean, noisy, and illumination-shifted query images), one after another.

### CLI arguments

- `--lbp-config` (required): path to a single LBP config (texture extraction + matching).
- `--experiment-config` (required): one or more paths to experiment configs. These are evaluated in series.
- `--summary-csv` (optional): path for the aggregate summary CSV. Defaults to `results/summary_<lbp_name>_<timestamp>.csv`.
- `--visualize` (optional flag): open the results visualization GUI after each experiment finishes, overriding each experiment's `output.visualize` setting. Useful for inspecting matches without editing config files.

### Outputs

- **Aggregate summary CSV** — one row per experiment, containing the matching statistics (total/correct/incorrect matches, percent correct, distance statistics) plus the LBP config, experiment config, run time, and `num_lbp_codes`. Written to `--summary-csv` (or `results/summary_<lbp_name>_<timestamp>.csv` by default).
  - `num_lbp_codes` is the length of the feature vector (the total number of LBP codes / histogram bins) produced by the texture extraction setup. This is determined by the chosen encoding (e.g. for `P=8`, `default` → 256, `ror` → 36, `uniform` → 10) and is summed across scales for multi-scale configs, making it easy to compare the dimensionality cost of different LBP variants.
- **Per-experiment outputs** — for each experiment whose `output` section enables them, results are written to `results/<lbp_name>__<experiment_name>/`:
  - `match_results.csv` (when `save_csv: true`): the raw per-match results.
  - report PDF (when `save_pdf: true`).
  - `run_config.yaml`: the fully merged config (LBP + experiment) actually used for the run, and a copy of the source experiment config.
  - A visualization window opens when `visualize: true`.

Each experiment takes only a few seconds to run on the bundled datasets. Once finished, you will see matching-related statistics in standard output for every experiment, followed by the path to the aggregate summary CSV. The example experiment configs use the ‘WellDefinedTextures’ datasets, which are derived from a subset of images included in a texture dataset called “Describable Textures Dataset”, which was gathered at a Johns Hopkins University summer workshop, and is hosted by Oxford University (dataset available at this link: https://www.robots.ox.ac.uk/~vgg/data/dtd/index.html#overview). This dataset uses the labels (cracked, dotted, flecked, etc.) derived from the original creators of the dataset.

### Plotting and comparing results

`plot_results.py` turns one or more aggregate summary CSVs into comparison plots. The intended workflow is to run each LBP config against the same series of increasingly challenging experiment conditions, then plot all of the resulting summaries together:

```bash
# One run per LBP config (each writes its own results/summary_<lbp_name>_<timestamp>.csv).
python run.py \
  --lbp-config config/lbp/default_lbp.yaml \
  --experiment-config config/experiments/clean.yaml config/experiments/noisy_inputs.yaml config/experiments/illumination.yaml

python run.py \
  --lbp-config config/lbp/ltp_ror_multiscale.yaml \
  --experiment-config config/experiments/clean.yaml config/experiments/noisy_inputs.yaml config/experiments/illumination.yaml

# Plot every summary found in results/ (or pass explicit CSV paths).
python plot_results.py
```

This produces two figures in `results/plots/`:

- **`accuracy_comparison.png`** — a grouped bar plot of accuracy (% correct matches). Each experiment condition is a separate x-axis group, and each LBP configuration is a differently coloured bar, so you can read off how each method degrades as conditions get harder. Beneath each condition is a small inset showing an example texture from the target dataset with that condition's perturbations applied (the same processing used during matching, and shown by the interactive `--visualize` tool), giving an at-a-glance intuition for how strong each perturbation is.
- **`lbp_code_counts.png`** — a supplementary bar plot comparing the number of LBP codes (feature-vector length) per LBP configuration, making the dimensionality cost of each method easy to compare against its accuracy.

The experiment conditions appear along the x-axis in the order they were run (so listing them worst-last gives a left-to-right "increasingly challenging" axis). Bars are coloured from a fixed brand palette, used in preference order: blue, pink, purple, gold, green (cycling if there are more than five configurations).

**CLI arguments:**

- `summaries` (positional, optional): one or more summary CSV files, or directories containing `summary_*.csv`. Defaults to searching `results/`.
- `--output-dir` (optional): directory for the plot images. Defaults to `results/plots`.
- `--accuracy-filename` / `--codes-filename` (optional): output filenames for the two plots.
- `--accuracy-title` / `--codes-title` (optional): plot titles.
- `--no-previews` (optional flag): disable the perturbed-texture preview insets beneath the accuracy plot.
- `--preview-example` (optional): name (or stem) of the target-dataset image to use for the preview insets. Defaults to the first image in the target folder.
- `--show` (optional flag): also display the plots interactively.

---

## What do these statistics mean?

After running the benchmarker using the default configuration, you should see the following statistics:

```text
Total matches: 1495
Total correct: 1049
Total incorrect: 446
Percent correct: 70.17%
Highest distance among correct matches: 0.116396
Lowest distance among correct matches: 0.000000
Average distance among correct matches: 0.002388
Highest distance among incorrect matches: 0.140297
Lowest distance among incorrect matches: 0.000277
Average distance among incorrect matches: 0.008493
```

---

### Metric Definitions

**Total matches:** The total number of matches included in the results of the experiment. This value is dependent on the number of images in the dataset used, as well as the configured ‘top’ and ‘tolerance’ values within the experiment’s configuration. In this case, there are 299 images in the dataset ran, and the top 5 matches were included in the result set, with all 5 of those matches falling under a tolerance value of 1, which results in 299 * 5 = 1495 matches (a deeper explanation of ‘top’, ‘tolerance’, and other experiment configuration parameters are in a later section.)

**Total correct:** The total number of image matches that were correct, with a correct match being qualified as a match between two images with the same texture ‘label’.

**Total incorrect:** The total number of image matches that were incorrect, meaning two matches images having different texture ‘labels’.

**Percent correct:** Total percent of reported matches which were correct.

**Highest distance among correct matches:** The highest distance computed across all correct matches. This statistic can be used to configure an experiment’s tolerance threshold to filter out incorrect matches without reducing the amount of correct matches.

**Lowest distance among correct matches:** The lowest distance computed across all correct matches. While good to know, this isn’t particularly useful in most cases, as it will almost always be near-0 during any meaningful experiment.

**Average distance among correct matches:** The average distance computed across all correct matches. This metric can be useful through comparison with the average incorrect distance, as a wide margin suggests strong performance in regards to how well the feature vectors being computed are doing in meaningfully describing the image in a manner that is both consistent within the same texture class, and discernible in comparison to other texture classes.

**Highest distance among incorrect matches:** Similar to ‘lowest distance among correct matches’, this metric isn’t particularly useful for tuning any specific parameters, but can provide some insight into the behavior of a particular configuration, as low values could suggest poor performance.

**Lowest distance among incorrect matches:** The lowest distance computed across all incorrect matches. This metric is arguably the most useful, as it can be used to filter out all or nearly all incorrect matches from an experiment by using a tolerance value slightly below it. This can be useful in Monty for tuning threshold values to eliminate false-positive ‘matches’ from contributing evidence during object recognition experiments.

**Average distance among incorrect matches:** Refer to ‘average distance among correct matches’.

---

#### Configuration Guide

This section explains how the configuration files work, what each parameter controls, and how to tune them for different experiments. The benchmark is driven by two YAML files: an **LBP config** and an **experiment config** (see *How to use* above).

**Experiment config** (`config/experiments/`) contains sections: *Dataset*, *Random Number Generator*, *Query Image Processing*, *Target Image Processing*, *Data Engineering*, and *Output*.

**LBP config** (`config/lbp/`) contains sections: *Texture Extraction* and *Matching*.

The sections below describe every parameter; the heading for each notes which file it belongs in.

1) Dataset *(experiment config)*
```yaml
data: 
    query_images_folder: LBP_Test_Images/WellDefinedTextures_10Rotations_128
    target_images_folder: LBP_Test_Images/WellDefinedTextures_128
```
**query_images_folder:**
Path to dataset of images in which to be matched to a target dataset.
- Must point to a directory containing only images (no nested folders).
- Relative or absolute paths can be used (absolute is recommended).
- Each image is expected to abide by the following encoding scheme: `IDENTIFIER_TEXTURE-CLASS_DISTANCE_ROTATION_LIGHTING.IMAGE_EXTENSION`
- In cases where distance, rotation, and/or lighting values are not known or sourced, using a placeholder '0' is perfectly fine-- the only truly necessary part of the filename encoding schema is 'TEXTURE-CLASS', which is used to drive 'correct' and 'incorrect' determinations for texture matching results.

**target_images_folder:**
Path to the dataset of images in which to be used to match against.
- Images in this set must abide by the same encoding scheme as 'query_images_folder'.
- This dataset should remain unprocessed in standard experimental setups to test matching 'noisy' query images to a stored (target) dataset.

2) Random Number Generator *(experiment config)*
```yaml
rng:
    seed: 42
```
**seed:**
- Controls randomness in the benchmark.
- Ensures reproducibility across runs.
- Affects operations like random cropping or noise.
- Use the same seed when comparing configurations.


3) Texture Extraction *(LBP config)*
This benchmarker supports the following variants of Local Binary Pattern texture extraction:
    - Standard Local Binary Pattern
    - Local Ternary Pattern
    - Completed Local Binary Pattern

```yaml
texture_extraction:
  local_binary_pattern:
    P: 8
    R: 1.0
    method: "uniform"
```
**P (number of neighbors):**
Number of sample points around each pixel
    Common values: 8, 16, 24
    Higher values → more detail, but more computation
**R (radius):**
Distance from center pixel
    Larger radius captures broader texture patterns
    Small radius focuses on fine detail
**method:**
Method used for encoding binary strings.
    For typical use, ror tends to be most robust to rotation, at the cost of being weak to noise and producing a
    much larger (2^P entries) feature vector.
    Uniform provides less rotation robustness, but stronger robustness to noise than ror, with a much smaller feature vector.
Options:
    "ror" → rotation invariant
    "uniform" → reduces dimensionality

**completed_local_binary_pattern:**
Uses the same parameters as single-scale LBP. Computationally more expensive than LBP, but extracts more texture detail
than LBP or LTP.


Additionally, this benchmarker supports extraction of single or multiple texture feature vectors
    per image. In the case where multiple texture feature vectors are utilized (referred to as 'Multi-Scale'), the feature vectors
    from each distinct texture extraction operation will be concatenated. To configure this variant of texture extraction, use
    the following pattern, which gives and example of performing Completed Local Binary Pattern analysis three times at different pixel radii. 
    (Note: the pattern is essentially placing 'multi_scale' at the 'texure extraction tecnique' entry location
    in the configuration, and nesting the desired texture extraction techniques inside this level as a list.)

```yaml
texture_extraction:
  multi_scale:
    - completed_local_binary_pattern:
        P: 8
        R: 1.0
        method: "ror"
    - completed_local_binary_pattern:
        P: 8
        R: 2.0
        method: "ror"
    - completed_local_binary_pattern:
        P: 8
        R: 3.0
        method: "ror"
```


4) Matching *(LBP config)*
```yaml
matching:
  metric: "chi2"
  tolerance: 1
  top: 5
```
**metric:**
Distance function for comparing histograms
    Options:
    "chi2" → best for histogram comparison
    "cosine" → measures orientation similarity
    "hellinger" → good probabilistic distance
**tolerance:**
Maximum allowed distance for a match
    Lower value → stricter matching
    1 → effectively disables filtering
**top:**
Number of matches returned per image


5) Query Image Processing *(experiment config)*
Applies transformations to the input/query image to simulate variations before matching.
Set to null to disable. Otherwise provide parameter values depending on implementation.
```yaml
query_image_processing:
  preprocessing:
    gaussian_blur: null
    gaussian_noise: null
    illumination: null
    contrast: null
    
  cropping:
    width: null
    height: null
    random_crop: false

  resampling:
    width: null
    height: null
    method: "lanczos"
```
**preprocessing**
    **gaussian_blur:**
    Sigma value for a gaussian filter to use on the image.
    Values between 0 and 2 are common, with 1.0 recomennded for moderate noise or greater.
    **gaussian_noise:**
    Sigma value for random noise to be added to an image.
    For 8-bit image data, the following range of values and their relative 'level of severity' are:
    0        - no noise
    1 to 10  - mild noise
    11 to 20 - moderate noise
    20+      - heavy noise
    **illumination:**
    Adjust brightness through a scaling factor.
    1.0      - no change
    1.5      - 150% of original brightness levels
    0.5      - 50% of original brightness levels.
    **contrast:**
    Adjust contrast levels through same scaling mechanic as illumination.

**cropping**
    **width / height:**
    Size of patch to crop out of original image. The resulting patch is used
    for texture analysis and matching. If random crop is set to false, the cropped
    patch will always be the center patch of the original image. If set to true, the
    patch will be from a random section of the image.
    **random_crop:**
    true → random region
    false → center crop

**resampling**
    **width / height:**
    Will resize the image being used to a resolution of width * height.
    This processing step is performed *after* any cropping.
    null = no resizing
    **method**
    Options:
        "lanczos" (high quality, slower)
        "bilinear" (balanced)
        "nearest" (fast, low quality)
        "bicubic" (smooth scaling)


6) Target Image Processing *(experiment config)*
The same transformations and processing steps can be applied to the target image set as the query set, though
generally these values should be left null in the 'target image processing' section of the configration
to match query images against raw, known values. However, this can be useful for experimenting with matching against
different resolutions or matching varying patches of query images against varying patches of target images without
needing to explicitly curate an additional dataset.


7) Data Engineering *(experiment config)*
```yaml
data_engineering:
  histogram_smoothing: null
```
**histogram_smoothing:**
Applies smoothing to LBP histograms
    Helps reduce noise sensitivity


8) Output *(experiment config)*
```yaml
output:
  save_csv: true
  save_pdf: false
  visualize: false
```
**save_csv:**
Saves raw per-match results
**save_pdf:**
Saves report/visual output
**visualize:**
Displays match results in a GUI window

Note: per-experiment results are saved under a new directory as `/results/<lbp_name>__<experiment_name>/match_results.csv` (or the report PDF). Regardless of these options, an aggregate summary CSV with one row per experiment is always written (see *Outputs* above).
---

#### Datasets

There are multiple datasets provided. The TextureSwatches_ManualCapture is a dataset of photographs taken by hand on a collenction
of 'texture swatches' which can be found [this Amazon link](https://www.amazon.com/Autistic-Children-Assorted-Educational-Equipment/dp/B0CLZY3763)

The remaining datasets are curated from images sourced from the Describable Textures Dataset. Images were selected under the criteria that they were
- representative of naturally encountered textures (no computer generated textures)
- contained a single, repeated 'instance' of a texture (no compositional/mix-and-matched textures)
- the texture comprised the majority or all of the image's contents

 There are three datasets containing images at different rotations, 'WellDefinedTextures_10Rotations_64', 'WellDefinedTextures_10Rotations_128', and
 'WellDefinedTextures_10Rotations_256', each of which contain instances of a texture image at 10 different rotations of 36 degrees, 72 degrees, 108 degrees... up to 324 degrees in increments of 36 degrees. This serves to gather examples of textures rotated into orientations which do not fall perfectly along the x and y axis,
 as working with such rotations can give misleading results in terms of rational invariance due to how bits are shifted in the ror and uniform LBP encoding schemes.
These rotated variants are in the resolution labeled at the end of their respective directory's identifier.

There is an image set labeled as 'WellDefinedTextures_128' which contains only the original, unrotated images in a 128x128 resolution.

Lastly, there is a dataset named 'DTD_TexturePatches_ExampleSet' which contains an array of textured images from the DTD dataset and at different rotations.
This dataset is useful for showing how LBP works on certain types of images, but shouldn't be used for refinement of any texture extraction setups to be used
in the real world due to the inclusion of textures which would not be encountered in the real world, as well as an imprecise labeling scheme.

The recommended setup to test isolated texture extraction and matching capabilities is to utilize the WellDefinedTextures_10Rotations_128 set
as a query set against the WellDefinedTextures_128 dataset as the target set. This will test all rotated variants of an image (including any noise configured
to be added) against their non-rotated counterparts.