import React, {useLayoutEffect, useRef} from 'react';
import {createPortal} from 'react-dom';

/** Non-modal anchored panel. Native top layer avoids clipped parent containers. */
export default function Popover({anchor, label, children, onClose, className=''}) {
  const ref=useRef(null);
  useLayoutEffect(()=>{
    const panel=ref.current,trigger=anchor.current;
    panel.showPopover();
    function position(){
      const box=trigger.getBoundingClientRect();
      panel.style.left=`${Math.max(8,Math.min(box.left,window.innerWidth-panel.offsetWidth-8))}px`;
      panel.style.top=`${Math.min(box.bottom+8,Math.max(8,window.innerHeight-120))}px`;
      panel.style.maxHeight=`${Math.max(100,window.innerHeight-parseFloat(panel.style.top)-8)}px`;
    }
    position();panel.querySelector('[aria-pressed="true"],button:not(:disabled),select,input')?.focus();
    const outside=e=>{if(!panel.contains(e.target)&&!trigger.contains(e.target))onClose()};
    const escape=e=>{if(e.key==='Escape'){e.preventDefault();onClose();trigger.focus()}};
    document.addEventListener('pointerdown',outside);document.addEventListener('keydown',escape);document.addEventListener('focusin',outside);
    window.addEventListener('resize',position);window.addEventListener('scroll',position,true);
    return()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',escape);document.removeEventListener('focusin',outside);window.removeEventListener('resize',position);window.removeEventListener('scroll',position,true);panel.hidePopover()};
  },[]);
  return createPortal(<div ref={ref} popover="manual" role="dialog" aria-label={label} className={`anchored-popover ${className}`}>{children}</div>,document.body);
}
