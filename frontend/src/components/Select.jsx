import React,{useEffect,useId,useRef,useState} from 'react';
import Popover from './Popover.jsx';
import './Select.css';
export default function Select({children,className='',wrapperClassName='',popover:unused,...props}){
 const [open,setOpen]=useState(false),[label,setLabel]=useState('');const anchor=useRef(null),listId=useId(),search=useRef(''),timer=useRef(null);
 const options=React.Children.toArray(children).filter(React.isValidElement).map(o=>({value:String(o.props.value??o.props.children),text:o.props.children,disabled:o.props.disabled}));
 const selected=options.find(o=>o.value===String(props.value));
 useEffect(()=>{const parent=anchor.current?.closest('label');if(parent){const clone=parent.cloneNode(true);clone.querySelectorAll('.select-control').forEach(n=>n.remove());setLabel(clone.textContent.trim())}},[]);
 useEffect(()=>()=>clearTimeout(timer.current),[]);
 function choose(option){if(option.disabled)return;props.onChange?.({target:{value:option.value,name:props.name}});setOpen(false);anchor.current?.focus()}
 function keyboard(e){const buttons=Array.from(e.currentTarget.parentElement.querySelectorAll('[role="option"]:not(:disabled)'));let index=buttons.indexOf(e.currentTarget);
 if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){e.preventDefault();index=e.key==='Home'?0:e.key==='End'?buttons.length-1:(index+(e.key==='ArrowDown'?1:-1)+buttons.length)%buttons.length;buttons[index]?.focus()}
 else if(e.key.length===1&&e.key!==' '){search.current+=e.key.toLowerCase();clearTimeout(timer.current);timer.current=setTimeout(()=>{search.current=''},600);buttons.find(b=>b.textContent.toLowerCase().startsWith(search.current))?.focus()}}
 return <span className={`select-control ${wrapperClassName}`}>
 <button ref={anchor} id={props.id} name={props.name} type="button" role="combobox" className={`select-input select-trigger ${className}`} aria-label={props['aria-label']||label||undefined} aria-labelledby={props['aria-labelledby']} aria-haspopup="listbox" aria-controls={open?listId:undefined} aria-expanded={open} disabled={props.disabled} onBlur={props.onBlur} onClick={()=>setOpen(!open)} onKeyDown={e=>{if(['ArrowDown','ArrowUp'].includes(e.key)){e.preventDefault();setOpen(true)}}}>{selected?.text||'Select'}</button>
 <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 10 5 5 5-5"/></svg>
 {open&&<Popover anchor={anchor} label={props['aria-label']||label||'Choose an option'} className="options-popover" onClose={()=>setOpen(false)}><div role="listbox" id={listId} aria-label={props['aria-label']||label||'Options'}>{options.map(o=><button type="button" role="option" aria-selected={o.value===String(props.value)} aria-pressed={o.value===String(props.value)} key={o.value} disabled={o.disabled} onKeyDown={keyboard} onClick={()=>choose(o)}>{o.text}<span aria-hidden="true">{o.value===String(props.value)?'✓':''}</span></button>)}</div></Popover>}
 </span>
}
