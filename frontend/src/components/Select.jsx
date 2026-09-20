import React, {useRef,useState} from 'react';
import Popover from './Popover.jsx';
import './Select.css';

/** Shared native dropdown: retains keyboard support, labels and form behavior. */
export default function Select({children, className = '', wrapperClassName = '', popover=false, ...props}) {
  const [open,setOpen]=useState(false),anchor=useRef(null);
  const options=React.Children.toArray(children);
  if(popover)return <span className={`select-control ${wrapperClassName}`}><button ref={anchor} type="button" className={`select-input select-trigger ${className}`} aria-label={props['aria-label']} aria-haspopup="dialog" aria-expanded={open} disabled={props.disabled} onClick={()=>setOpen(!open)}>{options.find(option=>String(option.props.value)===String(props.value))?.props.children}</button><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 10 5 5 5-5"/></svg>{open&&<Popover anchor={anchor} label={props['aria-label']||'Choose an option'} className="options-popover" onClose={()=>setOpen(false)}>{options.map((option,i)=><button type="button" key={option.key} aria-pressed={String(option.props.value)===String(props.value)} onKeyDown={e=>{if(['ArrowDown','ArrowUp'].includes(e.key)){e.preventDefault();const nodes=e.currentTarget.parentElement.querySelectorAll('button');nodes[(i+(e.key==='ArrowDown'?1:-1)+nodes.length)%nodes.length].focus()}}} onClick={()=>{props.onChange({target:{value:option.props.value}});setOpen(false);anchor.current.focus()}}>{option.props.children}</button>)}</Popover>}</span>;
  return <span className={`select-control ${wrapperClassName}`}>
    <select {...props} className={`select-input ${className}`}>{children}</select>
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="m7 10 5 5 5-5"/></svg>
  </span>;
}
