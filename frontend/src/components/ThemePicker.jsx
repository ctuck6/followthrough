import React from 'react';
import Select from './Select.jsx';
import {palettes} from '../themes.js';
export default function ThemePicker({palette,onPalette,mode,onMode}) {
 return <div className="theme-picker"><Select aria-label="Color theme" value={palette} onChange={e=>onPalette(e.target.value)} renderOption={option=>{
 const colors=palettes[option.value][mode];
 return <span className="theme-choice"><span>{option.text}</span><svg className="theme-preview" viewBox="0 0 100 60" aria-hidden="true"><rect width="100" height="60" rx="6" fill={colors[0]}/><path d="M6 0H28V60H6Q0 60 0 54V6Q0 0 6 0" fill={colors[8]}/><rect x="5" y="8" width="8" height="8" rx="3" fill="#c2ef85"/><rect x="5" y="23" width="18" height="5" rx="2" fill={colors[9]}/><path d="M6 35h14M6 43h14" stroke={colors[9]} strokeWidth="2"/><rect x="34" y="9" width="48" height="4" rx="2" fill={colors[2]}/><rect x="34" y="20" width="59" height="17" rx="4" fill={colors[7]}/><rect x="34" y="42" width="27" height="12" rx="3" fill={colors[1]}/><rect x="66" y="42" width="27" height="12" rx="3" fill={colors[1]}/><path d="M39 48h15" stroke={mode==='dark'?'#36e589':'#087c42'} strokeWidth="3"/><path d="M71 48h15" stroke={mode==='dark'?'#ff526b':'#c9233e'} strokeWidth="3"/></svg></span>
 }}>{Object.keys(palettes).map(name=><option key={name} value={name}>{name}</option>)}</Select><div className="theme-mode" role="group" aria-label="Appearance">{['light','dark'].map(value=><button key={value} type="button" aria-pressed={mode===value} onClick={()=>onMode(value)}>{value==='light'?'☀ Light':'☾ Dark'}</button>)}</div></div>
}
