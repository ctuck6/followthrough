import React, {useEffect, useState, useRef} from 'react';
import Modal from './components/Modal.jsx';

export default function Attachments({date, csrfToken, notify, tradeKey}) {
  const base=tradeKey?`/api/trades/${tradeKey}/attachments/`:`/api/days/${date}/attachments/`;
  const context=tradeKey?'this trade':date;
  const [items,setItems]=useState([]),[loading,setLoading]=useState(true),[uploading,setUploading]=useState(false),[error,setError]=useState('');
  const alive=useRef(true);
  const [preview,setPreview]=useState(null),[removing,setRemoving]=useState(null),[deleting,setDeleting]=useState(false),[deleteError,setDeleteError]=useState('');
  async function remove(){
    setDeleting(true);setDeleteError('');
    try{
      const response=await fetch(`${base}${removing.id}/`,{method:'DELETE',headers:{'X-CSRFToken':csrfToken}});
      if(!response.ok){let message='Could not delete this attachment. Please try again.';try{message=(await response.json()).error||message}catch{}throw Error(message)}
      setItems(previous=>previous.filter(item=>item.id!==removing.id));setRemoving(null);notify(`Attachment deleted from ${date}.`);
    }catch(e){setDeleteError(e.message)}finally{setDeleting(false)}
  }
  useEffect(()=>{
    alive.current=true;
    const controller=new AbortController();
    fetch(base,{signal:controller.signal}).then(async response=>{
      if(!response.ok)throw Error('Could not load attachments. Reopen this day to try again.');
      const result=await response.json();setItems(result.attachments);
    }).catch(e=>{if(e.name!=='AbortError')setError(e.message)}).finally(()=>{if(alive.current)setLoading(false)});
    return()=>{alive.current=false;controller.abort()};
  },[date,tradeKey]);
  async function upload(event){
    const files=Array.from(event.target.files);event.target.value='';if(!files.length)return;
    setUploading(true);setError('');let saved=0;const failures=[];
    for(const file of files){
      if(file.size===0||file.size>20*1024*1024){failures.push(`${file.name}: choose a nonempty file up to 20 MB.`);continue}
      try{
        const body=new FormData();body.append('file',file);
        const response=await fetch(base,{method:'POST',headers:{'X-CSRFToken':csrfToken},body});
        if(!response.ok){let reason='Upload failed. Please try again.';try{reason=(await response.json()).error||reason}catch{}throw Error(reason)}
        const attachment=await response.json();saved++;
        if(alive.current)setItems(previous=>[...previous,attachment]);
      }catch(e){failures.push(`${file.name}: ${e.message}`)}
    }
    if(alive.current){setUploading(false);setError(failures.join(' '))}
    if(saved)notify(`${saved===1?'Attachment saved':`${saved} attachments saved`} for ${date}.`);
  }
  return <section className="panel attachments-panel"><div className="panel-heading"><h2>{!tradeKey&&<span className="step">05</span>} {tradeKey?'Trade attachments':'Session attachments'}</h2><span className="subtle">{items.length} files</span></div>
    <label className="attachment-upload">{uploading?'Uploading…':'Add chart photos or files'}<input type="file" multiple onChange={upload} disabled={uploading||loading} aria-label="Add chart photos or files"/></label>
    <p className="footnote">Up to 20 MB per file. Select an attachment to preview it. Some file types are available to download only.</p>
    {error&&<p className="alert error" role="alert">{error}</p>}
    {loading?<p role="status">Loading attachments…</p>:items.length===0?<p className="attachment-empty">Keep your setups, entries and exits together. Add a chart screenshot to revisit this session later.</p>:<ul className="attachment-list">{items.map(item=><li className="attachment-row" key={item.id}>
      <button type="button" className="attachment-open" onClick={()=>setPreview(item)} aria-label={`View ${item.name}`}>
        {item.type.startsWith('image/')?<img src={item.url} alt="" loading="lazy"/>:<span className="attachment-file-icon" aria-hidden="true">FILE</span>}
        <span className="attachment-name">{item.name}</span>
      </button>
      <button type="button" className="attachment-trash" aria-label={`Delete ${item.name}`} title="Delete attachment" onClick={()=>{setDeleteError('');setRemoving(item)}}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/></svg></button>
    </li>)}</ul>}
    {preview&&<Modal title={preview.name} onClose={()=>setPreview(null)} className="attachment-preview">
      {preview.type.startsWith('image/')?<img className="attachment-enlarged" src={preview.url} alt={preview.name}/>:<div className="attachment-unavailable"><p>This file doesn't have an in-app preview.</p><p>Download it to view in its usual application.</p></div>}
      <div className="modal-actions"><a className="download-link" href={preview.url} download={preview.name}>Download original</a><button type="button" onClick={()=>setPreview(null)}>Close</button></div>
    </Modal>}
    {removing&&<Modal title="Delete attachment?" onClose={()=>setRemoving(null)} busy={deleting} className="attachment-confirm">
      <p>Delete <strong>{removing.name}</strong> from {context}? This permanently removes the file and cannot be undone.</p>
      {deleteError&&<p className="alert error" role="alert">{deleteError}</p>}
      <div className="modal-actions"><button type="button" autoFocus disabled={deleting} onClick={()=>setRemoving(null)}>Keep attachment</button><button type="button" className="danger-button" disabled={deleting} onClick={remove}>{deleting?'Deleting…':'Delete attachment'}</button></div>
    </Modal>}
  </section>;
}
