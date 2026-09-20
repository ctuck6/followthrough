// CSV fields stay text; nothing from an uploaded file is evaluated.
export function parseTradeCsv(text, date) {
  const rows=[];let row=[],field='',quoted=false,closed=false;
  text=text.replace(/^\uFEFF/,'');
  for(let i=0;i<text.length;i++){
    const ch=text[i];
    if(quoted){if(ch==='"'){if(text[i+1]==='"'){field+='"';i++}else{quoted=false;closed=true}}else field+=ch;continue}
    if(ch==='"'&&!field&&!closed){quoted=true;continue}
    if(ch===','||ch==='\n'||ch==='\r'){
      row.push(field);field='';closed=false;
      if(ch!==','){if(row.some(value=>value.trim()))rows.push(row);row=[];if(ch==='\r'&&text[i+1]==='\n')i++}
    }else{if(closed&&!/\s/.test(ch))throw Error('Unexpected text after a quoted CSV field.');if(!closed)field+=ch}
  }
  if(quoted)throw Error('A quoted CSV field is missing its closing quote.');
  row.push(field);if(row.some(value=>value.trim()))rows.push(row);
  if(rows.length<2)throw Error('Include column headers and at least one trade.');
  const headers=rows.shift().map(h=>h.trim().toLowerCase().replace(/[\s_-]+/g,''));
  const column=names=>headers.findIndex(h=>names.includes(h));
  const symbol=column(['symbol','ticker']),side=column(['side','direction']),pnl=column(['pnl','netpnl','netp&l','p&l']),notes=column(['notes','tradenotes']),day=column(['date','tradedate']);
  if([symbol,side,pnl].includes(-1))throw Error('Required columns: symbol (or ticker), side (Long/Short), and pnl (or net pnl).');
  if(new Set(headers).size!==headers.length)throw Error('CSV column names must be unique.');
  if(rows.length>500)throw Error('Import at most 500 trades per day.');
  return rows.map((cells,index)=>{
    const fail=message=>{throw Error(`Row ${index+2}: ${message}`)};
    if(cells.length!==headers.length)fail('Column count does not match the header.');
    const ticker=cells[symbol].trim().toUpperCase(),direction=cells[side].trim().toLowerCase(),amount=cells[pnl].trim();
    if(!ticker||ticker.length>30)fail('Ticker must contain 1–30 characters.');
    if(!['long','short'].includes(direction))fail('Side must be Long or Short.');
    if(!/^[+-]?\d+(\.\d{1,2})?$/.test(amount)||Math.abs(Number(amount))>999999999)fail('P&L must be a number with up to two decimals, without currency symbols or thousands separators.');
    if(day!==-1&&cells[day].trim()!==date)fail(`Date must match the open journal (${date}), in YYYY-MM-DD format.`);
    const note=notes===-1?'':cells[notes].trim();if(note.length>2000)fail('Notes must be at most 2,000 characters.');
    return {symbol:ticker,side:direction==='long'?'Long':'Short',pnl:Number(amount).toFixed(2),notes:note};
  });
}
