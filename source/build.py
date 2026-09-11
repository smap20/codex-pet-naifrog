from pathlib import Path
from PIL import Image
import cv2,numpy as np,json,hashlib
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'outputs/naifrog-v4.4';PET=(Path.home()/'.codex/pets/naifrog');(OUT/'pet').mkdir(exist_ok=True)
spec=json.loads((PET/'animation-v4.3.json').read_text());old=Image.open(PET/spec['spritesheetPath']).convert('RGBA');sheet=old.copy()
audit=json.loads((ROOT/'outputs/naifrog-v4.3/frame-audit.json').read_text())
bindings={'idle':'idle','running':'scratch','waiting':'listen','review':'talk','waving':'belly','failed':'dizzy','running-right':'float','jumping':'legacy-laugh'}
def transform(im,m):
    a=np.array(im,dtype=np.float32)/255;a[:,:,:3]*=a[:,:,3,None]
    z=cv2.warpAffine(a,m,(192,208),flags=cv2.INTER_LANCZOS4,borderMode=cv2.BORDER_CONSTANT,borderValue=0)
    alpha=np.clip(z[:,:,3],0,1);rgb=np.clip(z[:,:,:3]/np.maximum(alpha[:,:,None],1e-8),0,1)
    b=np.rint(np.dstack([rgb,alpha])*255).astype(np.uint8);b[b[:,:,3]==0,:3]=0;return Image.fromarray(b)
records={};expected={}
for state,key in bindings.items():
    matrix=np.array(audit['clips'][key]['matrix'],dtype=np.float32);records[state]=[]
    for i,f in enumerate(spec['states'][state]['frames']):
        source=Image.open(OUT/f'rgba/{key}/{i:04d}.png').convert('RGBA')
        if state=='jumping':
            canvas=Image.new('RGBA',(192,224))
            canvas.paste(source.crop((11,37,266,377)).resize((148,198),Image.Resampling.LANCZOS),(17,5))
            # The former crop was measured after toes had been deleted. Extend
            # its coverage at the exact same scale, without moving old pixels.
            extended=source.resize((148,210),Image.Resampling.LANCZOS,box=(11,37,266,37+210*340/198))
            canvas.paste(extended.crop((0,198,148,210)),(17,203))
            source=canvas
        result=transform(source,matrix);x,y=f['column']*192,f['row']*208;box=(x,y,x+192,y+208);before=np.array(old.crop(box));after=np.array(result)
        # Lanczos has negative lobes: adding source opacity can otherwise lower
        # a neighboring output alpha. A repair must never create fresh holes.
        after[:,:,3]=np.maximum(after[:,:,3],before[:,:,3]);result=Image.fromarray(after)
        changed=np.any(before!=after,axis=2);sheet.paste(result,(x,y));expected[(x,y)]=result
        records[state].append({'frame':i,'changedPixels':int(changed.sum()),'restoredOpaquePixels':int(((before[:,:,3]<128)&(after[:,:,3]>=240)).sum()),'maxAlphaDrop':int(np.maximum(before[:,:,3].astype(int)-after[:,:,3],0).max())})
        assert not np.any(after[[0,-1],:,3]>16) and not np.any(after[:,[0,-1],3]>16)
assert not any(r['changedPixels'] for r in records['idle']),'Previously fixed idle changed'
dest=OUT/'pet/animation-v4.4.webp';sheet.save(dest,lossless=True,method=4,exact=True);decoded=Image.open(dest).convert('RGBA')
for (x,y),im in expected.items():assert decoded.crop((x,y,x+192,y+208)).tobytes()==im.tobytes()
assert dest.stat().st_size*4/3 < 48*1024*1024
previous=spec['spritesheetPath'];spec['spritesheetPath']=dest.name;(OUT/'pet/animation-v4.4.json').write_text(json.dumps(spec,indent=2))
oldspec=json.loads((PET/'animation-v4.3.json').read_text());compare={**spec,'spritesheetPath':previous};assert compare==oldspec,'Timing/geometry/state changed'
pet=json.loads((PET/'pet.json').read_text());pet['animationManifestPath']='animation-v4.4.json';(OUT/'pet/pet.json').write_text(json.dumps(pet,indent=2,ensure_ascii=False))
report={'passed':True,'manifestOnlyChangesAtlasPath':True,'transformsUnchanged':True,'frameCount':len(expected),'bytes':dest.stat().st_size,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'states':records}
(OUT/'frame-audit.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:{'changedFrames':sum(r['changedPixels']>0 for r in v),'restoredOpaquePixels':sum(r['restoredOpaquePixels']for r in v),'maxAlphaDrop':max(r['maxAlphaDrop']for r in v)}for k,v in records.items()},indent=2))
