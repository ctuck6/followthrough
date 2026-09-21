import React, {useEffect, useId, useRef} from 'react';

let locks=0, savedStyles;
function lockScroll(){
 if(locks++===0){const body=document.body;savedStyles={overflow:body.style.overflow,paddingRight:body.style.paddingRight,htmlOverflow:document.documentElement.style.overflow};const gap=window.innerWidth-document.documentElement.clientWidth;body.style.overflow='hidden';document.documentElement.style.overflow='hidden';if(gap)body.style.paddingRight=`${parseFloat(getComputedStyle(body).paddingRight)+gap}px`;}
 return()=>{if(--locks===0){document.body.style.overflow=savedStyles.overflow;document.body.style.paddingRight=savedStyles.paddingRight;document.documentElement.style.overflow=savedStyles.htmlOverflow}};
}

export default function Modal({title, children, onClose, busy=false, className='',hideTitle=false}) {
  const ref=useRef(null), heading=useId();
  useEffect(()=>{const dialog=ref.current;const previous=document.activeElement;const unlock=lockScroll();dialog.showModal();return()=>{dialog.close();unlock();previous?.focus()}},[]);
  return <dialog ref={ref} className={`app-modal ${className}`} aria-labelledby={heading} onCancel={e=>{e.preventDefault();if(!busy)onClose()}} onClick={e=>{if(e.target===ref.current&&!busy){const box=ref.current.getBoundingClientRect();if(e.clientX<box.left||e.clientX>box.right||e.clientY<box.top||e.clientY>box.bottom)onClose()}}}>
    <header className={`modal-heading ${hideTitle?'compact-modal-heading':''}`}><h2 id={heading} className={hideTitle?'sr-only':undefined}>{title}</h2><button type="button" onClick={onClose} disabled={busy} aria-label="Close dialog" className="modal-close"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg></button></header>{children}
  </dialog>;
}
