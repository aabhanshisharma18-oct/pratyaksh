# Pratyaksh dataset expansion

Reviewed 14 November 2026. Maximum additional disk footprint: **20 GB decimal**, including downloaded archives, extracted media and retained caches together. Do not download 20 GB of archives and then extract a second 20 GB copy. The initial disk check found about 43 GiB free.

The linked Awesome repository is a discovery list, not one trained model or a downloadable unified dataset. Its MIT licence does not grant access to each dataset it lists. This catalogue consolidates repeated image/video entries; it is not a claim that we used them.

## What is already local

`/Users/Dell/Desktop/Dataset` contains 190,335 image files: Train/Real 70,001; Train/Fake 70,001; Validation/Real 19,787; Validation/Fake 19,641; Test/Real 5,413; Test/Fake 5,492. These are raw disk counts, not trained-on counts or independently sourced examples. The upstream dataset identity, terms, decoding, exact/perceptual duplicates and related identities need review before scaling training. Do not move Test or Validation into Train.

Existing local assets also include a DeepfakeTIMIT archive and a cached Tiny-GenImage pilot. Compressed archives are inventoried separately; cached `.image` assets are counted as files and do not imply downloaded full datasets. Earlier Celeb-DF training reports remain valid historical records, but its full extracted folder was not found by the top-level Desktop scan.

A machine-readable inventory is in `backend/data/datasets/expansion-20261114/local-inventory.json`. This ignored local record includes file counts, byte sizes and archive counts. It is deliberately separate from training metrics.

## First 20 GB allocation (targets, not known download sizes)

1. Up to 8 GB for a FaceForensics++ c23 subset after author approval, covering genuine sources and several manipulation methods. Keep all versions of one source together. Original SBI pretraining already used FF++ c23: this is adaptation data, not an unseen-data test of that pretrained model.
2. Up to 6 GB for a DFDC subset once access is configured, adding different actors and recording conditions. Retain original-video relationships from metadata.
3. Up to 3 GB for an approved external challenge subset, preferably DeepSpeak corrected v1.1 or FakeAVCeleb. Keep this subset for evaluation if it has never been used for tuning.
4. Reserve at least 3 GB for temporary archive/extraction overhead and metadata. If a provider offers only a larger indivisible archive, do not start it within this budget.

Actual archive sizes must be checked before each transfer. These targets do not promise that a provider offers a downloadable shard of that size. Avoid using all listed datasets as training data; some should remain unseen tests.

## Immediate access actions

