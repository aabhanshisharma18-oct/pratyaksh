export const imageFilterGroups = [
  ['Overview', [['visual', 'Visual Inspection'], ['file', 'File Format']]],
  ['File Analysis', [
    ['jpeg', 'JPEG Structure'], ['hex', 'Hex Viewer'], ['strings', 'Hex Strings'],
    ['exif', 'EXIF'], ['qt', 'JPEG QT'], ['ht', 'JPEG HT'],
    ['social', 'Social Media Identification'], ['thumb', 'Thumbnail'],
  ]],
  ['Global Analysis', [
    ['dct', 'DCT Plot'], ['ghosts', 'JPEG Ghosts Plot'], ['correlation', 'Correlation Plot'],
    ['dimples', 'JPEG Dimples'], ['histogram', 'Histogram'], ['color', 'Color Space'], ['fourier', 'Fourier'],
  ]],
  ['Camera Identification', [['prnu', 'PRNU Identification']]],
  ['Local Tampering Analysis', [
    ['ela', 'ELA'], ['dctMap', 'DCT Map'], ['blocking', 'Blocking Artifacts'], ['adjpeg', 'ADJPEG'],
  ]],
  ['Geometrical Analysis', [['shadows', 'Shadows']]],
  ['Deepfake Detection', [['model', 'Synthetic media scan']]],
] as const;

export type ImageFilter = typeof imageFilterGroups[number][1][number][0];
export const filterLabels = Object.fromEntries(imageFilterGroups.flatMap(([, filters]) =>
  [...filters].map(([id, label]) => [id, label]))) as Record<ImageFilter, string>;

export type InspectionResult = {
  rows?: [string,string][];
  chart?: number[];
  chartTitle?: string;
  xLabel?: string;
  yLabel?: string;
  xValues?: number[];
  detail?: string;
  image?: string;
};

export function fileInformation(file: File, bytes: Uint8Array, width: number, height: number): InspectionResult {
  const jpeg = bytes[0]===255 && bytes[1]===216;
  const png = [137,80,78,71,13,10,26,10].every((value,index)=>bytes[index]===value);
  const webp = new TextDecoder().decode(bytes.subarray(0,4))==='RIFF' &&
    new TextDecoder().decode(bytes.subarray(8,12))==='WEBP';
  const type = jpeg?'JPEG':png?'PNG':webp?'WebP':'Unrecognized';
  const extension = file.name.split('.').at(-1)?.toLowerCase();
  const matches = jpeg ? ['jpg','jpeg'].includes(extension??'') : png ? extension==='png' : webp ? extension==='webp' : false;
  return {rows:[
    ['Filename',file.name],['Detected header',type],['Extension / header',matches?'Matches':'Mismatch or unsupported header'],
    ['Reported media type',file.type||'Unknown'],['Width',String(width)],['Height',String(height)],
    ['File bytes',String(file.size)],
  ],detail:'File signature and decoded image dimensions.'};
}

const unavailable: Partial<Record<ImageFilter, string>> = {
  social: 'Platform attribution requires a validated signature database.',
  prnu: 'Camera identification requires a camera reference pattern and a matching implementation.',
  dimples: 'JPEG dimples analysis is not connected.',
  adjpeg: 'Aligned double JPEG detection is not connected.',
};

function jpegSegments(bytes: Uint8Array) {
  const segments: { id: number; offset: number; data: Uint8Array }[] = [];
  if (bytes[0] !== 255 || bytes[1] !== 216) return segments;
  segments.push({ id: 216, offset: 0, data: bytes.subarray(0, 0) });
  for (let offset = 2; bytes[offset] === 255 && offset + 1 < bytes.length;) {
    if (bytes[offset + 1] === 255) { offset++; continue; }
    const id = bytes[offset + 1];
    if (id === 217) {
      segments.push({ id, offset, data: bytes.subarray(offset, offset) });
      break;
    }
    const length = bytes[offset + 2] * 256 + bytes[offset + 3];
    if (!(length >= 2 && offset + 2 + length <= bytes.length)) break;
    segments.push({ id, offset, data: bytes.subarray(offset + 4, offset + 2 + length) });
    if (id === 218) break;
    offset += 2 + length;
  }
  return segments;
}

