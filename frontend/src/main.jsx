import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Aperture, ArrowDownToLine, Check, Cpu, ImagePlus, LoaderCircle, LockKeyhole, Maximize2, RefreshCw, ScanFace, Sparkles, UploadCloud, WandSparkles, Zap, SlidersHorizontal, Eraser, Image as ImageIcon } from 'lucide-react';
import './style.css';

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
const defaults = { brightness: 1, contrast: 1, saturation: 1, sharpness: 1, skin_smooth: 0, blemish: 0 };

function App() {
  const [file, setFile] = useState(null); const [preview, setPreview] = useState(''); const [result, setResult] = useState('');
  const [quality, setQuality] = useState('4k'); const [busy, setBusy] = useState(false); const [drag, setDrag] = useState(false);
  const [health, setHealth] = useState(null); const [analysis, setAnalysis] = useState(null); const [analyzing, setAnalyzing] = useState(false); const [error, setError] = useState('');
  const [livePreview, setLivePreview] = useState(''); const [liveStatus, setLiveStatus] = useState('Upload a photo to start live editing'); const [imageDimensions, setImageDimensions] = useState(null); const previewRequest = useRef(0);
  const [settings, setSettings] = useState(defaults); const [activeTab, setActiveTab] = useState('auto'); const [removeBg, setRemoveBg] = useState(false); const [bgColor, setBgColor] = useState('#18243a'); const [bgFile, setBgFile] = useState(null);
  const inputRef = useRef(null); const bgInputRef = useRef(null);
  useEffect(() => { fetch(`${API}/api/health`).then(r => r.json()).then(setHealth).catch(() => setHealth({ ok: false })); }, []);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  useEffect(() => () => { if (result) URL.revokeObjectURL(result); }, [result]);
  useEffect(() => () => { if (livePreview) URL.revokeObjectURL(livePreview); }, [livePreview]);
  const chooseFile = useCallback(async picked => {
    if (!picked) return; if (picked.type && !picked.type.startsWith('image/')) { setError('Please choose an image file.'); return; }
    if (picked.size > 50 * 1024 * 1024) { setError('Maximum image size is 50 MB.'); return; }
    setError(''); setFile(picked); setPreview(''); setImageDimensions(null); setAnalysis(null); setAnalyzing(true); setSettings(defaults); setRemoveBg(false); setBgFile(null); setLiveStatus('Preparing live preview…'); if (livePreview) { URL.revokeObjectURL(livePreview); setLivePreview(''); }
    if (preview) URL.revokeObjectURL(preview); if (result) { URL.revokeObjectURL(result); setResult(''); }
    try { const body = new FormData(); body.append('file', picked); const response = await fetch(`${API}/api/preview`, { method: 'POST', body });
      if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(data.detail || 'This image format could not be opened.'); }
      setPreview(URL.createObjectURL(await response.blob())); const ab = new FormData(); ab.append('file', picked); const ar = await fetch(`${API}/api/analyze`, { method: 'POST', body: ab }); if (ar.ok) setAnalysis(await ar.json());
    } catch (e) { setError(e.message || 'Could not read image. Check local backend.'); setFile(null); setAnalysis(null); } finally { setAnalyzing(false); }
  }, [preview, result]);
  const setValue = (key, value) => setSettings(old => ({ ...old, [key]: Number(value) }));
  const enhance = async () => {
    if (!file || busy) return; setBusy(true); setError('');
    try { const body = new FormData(); body.append('file', file); body.append('quality', quality); const r = await fetch(`${API}/api/enhance`, { method: 'POST', body });
      if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.detail || 'Enhancement failed.'); } const blob = await r.blob(); if (result) URL.revokeObjectURL(result); setResult(URL.createObjectURL(blob));
    } catch (e) { setError(e.message || 'Cannot connect to local AI server.'); } finally { setBusy(false); }
  };
  // Debounced live rendering: each slider change updates the preview automatically.
  useEffect(() => {
    if (!file || !preview) return;
    const requestId = ++previewRequest.current;
    const controller = new AbortController();
    setLiveStatus('Updating preview…');
    const timer = setTimeout(async () => {
      try {
        const body = new FormData();
        body.append('file', file);
        Object.entries(settings).forEach(([k, v]) => body.append(k, String(v)));
        body.append('remove_background', String(removeBg));
        body.append('background_color', bgColor);
        if (bgFile) body.append('background', bgFile);
        const response = await fetch(`${API}/api/edit-preview`, { method: 'POST', body, signal: controller.signal });
        if (!response.ok) {
          const data = await response.json().catch(() => ({}));
          throw new Error(data.detail || 'Live preview could not be updated.');
        }
        const nextUrl = URL.createObjectURL(await response.blob());
        if (requestId === previewRequest.current) {
          setLivePreview(old => { if (old) URL.revokeObjectURL(old); return nextUrl; });
          setLiveStatus('Live preview updated');
        } else URL.revokeObjectURL(nextUrl);
      } catch (err) {
        if (err.name !== 'AbortError' && requestId === previewRequest.current) setLiveStatus(err.message || 'Preview unavailable');
      }
    }, 280);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [file, preview, settings, removeBg, bgColor, bgFile]);
  const resetEditor = () => { setSettings(defaults); setRemoveBg(false); setBgFile(null); setLiveStatus('Resetting to original…'); };
  const download = (url = livePreview || result) => { if (!url) return; const a = document.createElement('a'); a.href = url; a.download = 'BORINA-EDITED-PHOTO.png'; a.click(); };
  const slider = (label, key, min, max, step, suffix='') => <label className="edit-slider"><span>{label}<b>{settings[key].toFixed(2)}{suffix}</b></span><input type="range" min={min} max={max} step={step} value={settings[key]} onChange={e => setValue(key,e.target.value)}/></label>;
  return <div className="app-shell studio-shell">
    <header className="topbar studio-topbar">
      <div className="brand"><div className="brand-mark"><Aperture size={21}/></div><div><div className="brand-name">BORINA <span>AI</span></div><div className="brand-sub">PHOTO ENHANCER PRO</div></div></div>
      <div className="top-right"><div className="local-pill"><span className={`status-dot ${health?.ok?'online':''}`}/>{health?.ok?'LOCAL ENGINE CONNECTED':'LOCAL ENGINE OFFLINE'}</div><div className="avatar">B</div></div>
    </header>
    <main className="studio-main">
      <section className="studio-preview panel">
        <div className="studio-section-head"><div><div className="step-label">PHOTO WORKSPACE</div><h2>{file ? 'Your photo' : 'Start editing'}</h2></div><div className="studio-head-actions"><span className="format-tag">JPG · PNG · HEIC · WEBP</span><button className="compact-button" onClick={()=>inputRef.current?.click()}><ImagePlus size={14}/> {file?'Change':'Upload'}</button></div></div>
        <input ref={inputRef} type="file" accept="image/*,.heic,.heif,.avif,.tif,.tiff,.bmp,.gif,.ico" hidden onChange={e=>chooseFile(e.target.files?.[0])}/>
        <div className={`studio-canvas ${drag?'dragging':''}`} onDragOver={e=>{e.preventDefault();setDrag(true)}} onDragLeave={()=>setDrag(false)} onDrop={e=>{e.preventDefault();setDrag(false);chooseFile(e.dataTransfer.files?.[0])}} onClick={()=>!file&&inputRef.current?.click()}>
          {file ? <img src={livePreview || result || preview} alt="Photo preview" onLoad={e=>setImageDimensions({width:e.currentTarget.naturalWidth,height:e.currentTarget.naturalHeight})}/> : <div className="studio-empty"><div className="upload-icon"><UploadCloud size={27}/></div><strong>Drop your photo here</strong><span>or click Upload to browse</span><small>Maximum file size · 50 MB</small></div>}
          {file && <><div className="canvas-chip">{livePreview?'LIVE EDIT PREVIEW':result?'ENHANCED RESULT':'ORIGINAL PHOTO'}</div>{imageDimensions&&<div className="canvas-dimensions">{imageDimensions.width.toLocaleString()} × {imageDimensions.height.toLocaleString()} px · AUTO FIT</div>}</>}
        </div>
        <div className="studio-preview-footer">
          <div className="studio-fileline">{file?<><ImageIcon size={14}/><span title={file.name}>{file.name}</span><button className="text-button" onClick={()=>{setFile(null);setAnalysis(null);setImageDimensions(null);setPreview('');setResult('');setLivePreview('');setLiveStatus('Upload a photo to start live editing');}}>Remove</button></>:<span className="muted">Original identity first · no generative face replacement</span>}</div>
          <div className="studio-actions"><span className="live-status"><i className="live-dot"/>{file?liveStatus:'Ready for your photo'}</span>{(livePreview||result)&&<button className="download-button" onClick={()=>download(livePreview||result)}><ArrowDownToLine size={14}/> Download</button>}</div>
        </div>
      </section>
      <section className="studio-controls panel">
        <div className="studio-section-head control-heading"><div><div className="step-label">EDITING CONTROLS</div><h2>Make it yours</h2></div><button className="reset-button" onClick={resetEditor}><RefreshCw size={13}/> Reset</button></div>
        <div className="studio-tabs" role="tablist" aria-label="Editing tools">
          <button className={activeTab==='auto'?'active':''} onClick={()=>setActiveTab('auto')}><Zap size={14}/> Auto</button>
          <button className={activeTab==='light'?'active':''} onClick={()=>setActiveTab('light')}><Sparkles size={14}/> Light & color</button>
          <button className={activeTab==='portrait'?'active':''} onClick={()=>setActiveTab('portrait')}><ScanFace size={14}/> Portrait</button>
          <button className={activeTab==='background'?'active':''} onClick={()=>setActiveTab('background')}><Eraser size={14}/> Background</button>
        </div>
        <div className="studio-tab-content">
          {activeTab==='auto'&&<>
            <div className="analysis-card compact-analysis"><div className="analysis-title"><Sparkles size={14}/>{analyzing?'ANALYZING PHOTO':'SMART AUTO ANALYSIS'}</div>{analysis?<><div className="analysis-tags">{analysis.recommendations.map((x,i)=><span key={i}>{x}</span>)}</div><small>{analysis.width} × {analysis.height} · Original image preserved</small></>:<small>Upload a photo to analyze lighting, color and detail.</small>}</div>
            <div className="quality-title">Export quality</div>
            <div className="quality-row">{[{id:'1080p',title:'Full HD',sub:'1920 px'},{id:'4k',title:'4K UHD',sub:'3840 px'},{id:'8k',title:'8K UHD',sub:'7680 px'}].map(q=><button key={q.id} className={`quality-mini ${quality===q.id?'selected':''}`} onClick={()=>setQuality(q.id)}><strong>{q.title}</strong><small>{q.sub}</small></button>)}</div>
            <div className="engine-card compact-engine"><div className="engine-icon"><Cpu size={17}/></div><div className="engine-copy"><strong>Local Photo Engine</strong><span>{health?.neural_ai_ready?'AI upscaling ready':'Local image processing'}</span></div><span className={`engine-indicator ${health?.ok?'good':''}`}/></div>
            <button className="enhance-button" disabled={!file||busy} onClick={enhance}>{busy?<><LoaderCircle className="spin" size={17}/> PROCESSING...</>:<><WandSparkles size={17}/> ONE-CLICK AI ENHANCE <span className="button-arrow">→</span></>}</button>
            <div className="privacy-line"><LockKeyhole size={12}/> Your photo stays on your computer.</div>
          </>}
          {activeTab==='light'&&<div className="slider-stack">{slider('Brightness','brightness',0.5,1.5,0.01)}{slider('Contrast','contrast',0.5,1.5,0.01)}{slider('Saturation','saturation',0,1.5,0.01)}{slider('Sharpness','sharpness',0.5,2,0.05)}<small className="tab-hint">Adjustments update the preview automatically.</small></div>}
          {activeTab==='portrait'&&<div className="slider-stack">{slider('Skin smoothing','skin_smooth',0,1,0.01)}{slider('Texture cleanup','blemish',0,1,0.01)}<p className="editor-help">Use subtle values for natural skin. These are general smoothing controls, not precise individual blemish removal.</p></div>}
          {activeTab==='background'&&<div className="background-tab"><label className="toggle-line"><input type="checkbox" checked={removeBg} onChange={e=>setRemoveBg(e.target.checked)}/> Remove original background</label><div className="background-options"><label>New background color <input type="color" value={bgColor} onChange={e=>setBgColor(e.target.value)}/></label><button className="secondary-button" onClick={()=>bgInputRef.current?.click()}><ImageIcon size={14}/> Choose background photo</button><input ref={bgInputRef} type="file" accept="image/*" hidden onChange={e=>setBgFile(e.target.files?.[0]||null)}/>{bgFile&&<small>{bgFile.name}</small>}</div><p className="editor-help">Background removal requires the optional local AI model.</p></div>}
        </div>
        {error&&<div className="error-banner compact-error">{error}</div>}
      </section>
    </main>
  </div>;
}
createRoot(document.getElementById('root')).render(<App/>);
