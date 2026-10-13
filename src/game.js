// Questions come from the bank (BANK, built by build.py): every individual Olympic and
// World Championships final 2016–2025. results[0] is the answer; q.clue is the clue row.
// SCHEDULE (from schedule.py) lists each day's five questions as indexes into BANK.
const ROUNDS=5, START=new Date(2026,9,11), SITE="https://bell-lap.vercel.app";
const PLACEHOLDER={s:"0.00", ms:"0:00.00", hms:"0:00:00", m:"0.00"};
const BYID={};
BANK.forEach(q=>{q.mark=q.results[0][3]; q.n=q.results[q.results.length-1][0]; BYID[q.id]=q;});

// ---- helpers ----
function store(k,v){try{if(v===undefined)return JSON.parse(localStorage.getItem(k));localStorage.setItem(k,JSON.stringify(v));}catch(e){return null;}}
const $=s=>document.querySelector(s);
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const ord=n=>{const s=["th","st","nd","rd"],v=n%100;return n+(s[(v-20)%10]||s[v]||s[0]);};
const pad=(n,w)=>String(n).padStart(w,"0");
function rng(seed){return()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;};}

function fmt(v,f){
  if(f==="m") return v.toFixed(2)+" m";
  if(f==="s") return v.toFixed(2);
  if(f==="ms"){const m=Math.floor(v/60);return m+":"+pad((v-m*60).toFixed(2),5);}
  const h=Math.floor(v/3600),m=Math.floor((v-h*3600)/60);return h+":"+pad(m,2)+":"+pad(Math.round(v-h*3600-m*60),2);
}
// ref is the clue mark on screen. Ambiguous input like "1.57" or "157" in a race timed in
// minutes is read as whichever meaning lands closer to it (here 1:57).
function parse(str,f,ref){
  let t=str.trim().replace(/,/g,".").replace(/\s*m$/i,"");
  if(!t) return null;
  if(f==="m"||f==="s") return /^\d+(\.\d+)?$/.test(t)?parseFloat(t):NaN;
  if(f==="ms"&&ref){
    const c=[]; let m;
    if((m=t.match(/^(\d+)\.(\d{2})$/))&&+m[2]<60) c.push(+m[1]*60+(+m[2]), parseFloat(t));
    else if((m=t.match(/^(\d+)(\d{2})$/))&&+m[2]<60) c.push(+m[1]*60+(+m[2]), +t);
    if(c.length) return c.reduce((a,b)=>Math.abs(Math.log(b/ref))<Math.abs(Math.log(a/ref))?b:a);
  }
  if(f==="hms") t=t.replace(/\./g,":");
  else if((t.match(/\./g)||[]).length>1){const i=t.lastIndexOf(".");t=t.slice(0,i).replace(/\./g,":")+t.slice(i);}
  if(!/^[\d:.]+$/.test(t)) return NaN;
  const p=t.split(":");
  if(p.some(x=>x===""||isNaN(+x))||p.slice(1).some(x=>+x>=60)) return NaN;
  if(f==="hms"&&p.length===2) p.push("0");
  return p.reduce((a,x)=>a*60+(+x),0);
}
// Typo guard: the winner is never more than ~26% from the clue mark, so a guess 1.5x away is
// probably a slip. fixes() re-reads the digits with the separator moved and keeps the closest sane reading.
const sane=(v,ref)=>Math.abs(Math.log(v/ref))<=0.4;
function fixes(str,f,ref,v){
  const d=str.replace(/\D/g,""), c=[];
  if(f==="s"||f==="m") for(let i=1;i<d.length;i++) c.push(d.slice(0,i)+"."+d.slice(i));
  if(f==="ms"&&d.length>=3) c.push(d.slice(0,-2)+":"+d.slice(-2));
  if(f==="ms"&&d.length>=4) c.push(d.slice(0,-3)+":"+d.slice(-3,-1)+"."+d.slice(-1));
  if(f==="ms"&&d.length>=5) c.push(d.slice(0,-4)+":"+d.slice(-4,-2)+"."+d.slice(-2));
  if(f==="hms"&&d.length>=5) c.push(d.slice(0,-4)+":"+d.slice(-4,-2)+":"+d.slice(-2));
  return c.map(x=>parse(x,f,ref)).filter(x=>x>0&&sane(x,ref)&&Math.abs(x-v)>1e-9)
    .reduce((a,b)=>a==null||Math.abs(Math.log(b/ref))<Math.abs(Math.log(a/ref))?b:a,null);
}
// Generous by design: half points at the clue's distance from the winner (min 4%); flat near the answer.
const clueRow=q=>q.results[q.clue];
const tolerance=q=>q.mark*Math.max(0.04,Math.abs(clueRow(q)[3]-q.mark)/q.mark);
const points=(g,q)=>{const e=Math.abs(g-q.mark)/tolerance(q);return Math.round(1000/(1+e*e));};
const better=(q,a,b)=>q.field?a>b:a<b;
// Where a guess would have finished. Big road fields only list the top 10 and the last finisher.
function placing(q,g){
  const rows=q.results, ahead=rows.filter(r=>better(q,r[3],g)).length;
  const tied=rows.some(r=>Math.abs(r[3]-g)<1e-9);
  if(q.partial&&ahead===rows.length-1) return {outside:true, ahead};
  if(ahead===rows.length) return {behind:true, place:q.n+1, ahead};
  return {place:tied?rows[ahead][0]:ahead===0?1:rows[ahead-1][0]+1, tied, ahead};
}
const chip=p=>p>=900?"🟩":p>=600?"🟨":p>=300?"🟧":"🟥";
const who=r=>`${esc(r[1])} <small>${r[2]}</small>`;

