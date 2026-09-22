import React,{useEffect,useRef,useState} from 'react';
import {createPortal} from 'react-dom';

function ToolIcon({name}){
 const paths={Cursor:'M12 3v18M3 12h18',Level:'M3 12h18',Trendline:'M4 20 20 4M3 17v4h4M17 3h4v4',Rectangle:'M4 5h16v14H4Z',Undo:'M9 5 4 10l5 5M4 10h9a6 6 0 0 1 6 6',Redo:'m15 5 5 5-5 5m5-5h-9a6 6 0 0 0-6 6',Clear:'M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7'};
 return <svg viewBox="0 0 24 24" aria-hidden="true"><path d={paths[name]}/></svg>;
}

export default function ChartDrawings({api,storageKey}){
 const [tool,setTool]=useState('Cursor'),[drawings,setDrawings]=useState(()=>{try{const stored=JSON.parse(localStorage.getItem(storageKey)||'[]');return Array.isArray(stored)?stored.filter(d=>['Level','Trendline','Rectangle'].includes(d.type)&&[d.a,d.b].every(p=>p&&Number.isFinite(p.time)&&Number.isFinite(p.price))).slice(0,200):[]}catch{return []}}),[redo,setRedo]=useState([]),[preview,setPreview]=useState(null),[projection,setProjection]=useState([]),[error,setError]=useState('');
 const anchor=useRef(null);
 useEffect(()=>{if(!storageKey)return;try{localStorage.setItem(storageKey,JSON.stringify(drawings));setError('')}catch{setError('Drawings could not be saved in this browser.')}},[drawings,storageKey]);
 useEffect(()=>{
  if(!api)return;
  const {chart,series}=api;
  chart.applyOptions({handleScroll:{pressedMouseMove:tool==='Cursor',horzTouchDrag:tool==='Cursor'}});
  anchor.current=null;setPreview(null);
  const point=event=>{if(!event.point||event.time==null||typeof event.time!=='number')return null;const price=series.coordinateToPrice(event.point.y);return price===null?null:{time:event.time,price}};
  const click=event=>{if(tool==='Cursor')return;const p=point(event);if(!p)return;
   if(tool==='Level'||anchor.current){const drawing={type:tool,a:anchor.current||p,b:p};setDrawings(current=>[...current,drawing].slice(-200));setRedo([]);anchor.current=null;setPreview(null);setTool('Cursor')}
   else{anchor.current=p;setPreview({type:tool,a:p,b:p})}
  };
  const move=event=>{if(!anchor.current)return;const p=point(event);if(p)setPreview({type:tool,a:anchor.current,b:p})};
  const cancel=event=>{if(event.key==='Escape'&&tool!=='Cursor'){event.preventDefault();event.stopPropagation();anchor.current=null;setPreview(null);setTool('Cursor')}};
  chart.subscribeClick(click);chart.subscribeCrosshairMove(move);document.addEventListener('keydown',cancel,true);
  return()=>{chart.unsubscribeClick(click);chart.unsubscribeCrosshairMove(move);document.removeEventListener('keydown',cancel,true)};
 },[api,tool]);
 useEffect(()=>{
  if(!api||(!drawings.length&&!preview)){setProjection([]);return;}let frame;
  const paint=()=>{const {chart,series}=api;const values=[...drawings,...(preview?[preview]:[])].map(d=>({...d,x1:chart.timeScale().timeToCoordinate(d.a.time),x2:chart.timeScale().timeToCoordinate(d.b.time),y1:series.priceToCoordinate(d.a.price),y2:series.priceToCoordinate(d.b.price)}));setProjection(previous=>JSON.stringify(previous)===JSON.stringify(values)?previous:values);frame=requestAnimationFrame(paint)};
  frame=requestAnimationFrame(paint);return()=>cancelAnimationFrame(frame);
 },[api,drawings,preview]);
 const element=api?.chart.chartElement();
 return <><div className="drawing-tools" role="toolbar" aria-label="Drawing tools">{['Cursor','Level','Trendline','Rectangle'].map(name=><button key={name} aria-label={name} aria-pressed={tool===name} disabled={!api} onClick={()=>setTool(name)} title={name==='Level'?'Click a price level':name==='Cursor'?'Pan and inspect candles':'Click a start point, then an end point'}><ToolIcon name={name}/></button>)}<button aria-label="Undo" title="Undo" disabled={!drawings.length} onClick={()=>{setRedo(r=>[...r,drawings.at(-1)]);setDrawings(d=>d.slice(0,-1))}}><ToolIcon name="Undo"/></button><button aria-label="Redo" title="Redo" disabled={!redo.length} onClick={()=>{setDrawings(d=>[...d,redo.at(-1)]);setRedo(r=>r.slice(0,-1))}}><ToolIcon name="Redo"/></button><button aria-label="Clear" title="Clear" disabled={!drawings.length} onClick={()=>{setRedo([...drawings].reverse());setDrawings([])}}><ToolIcon name="Clear"/></button></div>{error&&<span role="alert">{error}</span>}{element&&createPortal(<svg className="chart-drawing-overlay" aria-hidden="true" width={api.chart.paneSize().width} height={api.chart.paneSize().height}>{projection.map((d,index)=>{if(d.y1===null||d.y2===null)return null;const common={stroke:'#dbd390',strokeWidth:2};if(d.type==='Level')return <line key={index} x1="0" x2="100%" y1={d.y1} y2={d.y1} {...common}/>;if(d.x1===null||d.x2===null)return null;return d.type==='Rectangle'?<rect key={index} x={Math.min(d.x1,d.x2)} y={Math.min(d.y1,d.y2)} width={Math.abs(d.x2-d.x1)} height={Math.abs(d.y2-d.y1)} fill="rgba(219,211,144,.12)" {...common}/>:<line key={index} x1={d.x1} x2={d.x2} y1={d.y1} y2={d.y2} {...common}/>})}</svg>,element)}</>;
}
