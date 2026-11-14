# Whole-image synthetic media detection pilot

This offline experiment compares the existing UniversalFakeDetect head with a Pratyaksh-trained linear head. Both use the pinned, frozen CLIP ViT-L/14 encoder and official UniversalFakeDetect center-crop preprocessing. The experiment targets fully generated still images. The live whole-image detector and SBI face-forgery check retain their existing configurations.

## Data and protocol

- Source: [TheKernel01/Tiny-GenImage](https://huggingface.co/datasets/TheKernel01/Tiny-GenImage), revision `89c4fe9efd0ebc7ce5c7641ef57d578ccd639c69`. The dataset card lists CC BY-NC-SA 4.0. This is a local research pilot.
- Training: 224 source images, 112 real and 112 synthetic from ADM, BigGAN, GLIDE, SD15, VQDM and Wukong. Three versions per source yielded 672 training inputs.
- Development: 64 source images, 192 inputs. Each head's cutoff maximized development balanced accuracy before either head scored the test.
- Test: 48 labeled real photos and 48 Midjourney images. Midjourney was absent from both training and development for the new head.
- Variants: original, resized/JPEG re-save, and a simulated screenshot with a frame. Both classes received the same transformations. The simulated screenshots were made with Pillow and represent one layout. Variants share the base image's split and are correlated.
- Exact decoded-pixel duplicates and near matches by 64-bit dHash distance at most 3 were screened across splits. The source dataset does not expose capture identities or prompt families for this sample.

## Test results

| Inputs | UniversalFakeDetect | Pratyaksh CLIP head |
| --- | ---: | ---: |
| Original images | 67/96 (69.79%) | 75/96 (78.13%) |
| JPEG edits | 44/96 (45.83%) | 59/96 (61.46%) |
| Simulated screenshots | 47/96 (48.96%) | 61/96 (63.54%) |
| All versions | 158/288 (54.86%) | 195/288 (67.71%) |
| Synthetic versions caught | 63/144 (43.75%) | 137/144 (95.14%) |
| Genuine versions falsely flagged | 49/144 (34.03%) | 86/144 (59.72%) |
| Coverage | 288/288 | 288/288 |

The new head caught more synthetic images at the selected cutoff and produced more false alarms. The false-positive rate is too high for an automatic live verdict. Evaluate a preselected low-false-positive operating point on a fresh, independently sourced set spanning multiple held-out generators and real screenshot layouts before considering deployment.

## Reproduce

From the backend directory, using the existing model files and virtual environment:

```sh
.venv/bin/python -m evaluation.train_still_image_head \
  --cache data/datasets/tiny-genimage-pilot \
  --output evaluation/results/whole-image-tiny-genimage-reproduction
```

The run writes a source manifest, protocol, selected thresholds, classifier weights, paired test predictions and metrics. The original run is under `evaluation/results/whole-image-tiny-genimage-v1/`. Raw images and experiment artifacts remain local.

## Fresh test of stricter cutoffs

We selected an operating cutoff for each fixed classifier using a 10% false-alarm budget on the earlier development split. Then we evaluated both policies on 90 fresh Tiny-GenImage source files (45 genuine and 15 each from Midjourney, SD15 and BigGAN). All 270 inputs scored, including resized JPEG and simulated screenshot variants. Variants of one source are correlated. Midjourney was absent from the custom head's training, while SD15 and BigGAN were represented there.

| Classifier and cutoff | Genuine inputs flagged | AI-generated inputs caught | Balanced accuracy |
| --- | ---: | ---: | ---: |
| UniversalFakeDetect, previous | 36/135 | 77/135 | 65.19% |
| UniversalFakeDetect, stricter | 2/135 | 18/135 | 55.93% |
| Pratyaksh, previous | 89/135 | 130/135 | 65.19% |
| Pratyaksh, stricter | 54/135 | 117/135 | 73.33% |

On untouched originals, the stricter Pratyaksh cutoff scored 73/90 correctly (81.11%), with 14/45 genuine images flagged and 42/45 AI images caught. Its 40% false-positive rate across variants exceeded the development budget. The stricter UniversalFakeDetect cutoff missed 117/135 synthetic inputs. Keep both policies offline. A future training run should use diverse genuine hard negatives, including edits and real forwarding captures, and reserve a separate external test before choosing a live operating point.

Reproduction uses `evaluation.check_still_image_false_alarms` with `--prior evaluation/results/whole-image-tiny-genimage-v1`, `--cache data/datasets/tiny-genimage-pilot`, and a new `--output` directory. The completed local run is under `evaluation/results/whole-image-low-false-alarm-v1/`.