- [FaceForensics++ author access page](https://github.com/ondyari/FaceForensics#access): submit the author's request form. No request has been submitted by this tool.
- [DFDC official page](https://ai.meta.com/datasets/dfdc/) and [Kaggle data](https://www.kaggle.com/c/deepfake-detection-challenge/data): authorise access through the provider. No Kaggle credentials/client were found locally. Do not paste private keys into chat.
- [FakeAVCeleb access](https://github.com/DASH-Lab/FakeAVCeleb#access-request-form): author approval is required. Audio and visual authenticity labels are distinct; an altered video does not imply its audio is synthetic.
- [DeepSpeak author card](https://huggingface.co/datasets/faridlab/deepspeak_v1): gated institutional access. The author recommends corrected v1.1 instead of v1.0. The full v1.0 download is about 40 GB and is outside this budget.
- [WildDeepfake author page](https://github.com/xingjunm/wild-deepfake): an agreement is required. The linked official mirror does not waive it. This consists of face sequences, not necessarily complete videos with audio.
- [DFGC-21](https://github.com/bomb2peng/DFGC_starterkit/tree/master/DFGC-21%20dataset): request access; preserve it for held-out testing as the authors recommend. It derives from Celeb-DF v2 test sources, so it must not be treated as independent identities.
- [iFakeFaceDB](https://github.com/socialabubi/iFakeFaceDB): official ZIP server failed to connect during this review. Do not substitute a random mirror. It is synthetic-face-only and needs appropriate genuine controls.

## Complete catalogue

- **UADFV** — head-pose-era face forgeries. Proposed role: external_test. Access: Locate current author-hosted download; access not verified. [Source](https://arxiv.org/abs/1811.00656).
- **Eye Blinking Video (EBV)** — early blinking-focused examples. Proposed role: historical_test. Access: Listed download returned 404 during review. [Source](https://www.cs.albany.edu/~lsw/downloads.html).
- **DeepfakeTIMIT** — older face swaps. Proposed role: historical_test. Access: Archive already local; genuine source and fake archive are separate. [Source](https://conradsanderson.id.au/vidtimit/).
- **DFFD** — multiple facial manipulation types. Proposed role: training_candidate. Access: Author site timed out during review; verify access and terms. [Source](https://cvlab.cse.msu.edu/project-ffd.html).
- **Google/Jigsaw DeepFakeDetection** — actor-based face manipulations. Proposed role: training_candidate. Access: Hosted through FaceForensics; request access. [Source](https://github.com/ondyari/FaceForensics).
- **Celeb-DF v1** — earlier Celeb-DF release. Proposed role: overlap_review. Access: Overlap with v2 must be checked; do not count as independent data. [Source](https://github.com/yuezunli/celeb-deepfakeforensics).
- **Celeb-DF v2** — face swaps. Proposed role: existing_or_relocate. Access: Previously used locally; full extracted location not found in Desktop top-level scan. [Source](https://github.com/yuezunli/celeb-deepfakeforensics).
- **DFDC** — diverse actors and face swaps. Proposed role: training_candidate. Access: Requires Kaggle credentials/accepted data access, or Meta AWS registration; neither is configured locally. [Source](https://www.kaggle.com/c/deepfake-detection-challenge/data).
- **FaceForensics++** — Deepfakes, Face2Face, FaceSwap, NeuralTextures. Proposed role: training_candidate. Access: Author request form required; c23 subset first after approval. [Source](https://github.com/ondyari/FaceForensics).
- **FFIW-10K** — multiple faces in natural scenes. Proposed role: multi_face_test. Access: Review author download instructions and permissions. [Source](https://github.com/tfzhou/FFIW).
- **DeeperForensics-1.0** — face swaps and real-world perturbations. Proposed role: robustness_test. Access: Review access process; use a bounded subset after approval. [Source](https://github.com/EndlessSora/DeeperForensics-1.0).
- **WildDeepfake** — internet-collected face sequences. Proposed role: external_test. Access: Author requires an agreement; official Hugging Face mirror exists, but mirror availability does not remove author access conditions. [Source](https://github.com/xingjunm/wild-deepfake).
- **ForgeryNet** — multiple editing and forgery methods. Proposed role: later_expansion. Access: Large collection; select relevant tasks and review official terms. [Source](https://github.com/yinanhe/forgerynet).
- **World Leaders dataset (WLDR)** — person-of-interest research. Proposed role: research_reference. Access: Paper reference; no current general-purpose download verified. [Source](https://openaccess.thecvf.com/content_CVPR_2019/html/Agarwal_Protecting_World_Leaders_Against_Deep_Fakes_CVPR_2019_paper.html).
- **FakeAVCeleb** — real/fake audio and real/fake video combinations. Proposed role: multimodal_test. Access: Author request form required; keep audio and visual labels separate. [Source](https://github.com/DASH-Lab/FakeAVCeleb).
- **DeepSpeak** — webcam face swaps and lip-sync. Proposed role: external_test. Access: Gated request and institutional licence; author recommends corrected v1.1 over v1.0. [Source](https://huggingface.co/datasets/faridlab/deepspeak_v1).
- **IDForge** — identity-driven multimodal forgeries. Proposed role: later_expansion. Access: Review author access process and modality-specific labels. [Source](https://github.com/xyyandxyy/IDForge).
- **Celeb-DF++** — face swaps, reenactment and talking faces. Proposed role: external_test_after_overlap_audit. Access: Author approval required; overlaps original Celeb-DF sources. [Source](https://github.com/OUC-VAS/Celeb-DF-PP).
- **iFakeFaceDB** — synthetic faces with fingerprint modification. Proposed role: image_robustness_test. Access: Official download server failed to connect on 2026-11-14; research-only use stated by author. [Source](https://github.com/socialabubi/iFakeFaceDB).
- **100k Faces / Generated Photos** — synthetic faces. Proposed role: optional_licence_review. Access: Do not scrape; confirm current dataset availability and licensing. [Source](https://generated.photos/).
- **DFGC 2021** — challenge-generated facial forgeries. Proposed role: external_test_only. Access: Request form required; author recommends held-out testing only; derived from Celeb-DF v2 test sources. [Source](https://github.com/bomb2peng/DFGC_starterkit).

## Import after downloading approved media

Create a CSV with these columns:

```csv
dataset,path,label,split,group_id,manipulation_type,ground_truth,terms,source_url
```

Labels are `genuine` or `synthetic`; splits are `train`, `development` or `test`. Paths are relative to the CSV or absolute. Document actual provider labels and applicable terms. Global group IDs must connect related originals and variants even across datasets. Do not invent one unrelated group ID per frame or variant.

Run from the backend folder:

```bash
./.venv/bin/python -m evaluation.prepare_dataset_expansion merge \
  --index /absolute/path/to/reviewed-index.csv \
  --budget-gb 20 \
  --output evaluation/manifest.expansion.local.json
```

The importer hashes files, removes same-split exact duplicates and rejects conflicting labels, cross-split duplicate bytes and cross-split source groups. It preserves supplied splits. It does not independently verify licences, labels, decoding, identities or perceptual near duplicates; use the existing still-image audit and review source metadata before training. Indexed bytes are checked against the budget, but the importer does not download/copy data and cannot account for unrelated caches or archives: the combined on-disk budget must still be checked.

The output follows the existing D1 evaluation manifest fields. Evaluate image, face and video methods separately; do not merge different manipulation tasks into a single accuracy. This is not yet a multi-corpus training runner. Adapt the existing trainers after the approved corpus and source grouping are known.

For the temporal trainer, convert reviewed video rows to its documented list format with integer labels, and keep its opening-window/single-face coverage limitations. For image training, retain each derived frame's original video/source group and sample a bounded number of frames per source. Thousands of neighbouring frames are not thousands of independent examples.

## Measurement and honest status

Freeze model selection and thresholds on development data. Keep a genuinely untouched external test. Report video/source counts separately from image/frame counts, per-class and per-dataset errors, coverage and uncertainty. Earlier reused pilot tests are not fresh final holdouts.

At preparation time **no new dataset media was downloaded, no model was retrained, and no accuracy increase was measured**. Inventory, catalogue and import preparation are complete; author access and available shards determine the next data acquisition step. Do not publish restricted media to GitHub.
