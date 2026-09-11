from pathlib import Path
from PIL import Image,ImageFilter,ImageDraw
from scipy import ndimage
import cv2,numpy as np,json,os
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'outputs/naifrog-v4.4';SRC=ROOT/'work/naifrog-v4'
(OUT/'rgba').mkdir(exist_ok=True,parents=True)
def connected(mask):
    seed=np.zeros_like(mask);seed[0]=mask[0];seed[-1]=mask[-1];seed[:,0]=mask[:,0];seed[:,-1]=mask[:,-1]
    return ndimage.binary_propagation(seed,mask=mask)
def eye_fix(rgb,rgba,bounds=(90,45,235,230)):
    r,g,b=rgb.astype(float).transpose(2,0,1);green=(g>r*1.12)&(g>b*1.15)&(g>30)
    left,top,right,bottom=bounds
    green[:top]=False;green[bottom:]=False;green[:,:left]=False;green[:,right:]=False
    # Cluster green fragments per moving eye. No fixed face-height assumption:
    # float rises above the old y=100 cutoff, and half blinks split an iris.
    clusters,n=ndimage.label(ndimage.binary_dilation(green,iterations=4))
    near=ndimage.binary_dilation(rgba[:,:,3]>127,iterations=5)
    enclosed=np.zeros(green.shape,dtype=bool)
    for threshold in [28,64]:
        visible=rgb.max(axis=2)>threshold;enclosed |= ndimage.binary_fill_holes(visible)&~visible
    mask=np.zeros(green.shape,np.uint8);eyes=[]
    for k in range(1,n+1):
        region=green&(clusters==k);y,x=np.where(region)
        if len(x)<5 or not (region&near).any():continue
        if x.max()-x.min()>40 or y.max()-y.min()>35:continue
        cv2.fillConvexPoly(mask,cv2.convexHull(np.column_stack([x,y]).astype(np.int32)),255)
        roi=np.zeros(green.shape,bool);roi[max(0,y.min()-3):y.max()+4,max(left,x.min()-3):min(right,x.max()+4)]=True
        mask[enclosed&roi]=255
        eyes.append([int(x.min()),int(y.min()),int(x.max()),int(y.max())])
    out=rgba.copy();sel=mask>0;out[sel,:3]=rgb[sel];out[sel,3]=255
    assert not np.any(out[~sel]!=rgba[~sel])
    return out,eyes,int(np.count_nonzero(sel&(rgba[:,:,3]<255)))
report=json.loads((OUT/'repair-audit.json').read_text())if os.environ.get('NAIFROG_LAUGH_ONLY')else {'eyes':{},'laughHands':[]}
report['laughHands']=[]
for key in ([] if os.environ.get('NAIFROG_LAUGH_ONLY') else ['idle','scratch','listen','talk','belly','float','dizzy']):
    dest=OUT/'rgba'/key;dest.mkdir(exist_ok=True);cap=cv2.VideoCapture(str(SRC/f'sources/{key}.mp4'));count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));records=[]
    for i in range(count):
        ok,bgr=cap.read();assert ok
        rgb=cv2.resize(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB),(288,512),interpolation=cv2.INTER_AREA)
        p=ROOT/f'outputs/naifrog-v4.2/idle-rgba/{i:04d}.png'if key=='idle'else SRC/f'rgba/{key}/{i:04d}.png'
        a=np.array(Image.open(p));new,eyes,n=eye_fix(rgb,a);Image.fromarray(new).save(dest/f'{i:04d}.png')
        records.append({'frame':i,'irisBounds':eyes,'restoredPixels':n})
    cap.release();report['eyes'][key]=records;print(key,'eye pixels',sum(r['restoredPixels']for r in records),flush=True)
def new_laugh_alpha(rgb):
    values=rgb.astype(np.int16);border=np.concatenate((rgb[0],rgb[-1],rgb[:,0],rgb[:,-1]));background=np.median(border,axis=0).astype(np.int16)
    lum=values.mean(2);chroma=values.max(2)-values.min(2);distance=np.abs(values-background).max(2)
    certain=((lum>=236)&(chroma<=52))|((distance<=36)&(lum>=215)&(chroma<=58));bg=connected(certain)
    fringe=((lum>=185)&(chroma<=48))|((distance<=66)&(lum>=175)&(chroma<=62))
    for _ in range(5):bg |= fringe&ndimage.binary_dilation(bg)
    # The previous threshold chroma<=60 admitted the brown hands and stomach
    # into the connected floor region. Neutral floor is much less chromatic.
    ground=(lum>=48)&(chroma<=12);ground[:int(len(rgb)*.67)]=False;bg |= connected(ground)
    labels,n=ndimage.label(~bg);sizes=np.bincount(labels.ravel());sizes[0]=0;fg=labels==sizes.argmax()
    alpha=np.array(Image.fromarray(fg.astype(np.uint8)*255).filter(ImageFilter.GaussianBlur(.72)));alpha[alpha<4]=0;alpha[alpha>251]=255
    return alpha
