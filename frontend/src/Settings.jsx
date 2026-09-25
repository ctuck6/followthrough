import Accounts from './Accounts.jsx';
import React,{useEffect,useState} from 'react';
import {useAccountViewState} from './AccountScope.jsx';
export default function Settings({request,notify,onAccountDataAction}){
 const [tab,setTab]=useAccountViewState('settings-tab','Profile');
 const [profile,setProfile]=useState({display_name:'',bio:''}),[loaded,setLoaded]=useState(false),[saving,setSaving]=useState(false),[error,setError]=useState('');
 useEffect(()=>{const controller=new AbortController();fetch('/api/profile/',{signal:controller.signal}).then(async r=>{if(!r.ok)throw Error('Could not load your profile.');return r.json()}).then(p=>{setProfile(p);setLoaded(true)}).catch(e=>{if(e.name!=='AbortError')setError(e.message)});return()=>controller.abort()},[]);
 async function save(e){e.preventDefault();setSaving(true);setError('');try{setProfile(await request('/api/profile/','PUT',profile));notify('Profile saved.')}catch(e){setError(e.message)}finally{setSaving(false)}}
 return <div className={`settings-view ${tab==='Accounts'?'accounts-settings':''}`}><div className="trade-detail-tabs" role="tablist" aria-label="Settings">{['Profile','Accounts'].map(name=><button key={name} role="tab" aria-selected={tab===name} onClick={()=>setTab(name)}>{name}</button>)}</div>{tab==='Accounts'?<Accounts request={request} notify={notify} onAccountDataAction={onAccountDataAction}/>:<><section className="panel"><div className="panel-heading"><h2>Profile</h2><span className="profile-avatar" aria-hidden="true">{profile.display_name.trim().slice(0,1).toUpperCase()||'✓'}</span></div><form onSubmit={save} className="profile-form"><label>Display name<input maxLength="100" autoComplete="name" value={profile.display_name} disabled={!loaded||saving} onChange={e=>setProfile({...profile,display_name:e.target.value})}/></label><label>About you<textarea rows="4" maxLength="1000" value={profile.bio} disabled={!loaded||saving} onChange={e=>setProfile({...profile,bio:e.target.value})}/></label>{error&&<p className="alert error" role="alert">{error}</p>}<button className="primary" disabled={!loaded||saving}>{saving?'Saving…':'Save profile'}</button></form></section></>}
 </div>
}
