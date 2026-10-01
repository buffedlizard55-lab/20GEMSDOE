/* Local GeoTIFF pre-flight + template-matched writer. No server/contest upload.
 * Supports classic TIFF, float32, strips/tiles, none/LZW/deflate, predictor 1/3.
 * Unsupported formats fail CLOSED: no zero padding, missing-mask PASS or metadata-only PASS.
 * BigTIFF is not supported here; that is a checker limitation, not an official prohibition.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.GemsTiff = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';
  var MAX_PIXELS = 40000000;
  var trustedMasks = new WeakMap();
  function trustedMask(mask) {
    var original=trustedMasks.get(mask);
    if (!original || mask.length!==original.length) return false;
    for (var i=0;i<original.length;i++) if (mask[i]!==original[i]) return false;
    return true;
  }
  var EXPECT = { width: 3292, height: 3730, epsg: 32611, res: 100, originX: 243350, originY: 4508550,
    footprintPixels: 5167373, footprintBytes: 15681,
    footprintSha256: '9ec93feb7c07793a81332a30853e4971d51f6bf19791a09f195307f3d1f9893f' };
  Object.freeze(EXPECT);
  var TYPE_SIZE = { 1:1, 2:1, 3:2, 4:4, 5:8, 6:1, 7:1, 8:2, 9:4, 10:8, 11:4, 12:8, 13:4, 16:8, 17:8, 18:8 };
  function integer(n) { return Number.isSafeInteger(n) && n > 0; }
  function bound(offset, length, size, context) {
    if (!Number.isSafeInteger(offset) || !Number.isSafeInteger(length) || offset < 0 || length < 0 || offset + length > size)
      throw new Error('Truncated/out-of-bounds ' + context + '.');
  }
  function parseTiff(u8) {
    if (!(u8 instanceof Uint8Array)) throw new Error('TIFF bytes must be Uint8Array.');
    bound(0,8,u8.length,'TIFF header');
    var dv = new DataView(u8.buffer,u8.byteOffset,u8.byteLength), bom = dv.getUint16(0,false), le;
    if (bom === 0x4949) le = true; else if (bom === 0x4d4d) le = false; else throw new Error('Bad TIFF byte-order mark.');
    var magic = dv.getUint16(2,le);
    if (magic === 43) throw new Error('BigTIFF is unsupported by this local checker; use the Python validator.');
    if (magic !== 42) throw new Error('Bad TIFF magic number.');
    var ifd = dv.getUint32(4,le);
    if (ifd < 8) throw new Error('Missing TIFF image directory.');
    bound(ifd,2,u8.length,'image directory');
    var n = dv.getUint16(ifd,le), tags = {};
    if (n > 4096) throw new Error('Implausibly large TIFF directory.');
    bound(ifd,2+n*12+4,u8.length,'image directory entries');
    for (var i=0;i<n;i++) {
      var e=ifd+2+i*12, tag=dv.getUint16(e,le), type=dv.getUint16(e+2,le), count=dv.getUint32(e+4,le);
      if (!TYPE_SIZE[type] || count > 5000000 || tags[tag]) throw new Error('Unsupported/duplicate/corrupt TIFF tag ' + tag + '.');
      var size=TYPE_SIZE[type]*count, offset=size<=4 ? e+8 : dv.getUint32(e+8,le);
      bound(offset,size,u8.length,'tag '+tag);
      tags[tag]={type:type,count:count,offset:offset};
    }
    function vals(t) {
      if (!t) return [];
      var out=[];
      for (var k=0;k<t.count;k++) {
        var o=t.offset+k*TYPE_SIZE[t.type], v;
        if (t.type===3) v=dv.getUint16(o,le);
        else if (t.type===4 || t.type===13) v=dv.getUint32(o,le);
        else if (t.type===8) v=dv.getInt16(o,le);
        else if (t.type===9) v=dv.getInt32(o,le);
        else if (t.type===12) v=dv.getFloat64(o,le);
        else if (t.type===11) v=dv.getFloat32(o,le);
        else if (t.type===16 || t.type===18) v=Number(dv.getBigUint64(o,le));
        else if (t.type===17) v=Number(dv.getBigInt64(o,le));
        else if (t.type===5 || t.type===10) {
          var get=t.type===5 ? 'getUint32' : 'getInt32';
          v=dv[get](o,le)/dv[get](o+4,le);
        } else v=dv.getUint8(o);
        out.push(v);
      }
      return out;
    }
    function ascii(t) {
      if (!t) return null;
      if (t.type!==2) throw new Error('Invalid ASCII tag type.');
      var s='';
      for (var k=0;k<t.count;k++) { var c=dv.getUint8(t.offset+k); if (!c) break; s+=String.fromCharCode(c); }
      return s;
    }
    function one(t,d) { var v=vals(tags[t]); if (v.length>1) throw new Error('Invalid scalar tag '+t); return v.length ? v[0] : d; }
    var info={ littleEndian:le, extraIfds:dv.getUint32(ifd+2+n*12,le)!==0,
      width:one(256),height:one(257),bitsPerSample:vals(tags[258]),compression:one(259,1),
      samplesPerPixel:one(277,1),rowsPerStrip:one(278,0xffffffff),planar:one(284,1),sampleFormat:vals(tags[339]),
      predictor:one(317,1),photometric:one(262,1),orientation:one(274,1),
      tileWidth:one(322,0),tileHeight:one(323,0),stripOffsets:vals(tags[273]),stripByteCounts:vals(tags[279]),
      tileOffsets:vals(tags[324]),tileByteCounts:vals(tags[325]),pixelScale:vals(tags[33550]),
      tiePoint:vals(tags[33922]),modelTransform:vals(tags[34264]),geoKeys:vals(tags[34735]),
      nodata:ascii(tags[42113]),gdalMetadata:ascii(tags[42112]),epsg:0,rasterType:0 };
    info.tiled=!!(tags[324] || tags[325] || info.tileWidth || info.tileHeight);
    var keys=info.geoKeys;
    if (keys.length) {
      if (keys.length<4 || keys[0]!==1 || keys.length!==4+keys[3]*4) throw new Error('Malformed GeoKey directory.');
      for (var g=4;g<keys.length;g+=4) {
        if ((keys[g]===3072 || keys[g]===1025) && keys[g+1]===0 && keys[g+2]===1) {
          if (keys[g]===3072) info.epsg=keys[g+3]; else info.rasterType=keys[g+3];
        }
      }
    }
    return info;
  }

  function lzwDecode(input,expected) {
    if (!integer(expected) || expected>MAX_PIXELS*4) throw new Error('Invalid LZW output size.');
    var out=new Uint8Array(expected),op=0,prefix=new Int32Array(4096),suffix=new Uint8Array(4096),first=new Uint8Array(4096),len=new Uint16Array(4096);
    for (var i=0;i<256;i++) { prefix[i]=-1;suffix[i]=i;first[i]=i;len[i]=1; }
    var next=258,size=9,buf=0,bits=0,ip=0,prev=-1;
    function read() {
      while (bits<size) { if (ip>=input.length) throw new Error('Truncated LZW stream (missing end code).'); buf=((buf<<8)|input[ip++])>>>0;bits+=8; }
      var code=(buf>>>(bits-size))&((1<<size)-1);
      bits-=size;buf=buf&((1<<bits)-1);return code;
    }
    function emit(code) {
      var length=len[code],p=op+length-1,c=code,steps=0;
      if (!length || op+length>expected) throw new Error('LZW decoded size exceeds block or invalid dictionary.');
      while (c>=0) {
        if (++steps>length || c>=4096) throw new Error('Invalid LZW dictionary chain.');
        out[p--]=suffix[c];c=prefix[c];
      }
      if (steps!==length) throw new Error('Invalid LZW word length.');
      op+=length;
    }
    for (;;) {
      var code=read();
      if (code===257) { if (op!==expected) throw new Error('Truncated LZW output: '+op+' of '+expected+' bytes.'); return out; }
      if (code===256) { next=258;size=9;prev=-1;continue; }
      if (prev===-1) { if (code>255) throw new Error('Invalid first LZW code.');emit(code);prev=code;continue; }
      if (code<next) {
        emit(code);
        if (next<4096) { prefix[next]=prev;suffix[next]=first[code];first[next]=first[prev];len[next]=len[prev]+1;next++; }
      } else if (code===next && next<4096) {
        prefix[next]=prev;suffix[next]=first[prev];first[next]=first[prev];len[next]=len[prev]+1;emit(next);next++;
      } else throw new Error('Invalid LZW code '+code+'.');
      prev=code;
      if (next===511) size=10;else if (next===1023) size=11;else if (next===2047) size=12;
    }
  }
  async function inflate(u8,expected) {
    if (typeof DecompressionStream!=='function') throw new Error('Deflate needs a current browser with DecompressionStream.');
    var zlib=u8.length>=2 && (u8[0]&15)===8 && ((u8[0]<<8)+u8[1])%31===0;
    var stream=new Blob([u8]).stream().pipeThrough(new DecompressionStream(zlib ? 'deflate' : 'deflate-raw'));
    var reader=stream.getReader(),raw=new Uint8Array(expected),pos=0;
    try {
      for (;;) {
        var r=await reader.read();if (r.done) break;
        if (pos+r.value.length>expected) { await reader.cancel();throw new Error('Deflate output exceeds block size.'); }
        raw.set(r.value,pos);pos+=r.value.length;
      }
    } finally { reader.releaseLock(); }
    if (pos!==expected) throw new Error('Truncated deflate output: '+pos+' of '+expected+' bytes.');
    return raw;
  }
  function undoFloatPredictor(row,pixels,littleEndian) {
    var out=new Uint8Array(row.length);
    for (var i=1;i<row.length;i++) row[i]=(row[i]+row[i-1])&255;
    for (var k=0;k<pixels;k++) for (var b=0;b<4;b++) out[4*k+b]=row[(littleEndian ? 3-b : b)*pixels+k];
    return out;
  }
  async function decodeChunk(bytes,info,rows,cols) {
    var expected=rows*cols*4,raw;
    if (!integer(expected) || expected>MAX_PIXELS*4) throw new Error('Invalid TIFF block dimensions.');
    if (info.compression===1) { if (bytes.length!==expected) throw new Error('Uncompressed block size mismatch (no padding allowed).');raw=bytes; }
    else if (info.compression===5) raw=lzwDecode(bytes,expected);
    else if (info.compression===8 || info.compression===32946) raw=await inflate(bytes,expected);
    else throw new Error('Unsupported TIFF compression '+info.compression+'.');
    if (info.predictor===3) {
      var out=new Uint8Array(expected);
      for (var r=0;r<rows;r++) out.set(undoFloatPredictor(raw.slice(r*cols*4,(r+1)*cols*4),cols,info.littleEndian),r*cols*4);
      return out;
    }
    if (info.predictor!==1) throw new Error('Unsupported float32 predictor '+info.predictor+'.');
    return raw;
  }
  async function readRaster(u8,info) {
    var W=info.width,H=info.height;
    if (!integer(W) || !integer(H) || W*H>MAX_PIXELS) throw new Error('Invalid/oversized raster dimensions.');
    if (info.samplesPerPixel!==1 || info.bitsPerSample.length!==1 || info.bitsPerSample[0]!==32 || info.sampleFormat.length!==1 || info.sampleFormat[0]!==3)
      throw new Error('Only single-band float32 pixels can be decoded.');
    if (info.planar!==1 && info.planar!==2) throw new Error('Unsupported planar configuration.');
    var out=new Uint8Array(W*H*4),r;
    function chunk(offset,count) { if (!integer(count)) throw new Error('Missing/empty TIFF block.');bound(offset,count,u8.length,'raster block');return u8.subarray(offset,offset+count); }
    if (info.tiled) {
      var tw=info.tileWidth,th=info.tileHeight;
      if (!integer(tw) || !integer(th) || tw*th>MAX_PIXELS || info.stripOffsets.length) throw new Error('Invalid/conflicting tile layout.');
      var across=Math.ceil(W/tw),down=Math.ceil(H/th),count=across*down;
      if (info.tileOffsets.length!==count || info.tileByteCounts.length!==count) throw new Error('Missing or extra TIFF tiles.');
      for (var t=0;t<count;t++) {
        var tile=await decodeChunk(chunk(info.tileOffsets[t],info.tileByteCounts[t]),info,th,tw);
        var x0=(t%across)*tw,y0=Math.floor(t/across)*th;
        for (r=0;r<th && y0+r<H;r++) { var width=Math.min(tw,W-x0);out.set(tile.subarray(r*tw*4,r*tw*4+width*4),((y0+r)*W+x0)*4); }
      }
    } else {
      if (!integer(info.rowsPerStrip)) throw new Error('Invalid rows-per-strip.');
      var rps=Math.min(info.rowsPerStrip,H),strips=Math.ceil(H/rps);
      if (info.stripOffsets.length!==strips || info.stripByteCounts.length!==strips) throw new Error('Missing or extra TIFF strips.');
      for (var s=0;s<strips;s++) {
        var rows=Math.min(rps,H-s*rps),strip=await decodeChunk(chunk(info.stripOffsets[s],info.stripByteCounts[s]),info,rows,W);
        out.set(strip,s*rps*W*4);
      }
    }
    if (!info.littleEndian) for (var i=0;i<out.length;i+=4) { var a=out[i],b=out[i+1];out[i]=out[i+3];out[i+1]=out[i+2];out[i+2]=b;out[i+3]=a; }
    return new Float32Array(out.buffer,0,W*H);
  }

  function decodeMaskRuns(bytes,total) {
    if (!(bytes instanceof Uint8Array) || !integer(total) || total>MAX_PIXELS) throw new Error('Invalid footprint dimensions/bytes.');
    var mask=new Uint8Array(total),pos=0,n=0,val=0,run=0;
    while (pos<bytes.length) {
      var v=0,shift=0,b;
      do {
        if (pos>=bytes.length || shift>28) throw new Error('Truncated/overflowed footprint run.');
        b=bytes[pos++];v+=(b&127)*Math.pow(2,shift);shift+=7;
      } while (b&128);
      if (!Number.isSafeInteger(v) || v>total-n || (!v && run>0)) throw new Error('Invalid footprint run length.');
      if (val) mask.fill(1,n,n+v);n+=v;val^=1;run++;
    }
    if (n!==total) throw new Error('Footprint covers '+n+' pixels, expected '+total+'.');
    return mask;
  }
  async function sha256(bytes) {
    if (typeof crypto!=='undefined' && crypto.subtle) {
      var digest=await crypto.subtle.digest('SHA-256',bytes);
      return Array.from(new Uint8Array(digest)).map(function (b) { return b.toString(16).padStart(2,'0'); }).join('');
    }
    if (typeof require==='function') return require('crypto').createHash('sha256').update(bytes).digest('hex');
    throw new Error('Secure SHA-256 unavailable; use HTTPS or the Python validator.');
  }
  async function decodeFootprint(bytes) {
    if (bytes.length!==EXPECT.footprintBytes || await sha256(bytes)!==EXPECT.footprintSha256) throw new Error('Footprint SHA-256/size mismatch; pixel checks cannot be trusted.');
    var mask=decodeMaskRuns(bytes,EXPECT.width*EXPECT.height),count=0;
    for (var i=0;i<mask.length;i++) count+=mask[i];
    if (count!==EXPECT.footprintPixels) throw new Error('Unexpected footprint population.');
    Object.defineProperty(mask,'gemsFootprintSha256',{value:EXPECT.footprintSha256});
    trustedMasks.set(mask,mask.slice());
    return mask;
  }
  var footprintPromises={};
  function loadFootprint(url) {
    url=url || 'data/footprint.bin';
    if (!footprintPromises[url]) footprintPromises[url]=fetch(url).then(function (r) {
      if (!r.ok) throw new Error('Footprint download HTTP '+r.status);return r.arrayBuffer();
    }).then(function (b) { return decodeFootprint(new Uint8Array(b)); }).catch(function (e) { delete footprintPromises[url];throw e; });
    return footprintPromises[url];
  }
  function fullTransform(info) {
    var t=info.modelTransform,scale=info.pixelScale,tie=info.tiePoint,result;
    if (t.length) {
      if (t.length!==16 || !t.every(Number.isFinite) || t[12]!==0 || t[13]!==0 || t[14]!==0 || t[15]!==1) return null;
      result=[t[0],t[1],t[3],t[4],t[5],t[7]];
      if (scale.length || tie.length) return null;  // conflicting transform encodings
    } else {
      if (scale.length!==3 || tie.length!==6 || !scale.concat(tie).every(Number.isFinite) || scale[0]<=0 || scale[1]<=0 || tie[2]!==0) return null;
      result=[scale[0],0,tie[3]-tie[0]*scale[0],0,-scale[1],tie[4]+tie[1]*scale[1]];
    }
    if (info.rasterType===2) { result[2]-=.5*(result[0]+result[1]);result[5]-=.5*(result[3]+result[4]); }
    else if (info.rasterType!==1) return null;
    return result;
  }
  function preflight(field,info,footprint) {
    var checks=[],W=info.width,H=info.height,total=W*H,stats=null;
    function add(id,title,pass,detail,hard,fix) { checks.push({id:id,title:title,pass:!!pass,detail:detail,hard:hard!==false,fix:fix || ''}); }
    var transform=fullTransform(info),target=[100,0,243350,0,-100,4508550];
    var geoOk=transform && transform.every(function (v,i) { return Math.abs(v-target[i])<1e-8; });
    add('single_band','One band / image',info.samplesPerPixel===1 && !info.extraIfds,'samples/pixel='+info.samplesPerPixel,true,'Use one float32 image without additional image directories for this checker.');
    add('float32','32-bit float',info.bitsPerSample.length===1 && info.bitsPerSample[0]===32 && info.sampleFormat.length===1 && info.sampleFormat[0]===3,'bits='+info.bitsPerSample+', sampleFormat='+info.sampleFormat,true,'Write float32.');
    add('shape','Template dimensions',W===EXPECT.width && H===EXPECT.height,W+' x '+H,true,'Copy the official template grid.');
    add('crs','CRS EPSG:32611',info.epsg===EXPECT.epsg,'EPSG '+(info.epsg || 'missing'),true,'Copy the template CRS.');
    add('geotransform','Full six-term template transform',geoOk,transform ? transform.join(', ') : 'missing/conflicting transform or raster-type key',true,'Copy every affine coefficient and raster-type convention.');
    add('orientation','Top-left pixel storage',info.orientation===1,'orientation='+info.orientation,true,'Re-export top-left orientation.');
    var pixelData=field instanceof Float32Array && field.length===total && W===EXPECT.width && H===EXPECT.height;
    var maskOk=footprint instanceof Uint8Array && footprint.length===EXPECT.width*EXPECT.height && trustedMask(footprint);
    add('decoded_pixels','Complete decoded float32 raster',pixelData,pixelData ? 'All pixels decoded without padding.' : 'Missing/partial/unsupported pixel data.',true,'Use a supported valid encoding; metadata alone cannot PASS.');
    add('footprint_payload_integrity','SHA-256-verified template footprint',maskOk,maskOk ? EXPECT.footprintSha256 : 'Missing/unverified footprint; cannot check pixel values.',true,'Reload the published footprint payload or use the Python template checker.');
    if (pixelData && maskOk) {
      var inNaN=0,inInf=0,inMin=Infinity,inMax=-Infinity,inPos=0,outNaN=0,outFinite=0,outInf=0,outNonZero=0,outRange=0,inCount=0,mass=0,n05=0;
      for (var i=0;i<total;i++) {
        var v=field[i];
        if (footprint[i]!==0 && footprint[i]!==1) { maskOk=false;break; }
        if (footprint[i]) {
          inCount++;
          if (Number.isNaN(v)) inNaN++;else if (!Number.isFinite(v)) inInf++;
          else { inMin=Math.min(inMin,v);inMax=Math.max(inMax,v);if (v>0) inPos++;if (v>.5) n05++;mass+=v; }
        } else if (Number.isNaN(v)) outNaN++;
        else if (!Number.isFinite(v)) outInf++;
        else { outFinite++;if (v<0 || v>1) outRange++;if (v!==0) outNonZero++; }
      }
      maskOk=maskOk && inCount===EXPECT.footprintPixels;
      add('footprint_population','Expected template mask population',maskOk,inCount.toLocaleString()+' cells',true,'Restore the verified footprint.');
      stats={footprintPixels:inCount,inNaN:inNaN,inInf:inInf,inMin:inMin,inMax:inMax,positives:inPos,over05:n05,mass:mass,outNaN:outNaN,outFinite:outFinite,outInf:outInf,outNonZero:outNonZero};
      add('footprint_nan','No NaN/Inf inside footprint',inNaN===0 && inInf===0,inNaN+' NaN, '+inInf+' Inf',true,'Fix non-finite predictions upstream; do not silently fabricate evidence.');
      add('range','Every footprint value in [0,1]',Number.isFinite(inMin) && Number.isFinite(inMax) && inMin>=0 && inMax<=1,'min='+inMin+', max='+inMax,true,'Export bounded scores, not raw logits or 255-valued masks.');
      add('outside_range','Finite outside values also in [0,1]',outRange===0,outRange+' outside-range cells',true,'Outside should be NaN, or zero for the diagnostic twin.');
      add('outside_inf','No infinite values outside footprint',outInf===0,outInf+' Inf outside',true,'Outside values should be NaN.');
      add('outside_nan','Outside footprint is NaN (official convention)',outFinite===0 && outInf===0,outNaN+' NaN, '+outFinite+' finite outside',false,'Primary artifact uses NaN outside; zero-outside twin is diagnostic only.');
    } else {
      add('footprint_nan','No NaN/Inf inside footprint',false,'Not checked: complete data or verified mask unavailable.',true);
      add('range','Every footprint value in [0,1]',false,'Not checked: complete data or verified mask unavailable.',true);
    }
    add('nodata_tag','NaN nodata tag',/^nan$/i.test((info.nodata || '').trim()),'nodata='+info.nodata,false,'Match the template NaN nodata tag.');
    var hardFail=checks.filter(function (c) { return c.hard && !c.pass; }).map(function (c) { return c.id; });
    return {ok:hardFail.length===0,officialFormatCompliant:hardFail.length===0 && !!stats && stats.outFinite===0 && stats.outInf===0,
      hardFailures:hardFail,checks:checks,stats:stats};
  }
  async function checkFile(u8,footprint,options) {
    var info,field=null,readError=null;
    try { info=parseTiff(u8); } catch (e) { return {ok:false,officialFormatCompliant:false,hardFailures:['parse'],checks:[{id:'parse',title:'Readable TIFF structure',pass:false,hard:true,detail:String(e.message || e)}],stats:null}; }
    try { field=await readRaster(u8,info); } catch (e) { readError=String(e.message || e); }
    var res=preflight(field,info,footprint);
    if (readError) { res.checks.push({id:'read',title:'Raster decoded',pass:false,detail:readError,hard:true,fix:''});res.ok=false;res.officialFormatCompliant=false;res.hardFailures.push('read'); }
    res.info={width:info.width,height:info.height,compression:info.compression,predictor:info.predictor,tiled:info.tiled,epsg:info.epsg,nodata:info.nodata};
    if (options && options.includeRaster && res.ok) res.raster=field;
    return res;
  }

  function writeSubmission(field,footprint) {
    // Pure FORMAT export: preserve every in-footprint value, never a new candidate.
    if (!(field instanceof Float32Array) || field.length!==EXPECT.width*EXPECT.height || !(footprint instanceof Uint8Array) ||
        footprint.length!==field.length || !trustedMask(footprint)) throw new Error('Verified complete scores and footprint required for export.');
    var count=0;
    for (var i=0;i<field.length;i++) if (footprint[i]) { count++;if (!Number.isFinite(field[i]) || field[i]<0 || field[i]>1) throw new Error('Invalid in-footprint score at pixel '+i+'; export refused.'); }
    if (count!==EXPECT.footprintPixels) throw new Error('Footprint population changed.');
    var n=14,ifdEnd=8+2+n*12+4,scaleOffset=ifdEnd,tieOffset=scaleOffset+24,keyOffset=tieOffset+48,nodataOffset=keyOffset+32;
    var dataOffset=(nodataOffset+4+3)&~3,totalBytes=dataOffset+field.length*4,bytes=new Uint8Array(totalBytes),dv=new DataView(bytes.buffer);
    dv.setUint16(0,0x4949,false);dv.setUint16(2,42,true);dv.setUint32(4,8,true);dv.setUint16(8,n,true);
    var e=10;
    function tag(id,type,count,value) { dv.setUint16(e,id,true);dv.setUint16(e+2,type,true);dv.setUint32(e+4,count,true);if (type===3 && count===1) dv.setUint16(e+8,value,true);else dv.setUint32(e+8,value,true);e+=12; }
    tag(256,4,1,EXPECT.width);tag(257,4,1,EXPECT.height);tag(258,3,1,32);tag(259,3,1,1);tag(262,3,1,1);
    tag(273,4,1,dataOffset);tag(277,3,1,1);tag(278,4,1,EXPECT.height);tag(279,4,1,field.length*4);tag(339,3,1,3);
    tag(33550,12,3,scaleOffset);tag(33922,12,6,tieOffset);tag(34735,3,16,keyOffset);
    // ASCII nan\0 is four bytes: TIFF stores it INLINE, not at an offset.
    dv.setUint16(e,42113,true);dv.setUint16(e+2,2,true);dv.setUint32(e+4,4,true);bytes.set([110,97,110,0],e+8);
    [100,100,0].forEach(function (v,j) { dv.setFloat64(scaleOffset+j*8,v,true); });
    [0,0,0,EXPECT.originX,EXPECT.originY,0].forEach(function (v,j) { dv.setFloat64(tieOffset+j*8,v,true); });
    [1,1,0,3,1024,0,1,1,1025,0,1,1,3072,0,1,EXPECT.epsg].forEach(function (v,j) { dv.setUint16(keyOffset+j*2,v,true); });
    for (var p=0;p<field.length;p++) dv.setFloat32(dataOffset+p*4,footprint[p] ? field[p] : NaN,true);
    return bytes;
  }
  return {EXPECT:EXPECT,parseTiff:parseTiff,readRaster:readRaster,lzwDecode:lzwDecode,decodeMaskRuns:decodeMaskRuns,
    decodeFootprint:decodeFootprint,loadFootprint:loadFootprint,sha256:sha256,fullTransform:fullTransform,
    preflight:preflight,checkFile:checkFile,writeSubmission:writeSubmission};
});
