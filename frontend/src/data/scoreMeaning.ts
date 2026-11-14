import type {Finding} from '../model';

const pilotCutoffs: Record<string, number> = {
  'pratyaksh-two-blocks-20261111-232032': 0.03699474409222603,
  'pratyaksh-still-images-backbone-20261112': 0.5533131957054138,
};

export function faceScoreMeaning(score: number, modelVersion?: string) {
  const cutoff = modelVersion ? pilotCutoffs[modelVersion] : undefined;
  if (cutoff !== undefined) {
    return score >= cutoff
      ? 'Above the pilot cutoff. This face is worth reviewing for a possible swap.'
      : 'Below the pilot cutoff. The model found little sign of a face swap.';
  }
  return 'Higher scores mean the model saw stronger signs of a face swap. This model has no live cutoff.';
}

export function scoreMeaning(finding: Finding) {
  if (finding.score?.value == null) return 'This check produced no model score.';
  const {value, positive_class: target} = finding.score;
  if (target === 'Face forgery') {
    const scope = 'This is the highest score across the faces checked.';
    const cutoff = pilotCutoffs[finding.method_version];
    if (cutoff === undefined) {
      return faceScoreMeaning(value) + ' ' + scope;
    }
    const comparison = value >= cutoff
      ? 'At least one face crossed the pilot cutoff and is worth reviewing.'
      : 'None of the faces crossed the pilot cutoff.';
    return comparison + ' ' + scope;
  }
  const direction = value < 0.5 ? 'closer to 0' : value > 0.5 ? 'closer to 1' : 'at the midpoint';
  if (target === 'Deepfake') {
    return 'This score is ' + direction + '. Higher scores mean the model saw stronger signs that the overall image was AI-generated.';
  }
  if (target === 'Spoofed speech') {
    return 'This score is ' + direction + '. Higher scores mean the model saw stronger signs of synthetic or spoofed speech.';
  }
  return finding.score.interpretation;
}

export function videoFrameScoreMeaning(score: number) {
  const direction = score < 0.5 ? 'closer to 0' : score > 0.5 ? 'closer to 1' : 'at the midpoint';
  return 'The score is '+direction+'. Higher scores indicate a stronger AI-image signal in the sampled frame.';
}