const hex = (byte: number) => byte.toString(16).padStart(2, '0').toUpperCase();

function exifDetails(data: Uint8Array, thumbnail: boolean): InspectionResult {
  const tiff = new DataView(data.buffer, data.byteOffset + 6, data.length - 6);
  const order = tiff.getUint16(0);
  const little = order === 0x4949;
  const u16 = (at: number) => tiff.getUint16(at, little);
  const u32 = (at: number) => tiff.getUint32(at, little);
  if ((!little && order !== 0x4d4d) || u16(2) !== 42) throw new Error('Invalid TIFF header.');
  const readDirectory = (start: number) => {
    const count = u16(start);
    if (start + 6 + count * 12 > tiff.byteLength) throw new Error('Incomplete EXIF directory.');
    return { entries: Array.from({ length: count }, (_, i) => start + 2 + i * 12), next: u32(start + 2 + count * 12) };
  };
  const main = readDirectory(u32(4));
  if (thumbnail) {
    const entries = main.next ? readDirectory(main.next).entries : [];
    const offset = entries.find(at => u16(at) === 0x0201 && u16(at + 2) === 4 && u32(at + 4) === 1);
    const length = entries.find(at => u16(at) === 0x0202 && u16(at + 2) === 4 && u32(at + 4) === 1);
    if (offset === undefined || length === undefined) return { detail: 'No embedded JPEG thumbnail found.' };
    const start = u32(offset + 8), size = u32(length + 8);
    if (size < 2 || start + size > tiff.byteLength || tiff.getUint16(start) !== 0xffd8) throw new Error('Invalid EXIF thumbnail.');
    return { image: 'data:image/jpeg;base64,' + btoa(Array.from(data.subarray(6 + start, 6 + start + size), byte => String.fromCharCode(byte)).join('')), detail: 'Embedded EXIF thumbnail.' };
  }
  const names: Record<number,string> = {
    0x0100:'Image width',0x0101:'Image height',0x010e:'Description',0x010f:'Camera make',0x0110:'Camera model',
    0x0112:'Orientation',0x011a:'X resolution',0x011b:'Y resolution',0x0128:'Resolution unit',
    0x0131:'Software',0x0132:'File timestamp',0x013b:'Artist',0x8298:'Copyright',
    0x829a:'Exposure time',0x829d:'F number',0x8822:'Exposure program',0x8827:'ISO speed',
    0x9003:'Capture timestamp',0x9004:'Digitized timestamp',0x9010:'File timezone',
    0x9011:'Capture timezone',0x9012:'Digitized timezone',0x9201:'Shutter speed',
    0x9202:'Aperture',0x9203:'Brightness',0x9204:'Exposure compensation',
    0x9207:'Metering mode',0x9208:'Light source',0x9209:'Flash',0x920a:'Focal length',
    0xa001:'Color space',0xa002:'EXIF width',0xa003:'EXIF height',0xa402:'Exposure mode',
    0xa403:'White balance',0xa405:'Focal length in 35 mm',0xa406:'Scene capture type',
    0xa431:'Body serial number',0xa434:'Lens model',
  };
  const exifPointer = main.entries.find(at=>u16(at)===0x8769 && u16(at+2)===4 && u32(at+4)===1);
  const entries = exifPointer===undefined ? main.entries : [...main.entries,...readDirectory(u32(exifPointer+8)).entries];
  const rows: [string,string][] = [['Byte order',little?'Little endian':'Big endian']];
  const typeSizes: Record<number,number> = {1:1,2:1,3:2,4:4,5:8,7:1,9:4,10:8};
  for (const at of entries) {
    const label = names[u16(at)];
    const type=u16(at+2),count=u32(at+4),size=typeSizes[type];
    if (!label||!count||!size) continue;
    const length=count*size,start=length<=4?at+8:u32(at+8);
    if (start+length>tiff.byteLength) continue;
    if (type===2) {
      rows.push([label,new TextDecoder().decode(data.subarray(6+start,6+start+length)).split('\0')[0]]);
      continue;
    }
    const values = Array.from({length:Math.min(16,count)},(_,index)=>{
      const pos=start+index*size;
      if (type===3) return String(u16(pos));
      if (type===4) return String(u32(pos));
      if (type===9) return String(tiff.getInt32(pos,little));
      if (type===5||type===10) {
        const numerator=type===5?u32(pos):tiff.getInt32(pos,little);
        const denominator=type===5?u32(pos+4):tiff.getInt32(pos+4,little);
        return denominator ? numerator+'/'+denominator+' ('+Number((numerator/denominator).toPrecision(6))+')' : 'Undefined';
      }
      return String(tiff.getUint8(pos));
    });
    rows.push([label,values.join(', ')+(count>16?' …':'')]);
  }
  return { rows, detail: 'Embedded metadata as recorded in the file.' };
}