// Daily sets are fixed in SCHEDULE (built by schedule.py with the same picker, so days already
// played never change). If the schedule ever runs out it wraps around.
const daily=day=>SCHEDULE[(day-1)%SCHEDULE.length].map(i=>BANK[i].id);
// Practice sets: one sprint/hurdles, one middle/distance/road, one jump, one throw, one wildcard,
// balanced between men's and women's events.
function pick(seed,used=new Set()){
  const r=rng(seed), order=BANK.map(q=>q.id).filter(id=>!used.has(id));
  for(let i=order.length-1;i>0;i--){const j=Math.floor(r()*(i+1));[order[i],order[j]]=[order[j],order[i]];}
  const buckets=[["sprint","hurdles"],["middle","distance","road"],["jumps"],["throws"]], chosen=[];
  buckets.forEach(b=>{const id=order.find(id=>!chosen.includes(id)&&b.includes(BYID[id].group))||order.find(id=>!chosen.includes(id));chosen.push(id);});
  const men=chosen.filter(id=>BYID[id].g==="M").length, want=men>2?"W":men<2?"M":null;
  chosen.push(order.find(id=>!chosen.includes(id)&&(!want||BYID[id].g===want))||order.find(id=>!chosen.includes(id)));
  // shuffle the order of the five rounds
  for(let i=chosen.length-1;i>0;i--){const j=Math.floor(r()*(i+1));[chosen[i],chosen[j]]=[chosen[j],chosen[i]];}
  return chosen;
}

// ---- state ----
const today=new Date();today.setHours(0,0,0,0);
const dayNo=Math.round((today-START)/864e5)+1;
const dayKey="pf9-day-"+today.toISOString().slice(0,10);
let practice=false, interacted=false;
let game=valid(store(dayKey))||fresh(daily(Math.max(1,dayNo)));
function valid(g){return g&&g.rounds&&g.rounds.every(r=>BYID[r.id])?g:null;}
function fresh(ids){return {rounds:ids.map(id=>({id,g1:null,score:null})),cur:0,phase:"g1"};}
function save(){if(!practice)store(dayKey,game);}

