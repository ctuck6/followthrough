export const dateKey = date => `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;
export const letterGrade = score => score === null ? '—' : score >= 90 ? 'A' : score >= 80 ? 'B' : score >= 70 ? 'C' : score >= 60 ? 'D' : 'F';
export function monthCells(month) {
  const [year, index] = month.split('-').map(Number);
  const first = new Date(year, index-1, 1);
  const count = new Date(year, index, 0).getDate();
  return Array.from({length:Math.ceil((first.getDay()+count)/7)*7}, (_, i) => {
    const day = i-first.getDay()+1;
    return day < 1 || day > count ? null : dateKey(new Date(year,index-1,day));
  });
}
export function averageGrade(days, start, end) {
  const graded = days.filter(day => day.date >= start && day.date <= end && typeof day.score === 'number' && Number.isFinite(day.score));
  const score = graded.length ? Math.round(graded.reduce((sum,day)=>sum+day.score,0)/graded.length) : null;
  return {score, letter:letterGrade(score), count:graded.length};
}
export function timeframeRange(period, month, today) {
  const [year,index]=month.split('-').map(Number);
  if(period==='month')return [`${month}-01`,dateKey(new Date(year,index,0))];
  const end=new Date(`${today}T12:00:00`);
  const start=new Date(end);
  start.setDate(start.getDate()-(period==='7'?6:29));
  return [dateKey(start),today];
}

export function presetRange(period,today){
 const end=new Date(`${today}T12:00:00`),start=new Date(end);
 if(period==='week')start.setDate(start.getDate()-start.getDay());
 if(period==='current-month')start.setDate(1);
 if(period==='quarter'){start.setDate(1);start.setMonth(Math.floor(start.getMonth()/3)*3)}
 if(period==='ytd'){start.setDate(1);start.setMonth(0)}
 return [dateKey(start),today];
}
export function selectRangeDate(start,end,date,today){
 if(date>today||(!end&&start&&date<start))return [start,end];
 return !start||end?[date,'']:[start,date];
}

export const fullyReviewed = day => Boolean(day?.checks?.length && day.checks.every(check => ['followed','broken','na'].includes(check.status)));
export function consistencyStreak(days,today){
 const reviewed=new Set(days.filter(fullyReviewed).map(day=>day.date));
 const cursor=new Date(`${today}T12:00:00`);
 const weekday=()=>cursor.getDay()!==0&&cursor.getDay()!==6;
 if(weekday()&&!reviewed.has(today))cursor.setDate(cursor.getDate()-1);
 let streak=0;
 while(true){
  if(weekday()){
   if(!reviewed.has(dateKey(cursor)))break;
   streak++;
  }
  cursor.setDate(cursor.getDate()-1);
 }
 return streak;
}