raw=np.load(ROOT/'work/naifrog-v4.4/laugh-rgb.npy',mmap_mode='r');dest=OUT/'rgba/legacy-laugh';dest.mkdir(exist_ok=True)
for i,rgb in enumerate(raw):
    original=np.array(Image.open(ROOT/f'work/naifrog-v3/frames-rgba/{i:04d}.png'));fixed=ROOT/f'work/naifrog-v3-review/fixed-{i:04d}.png';old=np.array(Image.open(fixed))if fixed.exists()else original
    candidate=new_laugh_alpha(rgb);roi=np.zeros(candidate.shape,bool);roi[50:395,40:270]=True
    # Preserve every previously approved negative-space repair around raised hands.
    protected=old[:,:,3]<original[:,:,3]
    color=rgb.astype(np.int16)
    # Only restore source-colored anatomy, never neutral white/gray pockets
    # between the legs which the narrower floor rule can leave disconnected.
    anatomy=(color[:,:,0]>color[:,:,2]+15)&(color[:,:,1]>color[:,:,2]+4)
    # Restore interior anatomy; retain the existing outer matte instead of
    # making white-background antialias pixels on the silhouette opaque.
    anatomy=ndimage.binary_erosion(anatomy,iterations=2)
    dark_hand=(color[:,:,0]<170)&(color[:,:,0]>color[:,:,2]+8)&(color[:,:,1]>color[:,:,2]+2)
    anatomy |= dark_hand
    # Below the hand region, cream-colored pixels are floor shadow. The feet
    # (including almost-neutral dark toes) are distinctly darker in the source.
    anatomy[335:]=color[335:].max(axis=2)<170
    # During the lying segment feet are raised; low dark pixels instead form
    # the contact shadow. Keep its previously correct lower silhouette.
    if 409<=i<=454:anatomy[335:]=False
    restore=roi&anatomy&(~protected)&(candidate>old[:,:,3]);new=old.copy();new[:,:,3][restore]=candidate[restore];new[:,:,:3][restore]=rgb[restore]
    new,eye_bounds,eye_pixels=eye_fix(rgb,new,(0,0,rgb.shape[1],395))
    new[protected]=old[protected]
    assert np.array_equal(new[protected],old[protected]);assert (new[:,:,3]>=old[:,:,3]).all()
    Image.fromarray(new).save(dest/f'{i:04d}.png');report['laughHands'].append({'frame':i,'restoredPixels':int(restore.sum()),'opaqueRestoredPixels':int(((old[:,:,3]<128)&(new[:,:,3]>=240)).sum())})
report['passed']=True;report['method']={'eyes':'Moving per-iris source contour and enclosed dark pixels; source RGB, no color replacement','hands':'Neutral-floor threshold rejects brown hand/stomach pixels; locally restore original source alpha/RGB; prior raised-hand gap repairs protected'}
report['method']['feet']='Restore source pixels with max(R,G,B)<170 below y335 except lying frames409-454; retain prior lower silhouette there'
report['method']['legacyEyes']='Apply moving iris repair across full legacy source bounds'
(OUT/'repair-audit.json').write_text(json.dumps(report,indent=2));print('laugh restored',sum(r['opaqueRestoredPixels']for r in report['laughHands']),flush=True)
# Focused before/after source-resolution evidence.
ids=[124,128,130,132,135,137,139,141,145,150,160,175,195,270,300];sheet=Image.new('RGB',(5*300,3*240),'#ab417a');d=ImageDraw.Draw(sheet)
for j,i in enumerate(ids):
    old=Image.open(ROOT/f'work/naifrog-v3/frames-rgba/{i:04d}.png');new=Image.open(dest/f'{i:04d}.png')
    for z,a in enumerate([old,new]):
        a=a.crop((60,155,205,280)).resize((150,200));sheet.paste(a,(j%5*300+z*150,j//5*240+25),a)
    d.text((j%5*300+4,j//5*240+4),f'{i} BEFORE / REPAIRED',fill='white')
sheet.save(OUT/'qa/laugh-hands-repaired.jpg')