// ---- render ----
function render(){
  $("#day").textContent=practice?"Practice":"No. "+dayNo;
  $("#hintbtn").hidden=game.phase!=="g1";
  if(game.phase!=="g1") $("#hintpop").hidePopover?.();
  $("#lanes").innerHTML=game.rounds.map((r,k)=>`<li class="${k===game.cur&&game.phase!=="done"?"cur":""}"><span>${k+1}</span>${r.score!=null?`<b>${r.score}</b>`:""}</li>`).join("");
  if(game.phase==="done") return renderResults();
  const r=game.rounds[game.cur], q=BYID[r.id];
  const head=`<div><p class="eyebrow">${esc(q.ctx)}</p><h1 class="event">${esc(q.label)}</h1></div>`;
  if(game.phase==="reveal") return renderReveal(head,r,q);

  // Hint: the clue row, in a popup from the header button.
  const c=clueRow(q);
  $("#hintpop").innerHTML=`<span class="w">${esc(c[1])}</span> <span class="v">${fmt(c[3],q.fmt)}</span>`;
  $("#stage").innerHTML=`${head}
    <p class="ask">What was the winning ${q.field?"mark":"time"}? One guess.</p>
    <form class="guess" id="f" autocomplete="off">
      <input id="guess" type="text" inputmode="decimal" placeholder="${PLACEHOLDER[q.fmt]}" aria-label="Your guess" enterkeyhint="go">
      <button class="btn" id="go" disabled>Go</button>
    </form>
    <p class="readas" id="readas" aria-live="polite">${q.fmt==="ms"?"Dots work too, e.g. 1.58.20":q.fmt==="hms"?"Dots work too, e.g. 2.08.30":""}</p>`;
  const inp=$("#guess"), go=$("#go"), ra=$("#readas"), tip=ra.innerHTML, ref=c[3];
  let armed=false;
  inp.addEventListener("input",()=>{
    const v=parse(inp.value,q.fmt,ref);
    armed=false;go.textContent="Go";
    if(v===null){ra.className="readas";ra.innerHTML=tip;go.disabled=true;return;}
    if(isNaN(v)||v<=0){ra.className="readas err";ra.innerHTML=`<b>Can't read that.</b> Try the format ${PLACEHOLDER[q.fmt]}.`;go.disabled=true;return;}
    go.disabled=false;
    if(sane(v,ref)){ra.className="readas";ra.innerHTML=`Read as <b>${fmt(v,q.fmt)}</b>`;return;}
    const fx=fixes(inp.value,q.fmt,ref,v);
    ra.className="readas err";
    ra.innerHTML=`Read as <b>${fmt(v,q.fmt)}</b>. `+(fx?`Did you mean <button type="button" class="fix" id="fix">${fmt(fx,q.fmt)}</button>?`:`Typo?`);
    if(fx) $("#fix").onclick=()=>{inp.value=fmt(fx,q.fmt).replace(/ m$/,"");inp.dispatchEvent(new Event("input"));inp.focus({preventScroll:true});};
  });
  // A guess that looks like a typo needs a second press.
  $("#f").addEventListener("submit",e=>{
    e.preventDefault();const v=parse(inp.value,q.fmt,ref);if(!v||isNaN(v)) return;
    if(!sane(v,ref)&&!armed){armed=true;go.textContent="Sure?";return;}
    submit(v);
  });
  if(interacted) inp.focus({preventScroll:true});
}

function submit(v){
  interacted=true;
  const r=game.rounds[game.cur], q=BYID[r.id];
  r.g1=v; r.score=points(v,q); game.phase="reveal";
  save();render();
}

function placedLine(q,g){
  const p=placing(q,g);
  if(p.outside) return `That mark would place outside the top 10.`;
  if(p.behind) return `Behind the whole field.`;
  if(p.place===1&&p.tied) return `Spot on.`;
  if(p.place===1) return `${q.field==="high"?"Higher":q.field?"Further":"Faster"} than the winner. That mark would have won gold.`;
  return `That mark would ${p.tied?"tie for":"place"} ${ord(p.place)} of ${q.n}.`;
}

function straight(q,g){
  const res=q.results, c=clueRow(q), best=q.mark, worst=c[3];
  const X=v=>6+(v-worst)/(best-worst)*84;   // clue row at 6%, finish line at 90%
  const clamp=p=>Math.max(2,Math.min(98,p));
  const gx=X(g), p=clamp(gx), edge=p<14?"el":p>86?"er":"";
  return `<div class="straight" role="img" aria-label="Your guess against the field, finish line on the right">
    <div class="surface"></div>
    ${res.slice(1,q.clue+1).map(x=>`<div class="tick" style="left:${clamp(X(x[3]))}%"></div>`).join("")}
    <div class="finish" style="left:90%"></div>
    <div class="pin ${edge}" style="left:${p}%"><span>${gx<2?"◀ ":""}You ${fmt(g,q.fmt)}${gx>98?" ▶":""}</span></div>
    <span class="end">${ord(c[0])} · ${fmt(worst,q.fmt)}</span>
    <span class="end r">Winner · ${fmt(best,q.fmt)}</span>
  </div>`;
}

