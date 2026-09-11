from pathlib import Path
import json,hashlib,shutil
import numpy as np
from scipy import ndimage
from PIL import Image,ImageFilter,ImageDraw
ROOT=Path(__file__).resolve().parent;BASE=ROOT.parents[1];OUT=BASE/'outputs/naifrog-v3.1';OUT.mkdir(exist_ok=True);PET=OUT/'pet';PET.mkdir(exist_ok=True)
oldpet=(Path.home()/'.codex/pets/naifrog');spec=json.loads((oldpet/'animation-v3.json').read_text());atlas=Image.open(oldpet/'animation-v3.webp').convert('RGBA');changes=[]
for i in range(206,260):
 src=Image.open(ROOT.parent/'naifrog-v3/frames-rgba'/f'{i:04d}.png').convert('RGBA');a=np.array(src);rgb=a[:,:,:3].astype(float)
 roi=np.zeros(a.shape[:2],bool);roi[75:134,60:115]=True;roi[65:130,169:219]=True
 # Only neutral-white pockets in the two known negative spaces; not the hands.
 seeds=roi&(rgb.min(2)>225)&(np.ptp(rgb,axis=2)<32)&(a[:,:,3]>200)
 label,n=ndimage.label(seeds);counts=np.bincount(label.ravel());keep=[k for k in range(1,n+1) if counts[k]>=4];seeds=np.isin(label,keep)
 if not seeds.any():continue
 allowed=roi&(rgb.min(2)>178)&(np.ptp(rgb,axis=2)<64)
 mask=ndimage.binary_propagation(seeds,mask=allowed)
 # A soft edge around this newly opened space. All pixels outside this local
 # neighborhood, including teeth, belly and fingers, remain byte-identical.
 feather=np.asarray(Image.fromarray(mask.astype('uint8')*255).filter(ImageFilter.GaussianBlur(.45))).astype(float)/255
 new=a.copy();new[:,:,3]=np.rint(a[:,:,3]*(1-feather)).astype('uint8')
 # Remove the white matte only at the newly exposed gap edge, taking RGB from
 # the nearest existing colored foreground. Alpha and anatomy stay separate.
 boundary=ndimage.binary_dilation(mask,iterations=2)&(~mask)&(new[:,:,3]>0)
 colored=(np.ptp(rgb,axis=2)>75)&(a[:,:,3]>240)&(~mask)
 _,indices=ndimage.distance_transform_edt(~colored,return_indices=True)
 for c in range(3):new[:,:,c][boundary]=a[:,:,c][tuple(indices[:,boundary])]
 new[new[:,:,3]==0,:3]=0
 changed=np.any(new!=a,axis=2);assert not changed[140:290].any(),'mouth/belly modified'
 # Reuse precisely the v3 common crop and transform.
 im=Image.new('RGBA',(192,208));im.paste(Image.fromarray(new).crop((11,37,266,377)).resize((148,198),Image.Resampling.LANCZOS),(17,5))
 row=11+i//64;col=i%64;atlas.paste(im,(col*192,row*208))
 Image.fromarray(new).save(ROOT/f'fixed-{i:04d}.png')
 changes.append({'frame':i,'time_s':i/30,'removed_background_pixels':int(mask.sum()),'changed_source_pixels':int(changed.sum()),'output_rgba_sha256':hashlib.sha256(im.tobytes()).hexdigest()})
assert changes
atlas.save(PET/'animation-v3.1.webp',lossless=True,exact=True,method=4)
decoded=Image.open(PET/'animation-v3.1.webp').convert('RGBA');old=Image.open(oldpet/'animation-v3.webp').convert('RGBA');assert np.array_equal(np.array(decoded.crop((0,0,12288,2288))),np.array(old.crop((0,0,12288,2288))))
changed_ids={x['frame'] for x in changes}
for i in range(462):
 x=i%64*192;y=(11+i//64)*208;box=(x,y,x+192,y+208)
 if i not in changed_ids:assert decoded.crop(box).tobytes()==old.crop(box).tobytes()
 else:assert hashlib.sha256(decoded.crop(box).tobytes()).hexdigest()==next(v['output_rgba_sha256'] for v in changes if v['frame']==i)
spec['spritesheetPath']='animation-v3.1.webp';(PET/'animation-v3.1.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2));manifest=json.loads((oldpet/'pet.json').read_text());manifest['animationManifestPath']='animation-v3.1.json';(PET/'pet.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
report={'source_frames':462,'duration_ms':15400,'changes':changes,'only_source_gap_regions_edited':True,'other_frames_and_states_pixel_identical':True,'source':'upstream frames, same v3 crop/resize','method':'local neutral-white negative-space alpha correction; nearest foreground color only on new gap boundary'}
(OUT/'repair-audit.json').write_text(json.dumps(report,indent=2))
# Source-resolution before/after and final pet-size samples.
ids=[211,217,221,227,238,251,252,254];contact=Image.new('RGB',(len(ids)*170,2*245),(32,38,46));d=ImageDraw.Draw(contact)
for n,i in enumerate(ids):
 for r in [0,1]:
  f=ROOT/f'fixed-{i:04d}.png' if r and (ROOT/f'fixed-{i:04d}.png').exists() else ROOT.parent/'naifrog-v3/frames-rgba'/f'{i:04d}.png'
  im=Image.open(f).crop((60,50,220,180)).resize((160,130));contact.paste(im,(n*170,r*245),im)
  x=i%64*192;y=(11+i//64)*208;small=(decoded if r else old).crop((x,y,x+192,y+208)).resize((86,93));contact.paste(small,(n*170+38,r*245+136),small)
  d.text((n*170+4,r*245+230),f'{"AFTER" if r else "BEFORE"} {i}',fill='white')
contact.save(OUT/'hand-fix-contact.jpg')
print('Fixed',len(changes),'frames:',min(changed_ids),'..',max(changed_ids),flush=True)