export function inspectBytes(filter: ImageFilter, bytes: Uint8Array): InspectionResult | undefined {
  if (unavailable[filter]) return { detail: unavailable[filter] };
  if (filter === 'hex') return { rows: Array.from({length: Math.min(32, Math.ceil(bytes.length / 16))}, (_, i) => [
    (i * 16).toString(16).padStart(6, '0'), Array.from(bytes.subarray(i * 16, i * 16 + 16), hex).join(' '),
  ]), detail: 'First 512 bytes.' };
  if (filter === 'strings') {
    const prefix = new TextDecoder('windows-1252').decode(bytes.subarray(0, 65536));
    const rows: [string, string][] = Array.from(prefix.matchAll(/[ -~]{6,}/g)).slice(0, 64).map(match => [
      '0x' + match.index.toString(16), match[0].slice(0, 160),
    ]);
    return { rows, detail: rows.length ? 'Printable ASCII sequences in the first 64 KiB.' : 'No printable ASCII sequences of six or more characters in the first 64 KiB.' };
  }
  if (!['jpeg', 'exif', 'qt', 'ht', 'thumb', 'ghosts', 'ela', 'dct', 'dctMap', 'blocking'].includes(filter)) return;
  const segments = jpegSegments(bytes);
  if (!segments.length) return { detail: 'This filter requires JPEG evidence.' };
  if (filter === 'jpeg') return { rows: segments.map(({id, offset, data}) => [
    '0x' + offset.toString(16), 'FF ' + hex(id) + ' · ' + data.length + ' payload bytes',
  ]), detail: 'JPEG markers through the first scan header.' };
  if (filter === 'qt' || filter === 'ht') {
    const tables = segments.filter(segment => segment.id === (filter === 'qt' ? 0xdb : 0xc4));
    const rows: [string, string][] = [];
    for (const {data} of tables) {
      for (let at = 0; at < data.length;) {
        const info = data[at++];
        const precision = (info >> 4) + 1;
        const counts = data.subarray(at, at + 16);
        const size = filter === 'qt' ? 64 * precision : 16 + counts.reduce((sum, count) => sum + count, 0);
        if ((filter === 'qt' && precision > 2) || at + size > data.length) return { detail: 'JPEG table data is incomplete or invalid.' };
        const values = Array.from(data.subarray(at, at + size));
        rows.push([filter === 'qt' ? 'Table ' + (info & 15) : ((info >> 4) ? 'AC' : 'DC') + ' table ' + (info & 15),
          filter === 'qt' ? Array.from({length:64}, (_, i) => precision === 2 ? values[i * 2] * 256 + values[i * 2 + 1] : values[i]).join(' ')
            : 'Code counts: ' + values.slice(0, 16).join(' ') + ' · Symbols: ' + values.slice(16).map(hex).join(' ')]);
        at += size;
      }
    }
    return { rows, detail: rows.length ? (filter === 'qt' ? 'Quantization values in JPEG order.' : 'Huffman code counts by length and their symbols.') : 'No matching tables before the first scan.' };
  }
  if (filter === 'exif' || filter === 'thumb') {
    const segment = segments.find(({id, data}) => id === 0xe1 && data.length >= 14 && new TextDecoder().decode(data.subarray(0, 6)) === 'Exif\0\0');
    return segment ? exifDetails(segment.data, filter === 'thumb') : { detail: 'No JPEG EXIF segment found.' };
  }
}

