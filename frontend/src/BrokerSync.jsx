import React,{useEffect,useRef,useState} from 'react';
import {useAccount} from './AccountScope.jsx';

function useSyncStatus(){
 const {scopedFetch,accountId,accounts}=useAccount();
 const schwab=accounts.find(a=>String(a.id)===String(accountId))?.broker==='schwab';
 const [status,setStatus]=useState(null),[error,setError]=useState('');
 useEffect(()=>{
  let alive=true,timer;const controller=new AbortController();
  async function poll(){try{const response=await scopedFetch(schwab?'/api/schwab/sync/':'/api/broker-sync/',{signal:controller.signal});if(!response.ok)throw Error('Could not load sync status.');const value=await response.json();if(alive){setStatus(value);setError('')}}catch(e){if(alive&&e.name!=='AbortError')setError(e.message)}finally{if(alive)timer=setTimeout(poll,5000)}}
  poll();return()=>{alive=false;controller.abort();clearTimeout(timer)};
 },[accountId]);
 return {status,error};
}

export function BrokerSyncMonitor({onUpdated,notify}){
 const {status}=useSyncStatus();const {scopedFetch,refreshAccounts}=useAccount();
 const callbacks=useRef({onUpdated,notify});callbacks.current={onUpdated,notify};
 const observed=useRef(null);
 useEffect(()=>{
  if(!status?.last_success||observed.current===status.last_success)return;
  let alive=true;
  async function refresh(){try{const response=await scopedFetch('/api/executions/');if(!response.ok)throw Error('Could not refresh synced trades.');const result=await response.json();if(!alive)return;await callbacks.current.onUpdated(result);observed.current=status.last_success;await refreshAccounts();if(status.imported)callbacks.current.notify(`Broker synced · ${status.imported} new executions.`)}catch(e){if(alive)callbacks.current.notify(e.message)}}
  refresh();return()=>{alive=false};
 },[status?.last_success]);
 return null;
}

function SchwabConnection({request}){
 const {scopedFetch,accountId}=useAccount();const [status,setStatus]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);const [syncState,setSyncState]=useState(null);
 useEffect(()=>{let alive=true;async function poll(){try{const r=await scopedFetch('/api/schwab/connection/');if(!r.ok)throw Error('Could not load Schwab connection.');const s=await r.json();if(alive)setStatus(s);const sr=await scopedFetch('/api/schwab/sync/');if(sr.ok){const ss=await sr.json();if(alive)setSyncState(ss)}}catch(e){if(alive)setError(e.message)}}poll();const timer=setInterval(poll,3000);return()=>{alive=false;clearInterval(timer)}},[accountId]);
 async function sync(){setBusy(true);setError('');try{setSyncState(await request('/api/schwab/sync/','POST',{}))}catch(e){setError(e.message)}finally{setBusy(false)}}
 async function connect(){setBusy(true);setError('');try{setStatus(await request('/api/schwab/connection/','POST',{}))}catch(e){setError(e.message)}finally{setBusy(false)}}
 return <div className="broker-sync"><div className="panel-heading"><h3>Charles Schwab</h3><button className="primary" disabled={busy||!status?.configured||status?.status==='connecting'} onClick={connect}>{status?.status==='connecting'?'Connecting…':status?.status==='connected'?'Reconnect Schwab':'Connect Schwab'}</button>{status?.status==='connected'&&<button className="primary" disabled={busy||['running','queued'].includes(syncState?.status)} onClick={sync}>Sync now</button>}</div><dl className="sync-details"><div><dt>Schedule</dt><dd>On startup · Weekdays, 1:15 p.m. Pacific</dd></div><div><dt>Last successful sync</dt><dd>{syncState?.last_success?new Date(syncState.last_success).toLocaleString():'—'}</dd></div></dl>{syncState?.message&&<p role="status">{syncState.message}{syncState.status==='success'?` ${syncState.imported||0} imported · ${syncState.duplicates||0} duplicates skipped.`:''}</p>}{error&&<p className="alert error" role="alert">{error}</p>}{status?.status!=='connected'&&status?.message&&<p role="status">{status.message}</p>}</div>
}

export default function BrokerSync({request}){
 const {accounts,accountId}=useAccount();
 return accounts.find(a=>String(a.id)===String(accountId))?.broker==='schwab'?<SchwabConnection request={request}/>:<IbkrSync request={request}/>;
}
function IbkrSync({request}){
 const {status,error}=useSyncStatus();const [sending,setSending]=useState(false),[actionError,setActionError]=useState('');
 const running=sending||['running','queued'].includes(status?.status);
 async function sync(){setSending(true);setActionError('');try{await request('/api/broker-sync/','POST',{});}catch(e){setActionError(e.message)}finally{setSending(false)}}
 return <div className="broker-sync"><div className="panel-heading"><h3>IBKR Flex sync</h3><button className="primary" disabled={!status?.configured||!status?.available||running} onClick={sync}>{running?'Syncing…':'Sync now'}</button></div>
 <dl className="sync-details"><div><dt>Schedule</dt><dd>On startup · Weekdays, 1:15 p.m. Pacific</dd></div><div><dt>Last successful sync</dt><dd>{status?.last_success?new Date(status.last_success).toLocaleString():'—'}</dd></div></dl>
 {(error||actionError)&&<p role="alert" className="alert error">{actionError||error}</p>}
 {status&&!status.configured&&<p role="status">Add your IBKR Flex credentials to backend/.env.</p>}
 {status?.configured&&!status.available&&<p role="status">Select the IBKR account linked to your Flex query.</p>}
 {status?.available&&status.message&&<p role={status.status==='error'?'alert':'status'} className={status.status==='error'?'alert error':'subtle'}>{status.message}{status.status==='success'?` ${status.imported} imported · ${status.duplicates} duplicates skipped.`:''}</p>}
 {status?.available&&status.conflicts?.length>0&&<details><summary>Executions needing review ({status.conflicts.length})</summary><ul>{status.conflicts.map((c,i)=><li key={i}>{c.symbol} · {c.date} · {c.fields.join(', ')}</li>)}</ul></details>}
 </div>;
}