function board(q,g){
  const res=q.results, n=res.length;
  const rank={you:0,r:1,wr:2};
  const rows=[...res.map((x,k)=>({t:"r",v:x[3],k,x})),{t:"you",v:g},...(q.wr?[{t:"wr",v:q.wr[0]}]:[])]
    .sort((a,b)=>a.v===b.v?(rank[a.t]-rank[b.t])||((a.k||0)-(b.k||0)):(better(q,a.v,b.v)?-1:1));
  let html="", hidden=0;
  const flush=()=>{if(hidden){html+=`<tr class="gap"><td></td><td colspan="2">${hidden} more</td></tr>`;hidden=0;}};
  rows.forEach(rw=>{
    if(rw.t==="r"){
      if(q.partial&&rw.k===n-1) hidden+=rw.x[0]-res[n-2][0]-1;   // unlisted finishers between 10th and last
    }
    flush();
    if(rw.t==="you") html+=`<tr class="you"><td>You</td><td>Your guess</td><td class="m">${fmt(g,q.fmt)}</td></tr>`;
    else if(rw.t==="wr") html+=`<tr class="wr"><td>WR</td><td>World record going in <small>${q.wr[2]}</small></td><td class="m">${fmt(q.wr[0],q.fmt)}</td></tr>`;
    else html+=`<tr><td>${rw.x[0]}</td><td>${who(rw.x)}</td><td class="m">${fmt(rw.v,q.fmt)}</td></tr>`;
  });
  flush();
  return `<table class="board">${html}</table>`;
}

function renderReveal(head,r,q){
  const g=r.g1, w=q.results[0];
  const note=(q.wrBroken&&q.wr?`Broke the world record of ${fmt(q.wr[0],q.fmt)} set by ${esc(q.wr[1])} in ${q.wr[2]}. `:"")
    +`<a href="https://en.wikipedia.org/wiki/${encodeURIComponent(q.src.replace(/ /g,"_"))}" target="_blank" rel="noopener">Full results</a>`;
  $("#stage").innerHTML=`${head}
    <div class="answer">
      <div><span class="l">Winner</span><div class="big">${fmt(q.mark,q.fmt)}</div><div class="who">${esc(w[1])}, ${w[2]}</div>${q.wrBroken?`<span class="badge">New world record</span>`:""}</div>
      <div class="score"><span class="l">Points</span><div class="big">${r.score}</div></div>
    </div>
    <p class="placed">${placedLine(q,g)}</p>
    ${straight(q,g)}
    <button class="btn wide" id="next">${game.cur===ROUNDS-1?"See results":"Next final"}</button>
    <details class="more"><summary>Results</summary>${board(q,g)}<p class="note">${note}</p></details>`;
  $("#next").onclick=next;
  if(interacted) $("#next").focus({preventScroll:true});
}
function next(){
  if(game.cur>=ROUNDS-1) game.phase="done"; else {game.cur++;game.phase="g1";}
  save();render();window.scrollTo({top:0});
}

function shareText(){
  const t=game.rounds.reduce((a,r)=>a+r.score,0);
  return `Bell-Lap ${practice?"practice":"No. "+dayNo}\n${t.toLocaleString()} / 5,000\n${game.rounds.map(r=>chip(r.score)).join("")}\n${SITE}`;
}
function renderResults(){
  const t=game.rounds.reduce((a,r)=>a+r.score,0);
  $("#stage").innerHTML=`<div><p class="eyebrow">${practice?"Practice set":"Today"}</p><div class="total">${t.toLocaleString()} <small>/ 5,000</small></div></div>
    <table class="board sum">${game.rounds.map(r=>{const q=BYID[r.id],p=placing(q,r.g1);return `<tr><td>${chip(r.score)}</td>
      <td>${esc(q.label)}<small>${esc(q.ctx)} · ${fmt(q.mark,q.fmt)}, you ${fmt(r.g1,q.fmt)}${p.place?` (${ord(p.place)})`:""}</small></td>
      <td class="s">${r.score}</td></tr>`;}).join("")}</table>
    <pre class="share" id="share">${esc(shareText())}</pre>
    <div class="row"><button class="btn" id="copy">Copy</button><button class="btn quiet" id="again">Practice</button></div>`;
  $("#copy").onclick=()=>{
    const b=$("#copy");
    navigator.clipboard.writeText(shareText()).then(()=>{b.textContent="Copied";},()=>{
      const s=window.getSelection(),rg=document.createRange();rg.selectNodeContents($("#share"));s.removeAllRanges();s.addRange(rg);b.textContent="Selected";});
  };
  $("#again").onclick=()=>{practice=true;interacted=true;game=fresh(pick(Math.floor(Math.random()*1e9)));render();window.scrollTo({top:0});};
}

document.addEventListener("keydown",e=>{if(e.key==="Enter"&&game.phase==="reveal"&&document.activeElement?.id!=="next"&&!e.target.closest?.("summary,a")){e.preventDefault();next();}});
render();