export async function inspectPixels(filter: ImageFilter, image: HTMLImageElement, quality: number, coefficientIndex = 1): Promise<InspectionResult | undefined> {
  if (!['histogram', 'color', 'correlation', 'blocking', 'ela', 'ghosts', 'dct', 'dctMap', 'fourier'].includes(filter)) return;
  const canvas = document.createElement('canvas');
  const pixelSample = ['blocking', 'ela', 'ghosts', 'dct', 'dctMap'].includes(filter);
  const scale = Math.min(1, 384 / Math.max(image.naturalWidth, image.naturalHeight));
  const width = canvas.width = Math.max(1, pixelSample ? Math.min(384, image.naturalWidth) : Math.round(image.naturalWidth * scale));
  const height = canvas.height = Math.max(1, pixelSample ? Math.min(384, image.naturalHeight) : Math.round(image.naturalHeight * scale));
  const context = canvas.getContext('2d', {willReadFrequently:true});
  if (!context) throw new Error('Canvas is unavailable.');
  const ctx = context;
  if (pixelSample) ctx.drawImage(image, 0, 0, width, height, 0, 0, width, height);
  else ctx.drawImage(image, 0, 0, width, height);
  const source = ctx.getImageData(0, 0, width, height);
  const luma = (at: number) => (source.data[at * 4] * .299 + source.data[at * 4 + 1] * .587 + source.data[at * 4 + 2] * .114);
  const count = width * height;
  const crop = 'Native-resolution top-left sample (' + width + ' × ' + height + ' px).';
  if (filter === 'histogram' || filter === 'color') {
    const chart = Array<number>(32).fill(0);
    const sums = [0, 0, 0];
    for (let at = 0; at < count; at++) {
      chart[Math.min(31, Math.floor(luma(at) / 8))]++;
      for (let channel = 0; channel < 3; channel++) sums[channel] += source.data[at * 4 + channel];
    }
    if (filter==='histogram') return {chart,chartTitle:'Luma histogram',xLabel:'Luma (0–255)',yLabel:'Pixel count',
      xValues:Array.from({length:32},(_,i)=>i*8),detail:'Luma histogram from dark to light (32 bins, decoded preview).'};
    const plot = document.createElement('canvas');
    plot.width=480; plot.height=290;
    const plotContext=plot.getContext('2d');
    if (!plotContext) throw new Error('Color plot could not be created.');
    plotContext.fillStyle='#f1f5f9';plotContext.fillRect(0,0,480,290);
    const gradient = plotContext.createLinearGradient(48,0,450,0);
    ['#ff0000','#ffff00','#00ff00','#00ffff','#0000ff','#ff00ff','#ff0000'].forEach((color,i)=>gradient.addColorStop(i/6,color));
    plotContext.fillStyle=gradient; plotContext.fillRect(48,20,402,220);
    const shade = plotContext.createLinearGradient(0,20,0,240);
    shade.addColorStop(0,'rgba(255,255,255,0)');shade.addColorStop(1,'rgba(0,0,0,.9)');
    plotContext.fillStyle=shade;plotContext.fillRect(48,20,402,220);
    plotContext.fillStyle='rgba(255,255,255,.4)';
    for (let at=0;at<count;at+=4) {
      const r=source.data[at*4]/255,g=source.data[at*4+1]/255,b=source.data[at*4+2]/255;
      const max=Math.max(r,g,b),min=Math.min(r,g,b),delta=max-min;
      let hue=0;
      if (delta) {
        if (max===r) hue=60*((g-b)/delta%6);
        else if (max===g) hue=60*((b-r)/delta+2);
        else hue=60*((r-g)/delta+4);
      }
      if (hue<0) hue+=360;
      const saturation=max?delta/max:0;
      plotContext.fillRect(48+hue/360*400,238-saturation*216,1.5,1.5);
    }
    plotContext.fillStyle='#203c58';plotContext.font='12px sans-serif';
    [0,60,120,180,240,300,360].forEach(value=>plotContext.fillText(String(value),44+value/360*402,258));
    plotContext.fillText('Hue (degrees)',204,280);
    plotContext.fillText('100%',7,27);plotContext.fillText('0%',20,240);
    return {image:plot.toDataURL(),rows:['Red','Green','Blue'].map((name,i)=>['Mean '+name,(sums[i]/count).toFixed(2)]),
      detail:'HSV distribution from the decoded preview. Horizontal axis shows hue, vertical axis shows saturation (0–100%). White points represent sampled pixels.'};
  }
  if (filter === 'fourier') {
    if (width < 2) return {detail:'The image is too narrow for a horizontal frequency plot.'};
    const chart = Array.from({length:Math.min(32, Math.floor(width / 2))}, (_, bin) => {
      const angles = Array.from({length:width}, (_, x) => 2 * Math.PI * (bin + 1) * x / width);
      const basis = angles.map(angle => [Math.cos(angle), Math.sin(angle)]);
      let power = 0;
      for (let row = 0; row < height; row++) {
        let real = 0, imaginary = 0;
        for (let x = 0; x < width; x++) {
          const value = luma(row * width + x);
          real += value * basis[x][0];
          imaginary += value * basis[x][1];
        }
        power += real * real + imaginary * imaginary;
      }
      return Math.log1p(power / (height * width * width));
    });
    return {chart,xLabel:'Cycles per row',yLabel:'Log power',xValues:chart.map((_,i)=>i+1), detail:'Horizontal luma spectrum (log-scaled mean power), starting at one cycle per preview row.'};
  }
  if (filter === 'correlation') {
    if (width < 2) return {detail:'The image is too narrow for horizontal correlation.'};
    const chart = Array.from({length:Math.min(16, width - 1)}, (_, i) => {
      const lag = i + 1;
      let x = 0, y = 0, xx = 0, yy = 0, xy = 0;
      const n = (width - lag) * height;
      for (let row = 0; row < height; row++) for (let col = lag; col < width; col++) {
        const a = luma(row * width + col - lag), b = luma(row * width + col);
        x += a; y += b; xx += a * a; yy += b * b; xy += a * b;
      }
      const denominator = Math.sqrt(Math.max(0, n * xx - x * x) * Math.max(0, n * yy - y * y));
      return denominator ? (n * xy - x * y) / denominator : 0;
    });
    return {chart,xLabel:'Horizontal offset (px)',yLabel:'Correlation',xValues:chart.map((_,i)=>i+1), detail:'Horizontal Pearson luma correlation for offsets starting at 1 pixel in the decoded preview.'};
  }
  if (filter === 'blocking') {
    let boundary = 0, interior = 0, boundaryCount = 0, interiorCount = 0;
    for (let row = 0; row < height; row++) for (let col = 1; col < width; col++) {
      const delta = Math.abs(luma(row * width + col) - luma(row * width + col - 1));
      if (col % 8 === 0) { boundary += delta; boundaryCount++; }
      else { interior += delta; interiorCount++; }
    }
    return { rows: [['Across 8 px boundaries', boundaryCount ? (boundary / boundaryCount).toFixed(3) : 'Unavailable'],
      ['Within blocks', interiorCount ? (interior / interiorCount).toFixed(3) : 'Unavailable']],
      detail:crop + ' Mean horizontal luma difference. Scene edges and compression can affect both values.' };
  }
  if (filter === 'dct' || filter === 'dctMap') {
    if (width < 8 || height < 8) return {detail:'At least one full 8 × 8 block is required.'};
    const bins = Array<number>(32).fill(0);
    const map = ctx.createImageData(width, height);
    const frequencyX = coefficientIndex%8, frequencyY = Math.floor(coefficientIndex/8);
    const basisX = Array.from({length:8},(_,x)=>Math.cos((2*x+1)*frequencyX*Math.PI/16)*(frequencyX?0.5:1/Math.sqrt(8)));
    const basisY = Array.from({length:8},(_,y)=>Math.cos((2*y+1)*frequencyY*Math.PI/16)*(frequencyY?0.5:1/Math.sqrt(8)));
    for (let row = 0; row + 7 < height; row += 8) for (let col = 0; col + 7 < width; col += 8) {
      let coefficient = 0;
      for (let y = 0; y < 8; y++) for (let x = 0; x < 8; x++) coefficient += luma((row + y) * width + col + x) * basisX[x] * basisY[y];
      bins[Math.min(31, Math.floor(Math.abs(coefficient) / 32))]++;
      for (let y = 0; y < 8; y++) for (let x = 0; x < 8; x++) {
        const at = ((row + y) * width + col + x) * 4;
        map.data.fill(Math.min(255, Math.abs(coefficient)), at, at + 3);
        map.data[at + 3] = 255;
      }
    }
    const detail = crop + ' Magnitude of DCT coefficient (' + frequencyX + ', ' + frequencyY + ') in each 8 × 8 decoded luma block.';
    if (filter === 'dct') return {chart:bins,xLabel:'Absolute coefficient magnitude',yLabel:'Block count',xValues:bins.map((_,i)=>i*32),detail};
    ctx.putImageData(map, 0, 0);
    return {image:canvas.toDataURL(), detail};
  }
  async function residual(quality: number) {
    const blob = await new Promise<Blob | null>(resolve => canvas.toBlob(resolve, 'image/jpeg', quality / 100));
    if (!blob) throw new Error('JPEG recompression failed.');
    const bitmap = await createImageBitmap(blob);
    try {
      ctx.drawImage(bitmap, 0, 0);
      const decoded = ctx.getImageData(0, 0, width, height);
      const map = ctx.createImageData(width, height);
      let sum = 0;
      for (let at = 0; at < source.data.length; at += 4) {
        for (let channel = 0; channel < 3; channel++) {
          const delta = Math.abs(source.data[at + channel] - decoded.data[at + channel]);
          sum += delta * delta;
          map.data[at + channel] = Math.min(255, delta * 8);
        }
        map.data[at + 3] = 255;
      }
      ctx.putImageData(source, 0, 0);
      return {map, mse:sum / (count * 3)};
    } finally { bitmap.close(); }
  }
  if (filter === 'ela') {
    const {map} = await residual(quality);
    ctx.putImageData(map, 0, 0);
    return {image:canvas.toDataURL(), detail:crop + ' JPEG recompression residual at quality ' + quality + ' (8× display gain). Texture and compression can produce bright regions.'};
  }
  const qualities = [50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100];
  const chart: number[] = [];
  for (const value of qualities) chart.push((await residual(value)).mse);
  return {chart,xLabel:'JPEG quality',yLabel:'Mean squared error',xValues:qualities, rows:qualities.map((value, i) => [String(value), chart[i].toFixed(3)]), detail:crop + ' Mean squared recompression error across JPEG qualities 50–100.'};
}
