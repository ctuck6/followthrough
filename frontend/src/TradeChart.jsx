import {useAccount} from './AccountScope.jsx';
import React,{useEffect,useRef,useState} from 'react';
import {createChart,CandlestickSeries,createSeriesMarkers,ColorType} from 'lightweight-charts';
import Select from './components/Select.jsx';
import ChartDrawings from './ChartDrawings.jsx';
import {executionMarkers} from './chartMarkers.js';

export function CandleChart({data,storageKey}) {
 const host=useRef(null),[api,setApi]=useState(null);
 const container=useRef(null),controls=useRef(null),pinned=useRef(false),[hover,setHover]=useState(''),[isPinned,setIsPinned]=useState(false);
 const markers=executionMarkers(data.candles,data.markers);
 useEffect(()=>{
  const format=time=>new Intl.DateTimeFormat('en-US',{timeZone:data.timezone,hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(new Date(Number(time)*1000));
  const chart=createChart(host.current,{autoSize:false,width:Math.max(1,container.current.clientWidth),height:Math.max(1,container.current.clientHeight),layout:{attributionLogo:true},timeScale:{timeVisible:true,secondsVisible:false},localization:{timeFormatter:format},handleScroll:{mouseWheel:true,pressedMouseMove:true,horzTouchDrag:true,vertTouchDrag:false},handleScale:{mouseWheel:true,pinch:true,axisPressedMouseMove:true},grid:{vertLines:{visible:false}}});
  const series=chart.addSeries(CandlestickSeries,{upColor:'#46956a',downColor:'#cc6969',borderVisible:false,wickUpColor:'#46956a',wickDownColor:'#cc6969'});
  series.setData(data.candles);
  const markerSeries=createSeriesMarkers(series,executionMarkers(data.candles,data.markers));
  const theme=()=>{const dark=document.documentElement.dataset.theme==='dark';const palette=getComputedStyle(document.documentElement);const up=palette.getPropertyValue('--report-teal').trim(),down=palette.getPropertyValue('--report-coral').trim();series.applyOptions({upColor:up,downColor:down,wickUpColor:up,wickDownColor:down});markerSeries.setMarkers(executionMarkers(data.candles,data.markers).map(marker=>({...marker,color:marker.shape==='arrowUp'?up:down})));const styles=getComputedStyle(container.current);chart.applyOptions({layout:{background:{type:ColorType.Solid,color:palette.getPropertyValue('--sidebar').trim()},textColor:'#e3ecdf'},grid:{horzLines:{color:'#2d4035'}},rightPriceScale:{borderColor:'#2d4035'},timeScale:{borderColor:'#2d4035',tickMarkFormatter:time=>format(time).replace(/:\d{2} /,' ')}})};
  theme();const observer=new MutationObserver(theme);observer.observe(document.documentElement,{attributes:true,attributeFilter:['data-theme','data-palette','style']});
  const details=event=>{
   const candle=event.seriesData.get(series);
   if(!candle||!event.time)return '';
   const fills=data.markers.filter(fill=>Math.floor(fill.time/60)*60===event.time);
   const price=value=>Number(value).toLocaleString('en-US',{maximumFractionDigits:6});
   return `${format(event.time)} · O ${price(candle.open)}  H ${price(candle.high)}  L ${price(candle.low)}  C ${price(candle.close)}`+(fills.length?' | '+fills.map(fill=>`${fill.kind} · ${fill.side==='BUY'?'Buy':'Sell'} ${Number(fill.quantity)} @ ${Number(fill.price)} · ${format(fill.time)}`).join(' | '):'');
  };
  chart.subscribeCrosshairMove(event=>{if(!pinned.current)setHover(details(event))});
  chart.subscribeClick(event=>{const text=details(event);if(text){pinned.current=true;setIsPinned(true);setHover(text)}});
  const first=data.markers[0]?.time,last=data.markers.at(-1)?.time;
  const reset=()=>{chart.priceScale('right').applyOptions({autoScale:true,scaleMargins:{top:.12,bottom:.12}});if(first&&last)chart.timeScale().setVisibleRange({from:Math.floor(first/60)*60-1800,to:Math.floor(last/60)*60+1800});else chart.timeScale().fitContent();};reset();
  controls.current={chart,reset};setApi({chart,series});
  const resize=new ResizeObserver(()=>{const box=container.current;if(box.clientWidth&&box.clientHeight)chart.resize(box.clientWidth,box.clientHeight)});resize.observe(container.current);
  return()=>{controls.current=null;resize.disconnect();observer.disconnect();chart.remove()};
 },[data]);
 function zoom(factor){const scale=controls.current?.chart.timeScale(),range=scale?.getVisibleLogicalRange();if(range){const middle=(range.from+range.to)/2,half=Math.max(3,(range.to-range.from)*factor/2);scale.setVisibleLogicalRange({from:middle-half,to:middle+half})}}
 return <div className="candle-workspace"><div className="chart-controls" role="toolbar" aria-label="Chart controls"><button aria-label="Zoom out" onClick={()=>zoom(1.35)}>−</button><button aria-label="Zoom in" onClick={()=>zoom(.75)}>+</button><button onClick={()=>controls.current?.reset()}>Focus trade</button><button onClick={()=>{controls.current?.chart.priceScale('right').applyOptions({autoScale:true});controls.current?.chart.timeScale().fitContent()}}>Fit session</button>{isPinned&&<button onClick={()=>{pinned.current=false;setIsPinned(false);setHover('')}}>Unpin candle</button>}</div><ChartDrawings api={api} storageKey={storageKey}/><div ref={container} className="trade-candle-chart" aria-label={`${data.symbol} one-minute candlestick chart`} role="img"><div className="chart-render-host" ref={host}/></div><div className="chart-execution-tooltip" aria-live="polite">{hover||'\u00a0'}</div>{markers.length<data.markers.length&&<p className="chart-status" role="status">{data.markers.length-markers.length} execution marker(s) could not be placed because their minute candles are unavailable.</p>}</div>;
}

export default function TradeChart({trade}){
 const {scopedFetch}=useAccount();
 const [date,setDate]=useState(''),[data,setData]=useState(null),[error,setError]=useState(''),[loading,setLoading]=useState(true),[retry,setRetry]=useState(0);
 useEffect(()=>{
  const controller=new AbortController();setLoading(true);setError('');
  scopedFetch(`/api/trades/${encodeURIComponent(trade.trade_id)}/chart/${date?`?date=${date}`:''}`,{signal:controller.signal}).then(async response=>{const result=await response.json();if(!response.ok)throw Error(result.error||'Could not load chart.');return result}).then(result=>{setData(result);setLoading(false)}).catch(error=>{if(error.name!=='AbortError'){setError(error.message);setLoading(false)}});
  return()=>controller.abort();
 },[trade.trade_id,date,retry]);
 return <section className="trade-charts"><div className="chart-heading"><h3>{trade.asset_class==='OPT'?`${trade.symbol} · Underlying`:`${trade.symbol} · Chart`}</h3><span className="chart-interval">1 minute</span>{data?.dates.length>1&&<Select aria-label="Chart session" value={date||data.date} onChange={event=>setDate(event.target.value)}>{data.dates.map(day=><option key={day} value={day}>{day}</option>)}</Select>}</div>{loading?<p className="chart-status" role="status">Loading chart…</p>:error||data?.error?<div className="chart-status" role="status"><p>{error||data.error}</p><button onClick={()=>setRetry(value=>value+1)}>Retry</button></div>:data&&<CandleChart key={data.date} data={data} storageKey={`followthrough-drawings:${trade.trade_id}:${data.date}`}/>}
 <div className="chart-credit"><a href="https://www.tradingview.com/" target="_blank" rel="noreferrer">TradingView Lightweight Charts™</a><span>Data: Twelve Data{data?.timezone?` · ${data.timezone}`:''}</span></div>
 {trade.asset_class==='OPT'&&<details className="option-chart-unavailable"><summary>{trade.symbol} · {trade.expiry} · {Number(trade.strike)} {trade.put_call==='C'?'Call':'Put'}</summary><p role="status">{data?.option_error||'Historical option-contract candles are not available from the configured data source.'}</p></details>}
 </section>;
}
