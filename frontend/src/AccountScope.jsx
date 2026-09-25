import React, {createContext, useContext, useEffect, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import Select from './components/Select.jsx';

export function HeaderControls({children}) {
  const [host,setHost]=useState(null);
  useEffect(()=>{setHost(document.getElementById('page-controls'))},[]);
  return host?createPortal(children,host):null;
}
const Context = createContext(null);
export const useAccount = () => useContext(Context);
export function useAccountViewState(key, initial) {
  const {viewState,setViewState}=useAccount();
  const value=viewState[key]??initial;
  return [value,next=>setViewState(old=>({...old,[key]:typeof next==='function'?next(old[key]??initial):next}))];
}
export function AccountSwitcher() {
  const {accounts, accountId, switchAccount, switching, hasUnassigned} = useAccount();
  return <Select wrapperClassName="account-switcher" aria-label="Brokerage account" value={accountId} disabled={switching || !accounts.length} onChange={e=>switchAccount(e.target.value)}>
    {(hasUnassigned || !accounts.length || accountId==='unassigned') && <option value="unassigned">{accounts.length?'Unassigned':'No accounts'}</option>}
    {accounts.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}
  </Select>;
}
export default function AccountScope({children}) {
  const [accounts,setAccounts]=useState([]),[hasUnassigned,setHasUnassigned]=useState(false),[accountId,setAccountId]=useState(null),[error,setError]=useState(''),[switching,setSwitching]=useState(false);
  const [viewState,setViewState]=useState({});
  const beforeSwitch=useRef(null),inFlight=useRef(false);
  async function refreshAccounts() {
    const response=await fetch('/api/accounts/');
    if(!response.ok)throw Error('Could not load brokerage accounts.');
    const data=await response.json();
    setAccounts(data.accounts);setHasUnassigned(data.has_unassigned);
    setAccountId(previous=>{
      if(previous!==null&&(data.accounts.some(a=>String(a.id)===previous)||(previous==='unassigned'&&data.has_unassigned)))return previous;
      let saved;try{saved=localStorage.getItem('followthrough-account')}catch{}
      return data.accounts.some(a=>String(a.id)===saved)?saved:data.has_unassigned?'unassigned':String(data.accounts[0]?.id||'unassigned');
    });
    setError('');
  }
  useEffect(()=>{refreshAccounts().catch(e=>setError(e.message))},[]);
  async function switchAccount(next) {
    if(next===accountId||inFlight.current)return;
    inFlight.current=true;setSwitching(true);
    try {
      if(beforeSwitch.current&&!await beforeSwitch.current())return;
      setAccountId(next);try{localStorage.setItem('followthrough-account',next)}catch{}
    } finally {inFlight.current=false;setSwitching(false)}
  }
  const scopedUrl=url=>`${url}${url.includes('?')?'&':'?'}account_id=${encodeURIComponent(accountId)}`;
  const scopedFetch=(url,options)=>fetch(scopedUrl(url),options);
  if(accountId===null)return <main className="loading"><h1>Followthrough</h1><p role="status">{error||'Opening your accounts…'}</p>{error&&<button onClick={()=>refreshAccounts().catch(e=>setError(e.message))}>Try again</button>}</main>;
  return <Context.Provider value={{viewState,setViewState,accounts,hasUnassigned,accountId,switchAccount,switching,beforeSwitch,refreshAccounts,scopedUrl,scopedFetch}}>{children}</Context.Provider>;
}
