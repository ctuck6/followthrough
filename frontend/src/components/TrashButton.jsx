import React from 'react';
export default function TrashButton({label,onClick,disabled=false}){return <button type="button" className="attachment-trash" aria-label={label} title={label} onClick={onClick} disabled={disabled}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/></svg></button>}
