import React, {useLayoutEffect, useRef, useContext, createContext, useId} from 'react';
import {createPortal} from 'react-dom';

const PopoverParents=createContext([]);

/** Non-modal anchored panel. Native top layer avoids clipped parent containers. */
export default function Popover({anchor, label, children, onClose, className=''}) {
  const ref=useRef(null),id=useId(),parents=useContext(PopoverParents);
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
    const outside=e=>{const nested=e.target.closest?.('[data-popover-parents]')?.dataset.popoverParents?.split(' ').includes(id);if(!nested&&!panel.contains(e.target)&&!trigger.contains(e.target))onClose()};
    const escape=e=>{if(e.key==='Escape'&&Array.from(document.querySelectorAll('.anchored-popover:popover-open')).at(-1)===panel){e.preventDefault();onClose();trigger.focus()}};
    document.addEventListener('pointerdown',outside);document.addEventListener('keydown',escape);document.addEventListener('focusin',outside);
    window.addEventListener('resize',position);window.addEventListener('scroll',position,true);
    return()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',escape);document.removeEventListener('focusin',outside);window.removeEventListener('resize',position);window.removeEventListener('scroll',position,true);panel.hidePopover()};
  },[]);
  return createPortal(<PopoverParents.Provider value={[...parents,id]}><div data-popover-parents={parents.join(' ')} ref={ref} popover="manual" role="dialog" aria-label={label} className={`anchored-popover ${className}`}>{children}</div></PopoverParents.Provider>,document.body);
}
