export function paginationItems(current, total) {
 const visible=new Set([0,total-1,current-1,current,current+1]);
 if(current<2){visible.add(1);visible.add(2)}
 if(current>total-3){visible.add(total-2);visible.add(total-3)}
 const sorted=[...visible].filter(n=>n>=0&&n<total).sort((a,b)=>a-b),items=[];
 for(const n of sorted){
  const previous=items.at(-1);
  if(typeof previous==='number'&&n-previous>1)items.push(`gap-${previous}`);
  items.push(n);
 }
 return items;
}
