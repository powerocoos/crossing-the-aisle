function start(D){
"use strict";
var STATES={AL:"Alabama",AK:"Alaska",AZ:"Arizona",AR:"Arkansas",CA:"California",CO:"Colorado",CT:"Connecticut",DE:"Delaware",FL:"Florida",GA:"Georgia",HI:"Hawaii",ID:"Idaho",IL:"Illinois",IN:"Indiana",IA:"Iowa",KS:"Kansas",KY:"Kentucky",LA:"Louisiana",ME:"Maine",MD:"Maryland",MA:"Massachusetts",MI:"Michigan",MN:"Minnesota",MS:"Mississippi",MO:"Missouri",MT:"Montana",NE:"Nebraska",NV:"Nevada",NH:"New Hampshire",NJ:"New Jersey",NM:"New Mexico",NY:"New York",NC:"North Carolina",ND:"North Dakota",OH:"Ohio",OK:"Oklahoma",OR:"Oregon",PA:"Pennsylvania",RI:"Rhode Island",SC:"South Carolina",SD:"South Dakota",TN:"Tennessee",TX:"Texas",UT:"Utah",VT:"Vermont",VA:"Virginia",WA:"Washington",WV:"West Virginia",WI:"Wisconsin",WY:"Wyoming",DC:"District of Columbia",PR:"Puerto Rico",GU:"Guam",VI:"U.S. Virgin Islands",AS:"American Samoa",MP:"Northern Mariana Islands"};
var POS={Y:"Yea",N:"Nay",P:"Present",X:"Not voting",S:"Other"};
var PN={D:"Democrats",R:"Republicans"},P1={D:"Democrat",R:"Republican"},OTHER={D:"R",R:"D"};
var MON=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
var mById={},vById={},idx={h:{},s:{}},grp={h:[],s:[]};
D.members.forEach(function(m){mById[m.id]=m});
D.hm.forEach(function(id,i){idx.h[id]=i;grp.h.push(mById[id].g)}); D.sm.forEach(function(id,i){idx.s[id]=i;grp.s.push(mById[id].g)});
var billVotes={};
D.votes.forEach(function(v){
  vById[v.id]=v;
  var c={D:{Y:0,N:0,P:0,X:0,S:0},R:{Y:0,N:0,P:0,X:0,S:0}},p=v.pos,g=grp[v.c],i,ch;
  for(i=0;i<p.length;i++){ch=p[i];if(ch!=='.'&&c[g[i]])c[g[i]][ch]++}
  v.cn=c; v.pl=!!(v.mD&&v.mR&&v.mD!==v.mR);
  v.xD=v.pl?c.D[v.mR]:0; v.xR=v.pl?c.R[v.mD]:0;
  if(v.b){(billVotes[v.b]=billVotes[v.b]||[]).push(v)}
});
var billList=Object.keys(D.bills).map(function(k){var b=D.bills[k];b.key=k;b.votes=billVotes[k]||[];b.last=b.votes[0]?b.votes[0].dt:'';return b})
  .sort(function(a,b){return a.last<b.last?1:a.last>b.last?-1:0});

function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
function fdate(d){var p=d.split('-');return MON[+p[1]-1]+' '+(+p[2])+', '+p[0]}
function mtag(m){return '<span class="pt '+m.g+'">('+m.p+'-'+m.s+(m.c==='h'&&m.d!=null?'-'+(m.d===0?'AL':m.d):'')+')</span>'}
function seat(m){if(m.c==='s')return 'Senator, '+(STATES[m.s]||m.s);
  if(!m.vot)return 'Delegate, '+(STATES[m.s]||m.s);
  return 'Representative, '+(STATES[m.s]||m.s)+(m.d?' district '+m.d:' at large')}
function chName(c){return c==='h'?'House':'Senate'}
function posOf(v,m){var i=idx[v.c][m.id];return i==null?'.':(v.pos[i]||'.')}
function maj(v,g){return g==='D'?v.mD:v.mR}
function isBreak(v,ch,g){var mj=maj(v,g);return mj&&(ch==='Y'||ch==='N')&&ch!==mj}
function isCross(v,ch,g){return v.pl&&isBreak(v,ch,g)}
function pbar(v,g){var c=v.cn[g],o=c.X+c.P+c.S,t=c.Y+c.N+o||1;
  return '<div class="pbar"><span class="k '+g+'">'+g+'</span><div class="bar" role="img" aria-label="'+PN[g]+': '+c.Y+' yea, '+c.N+' nay, '+o+' not voting"><i class="Y" style="width:'+(100*c.Y/t)+'%"></i><i class="N" style="width:'+(100*c.N/t)+'%"></i><i class="X" style="width:'+(100*o/t)+'%"></i></div><span><b>'+c.Y+'</b> Yea · <b>'+c.N+'</b> Nay</span></div>'}
function bars(v){return pbar(v,'D')+pbar(v,'R')}
function xchips(v){return (v.xD?'<span class="chip brk">'+v.xD+' D sided with R</span>':'')+(v.xR?'<span class="chip brk">'+v.xR+' R sided with D</span>':'')}
function voteRow(v,extra){
  return '<button class="row" data-go="vote-'+v.id+'"><div class="meta"><span>'+fdate(v.dt)+'</span><span class="chip '+v.c+'">'+chName(v.c)+'</span>'+(v.lab?'<span>'+esc(v.lab)+'</span>':'')+(extra?'':xchips(v))+'</div>'+
    '<div class="split"><div><div class="ttl">'+esc(v.t)+'</div><div class="sub">'+esc(v.q)+' · '+esc(v.res)+'</div></div>'+(extra||'')+'</div>'+(extra?'':bars(v))+'</button>'}

var state={tab:'votes',vCh:'',vKind:'fp',vX:'',vQ:'',bQ:'',mQ:'',mCh:'',mSt:'',mP:'',fSt:'',fZip:'',kCh:'s',kP:'D',rKind:'fp',rBrk:false,rQ:'',lim:40};
var TABS=[['votes','Recent votes'],['bills','Bills'],['members','Members'],['find','Find my rep'],['breaks','Crossing the aisle']];
var main=document.getElementById('main'),tabsEl=document.getElementById('tabs');
document.getElementById('asof').textContent=fdate(D.meta.latest);

function drawTabs(){tabsEl.innerHTML=TABS.map(function(t){return '<button data-go="'+t[0]+'"'+(state.tab===t[0]?' aria-current="page"':'')+'>'+t[1]+'</button>'}).join('')}
function kindOk(v,k){return k==='all'||(k==='fp'&&v.fp)||(k==='b'&&v.k==='b')||(k==='n'&&v.k==='n')}
function xOk(v,x){return !x||(x==='D'&&v.xD>0)||(x==='R'&&v.xR>0)||(x==='pl'&&v.pl)||(x==='bi'&&v.mD&&v.mD===v.mR)}
function opt(v,cur,label){return '<option value="'+v+'"'+(cur===v?' selected':'')+'>'+label+'</option>'}
function kindSelect(id,val){return '<select id="'+id+'" aria-label="Type of vote">'+opt('fp',val,'Final votes on bills')+opt('b',val,'All votes on bills')+opt('n',val,'Nominations')+opt('all',val,'Every roll call')+'</select>'}
function xSelect(id,val){return '<select id="'+id+'" aria-label="How the parties split">'+opt('',val,'Any party split')+opt('D',val,'Democrats sided with Republicans')+opt('R',val,'Republicans sided with Democrats')+opt('pl',val,'Parties voted opposite ways')+opt('bi',val,'Parties voted the same way')+'</select>'}
function seg(name,val,opts){return '<div class="seg" role="group">'+opts.map(function(o){return '<button data-set="'+name+'" data-val="'+o[0]+'" aria-pressed="'+(val===o[0])+'">'+o[1]+'</button>'}).join('')+'</div>'}
function match(q,text){if(!q)return true;q=q.toLowerCase().split(/\s+/);text=text.toLowerCase();for(var i=0;i<q.length;i++){if(q[i]&&text.indexOf(q[i])<0)return false}return true}
function paged(items,render){var n=Math.min(items.length,state.lim);var h='<p class="count">'+items.length.toLocaleString()+' result'+(items.length===1?'':'s')+'</p>';
  if(!items.length)return h+'<div class="panel">Nothing matches. Try a different search or filter.</div>';
  h+='<div class="list">'+items.slice(0,n).map(render).join('')+'</div>';
  if(items.length>n)h+='<button class="more" data-more="1">Show 40 more</button>';return h}

function viewVotes(){
  var items=D.votes.filter(function(v){return(!state.vCh||v.c===state.vCh)&&kindOk(v,state.vKind)&&xOk(v,state.vX)&&match(state.vQ,v.t+' '+(v.lab||'')+' '+v.q)});
  return '<h2>Recent votes</h2><p class="lede">Every roll call, newest first, with how each party split.</p>'+
   '<div class="filters"><input type="search" id="vQ" placeholder="Search bills and votes" aria-label="Search votes" value="'+esc(state.vQ)+'">'+kindSelect('vKind',state.vKind)+xSelect('vX',state.vX)+seg('vCh',state.vCh,[['','Both'],['h','House'],['s','Senate']])+'</div>'+
   '<div id="res">'+paged(items,function(v){return voteRow(v)})+'</div>'}
function billRow(b){var v=b.votes[0];
  return '<button class="row" data-go="bill-'+b.key+'"><div class="meta"><span>'+esc(b.lab)+'</span><span>'+b.votes.length+' roll call'+(b.votes.length===1?'':'s')+'</span>'+(v?'<span>Latest '+fdate(v.dt)+'</span>':'')+'</div><div class="ttl">'+esc(b.t||b.lab)+'</div>'+(v?'<div class="sub">'+chName(v.c)+': '+esc(v.q)+' · '+esc(v.res)+'</div>':'')+'</button>'}
function viewBills(){
  var items=billList.filter(function(b){return match(state.bQ,(b.t||'')+' '+b.lab+' '+b.lab.replace(/[. ]/g,''))});
  return '<h2>Bills</h2><p class="lede">Bills and resolutions that reached a recorded vote. Open one to see every roll call on it.</p>'+
   '<div class="filters"><input type="search" id="bQ" placeholder="Search by title or number, like H.R. 2102" aria-label="Search bills" value="'+esc(state.bQ)+'"></div>'+
   '<div id="res">'+paged(items,billRow)+'</div>'}
function memberRow(m){
  return '<button class="row" data-go="member-'+m.id+'"><div class="split"><div><div class="ttl">'+esc(m.n)+' '+mtag(m)+'</div><div class="sub">'+esc(seat(m))+(m.cur?'':' · no longer serving')+'</div></div>'+
   '<div class="right">'+(m.w!=null?'<div class="pct">'+m.w+'%</div><div class="tally">with party</div>':'<div class="tally">no votes</div>')+'</div></div></button>'}
function stateSelect(id,val,label){
  var keys=Object.keys(STATES).sort(function(a,b){return STATES[a]<STATES[b]?-1:1});
  return '<select id="'+id+'" aria-label="State"><option value="">'+label+'</option>'+keys.map(function(k){return opt(k,val,STATES[k])}).join('')+'</select>'}
function viewMembers(){
  var items=D.members.filter(function(m){return(!state.mCh||m.c===state.mCh)&&(!state.mP||m.g===state.mP)&&(!state.mSt||m.s===state.mSt)&&match(state.mQ,m.n+' '+m.l+' '+(STATES[m.s]||''))});
  return '<h2>Members</h2><p class="lede">Everyone who has served in the 119th Congress. Open a member for the full record.</p>'+
   '<div class="filters"><input type="search" id="mQ" placeholder="Search by name" aria-label="Search members" value="'+esc(state.mQ)+'">'+stateSelect('mSt',state.mSt,'All states')+seg('mP',state.mP,[['','All'],['D','Democrats'],['R','Republicans']])+seg('mCh',state.mCh,[['','Both'],['h','House'],['s','Senate']])+'</div>'+
   '<div id="res">'+paged(items,memberRow)+'</div>'}
var zips=null,zipsState='';
function loadZips(){
  if(zips||zipsState==='loading')return;zipsState='loading';
  fetch('/zips.json').then(function(r){if(!r.ok)throw new Error(r.status);return r.json()}).then(function(z){zips=z;zipsState='';if(cur.id==='find')render(true)}).catch(function(){zipsState='failed';if(cur.id==='find')render(true)})}
function repsFor(st,d){return D.members.filter(function(m){return m.cur&&m.c==='h'&&m.s===st&&(m.d||0)===d})}
function sensFor(st){return D.members.filter(function(m){return m.cur&&m.c==='s'&&m.s===st})}
function stateBlock(st,sen,rep){
  var h='';
  if(sen.length)h+='<h3>Senate</h3><div class="list">'+sen.map(memberRow).join('')+'</div>';
  h+='<h3>House</h3>'+(rep.length?'<div class="list">'+rep.map(memberRow).join('')+'</div>':'<div class="panel">No current House member on record.</div>');
  return h}
function zipResult(z){
  if(zipsState==='failed')return '<p class="note">The ZIP code list did not load. Check your connection, or pick your state below.</p>';
  if(!zips)return '<p class="note">Looking up '+esc(z)+'…</p>';
  var hit=zips[z];
  if(!hit)return '<div class="panel">ZIP code '+esc(z)+' is not in the list. Some new and PO box ZIP codes are missing. Pick your state below instead.</div>';
  var parts=hit.split(',').map(function(k){var m=/^([A-Z]{2})(\d+)$/.exec(k);return{st:m[1],d:+m[2]}}),h='',seen={},n=parts.length;
  h+='<p class="lede">ZIP code '+esc(z)+(n>1?' is split between '+n+' congressional districts. Which one is yours depends on your street address, so each is shown.':' is in one congressional district.')+'</p>';
  parts.forEach(function(p){
    var label=p.d===0?STATES[p.st]+' (at large)':STATES[p.st]+', District '+p.d;
    h+='<h3>'+esc(label)+'</h3>';
    var rep=repsFor(p.st,p.d);
    h+=rep.length?'<div class="list">'+rep.map(memberRow).join('')+'</div>':'<div class="panel">No current House member on record for this district.</div>'});
  Object.keys(parts.reduce(function(o,p){o[p.st]=1;return o},{})).forEach(function(st){
    var sen=sensFor(st);if(sen.length)h+='<h3>'+esc(STATES[st])+' senators</h3><div class="list">'+sen.map(memberRow).join('')+'</div>'});
  if(n>1)h+='<p class="note">To narrow it down, the House\'s own <a href="https://www.house.gov/representatives/find-your-representative" target="_blank" rel="noopener">Find Your Representative</a> tool can help.</p>';
  return h}
function viewFind(){
  var z=(state.fZip||'').replace(/\D/g,'');
  var h='<h2>Find my rep</h2><p class="lede">Enter your ZIP code to see who represents you in Congress.</p><div class="filters"><input type="search" id="fZip" inputmode="numeric" autocomplete="postal-code" maxlength="10" placeholder="ZIP code" aria-label="ZIP code" value="'+esc(state.fZip)+'"></div>';
  if(z.length===5){loadZips();h+=zipResult(z)}
  else if(z.length>0)h+='<p class="note">Enter all 5 digits of your ZIP code.</p>';
  h+='<h3>Or pick your state</h3><div class="filters">'+stateSelect('fSt',state.fSt,'Choose a state')+'</div>';
  if(!state.fSt)return h+'<p class="note">Districts follow the maps used for the current 119th Congress, which ends January 3, 2027. Members elected in November 2026 take office after that.</p>';
  var cur=D.members.filter(function(m){return m.s===state.fSt&&m.cur});
  var sen=cur.filter(function(m){return m.c==='s'}),rep=cur.filter(function(m){return m.c==='h'}).sort(function(a,b){return(a.d||0)-(b.d||0)});
  h+='<h3>Senate</h3>'+(sen.length?'<div class="list">'+sen.map(memberRow).join('')+'</div>':'<div class="panel">No senators. This is not a state.</div>');
  h+='<h3>House</h3>'+(rep.length?'<div class="list">'+rep.map(memberRow).join('')+'</div>':'<div class="panel">No current House member on record.</div>');
  if(rep.length>1)h+='<p class="note">House members are listed by district number. Enter your ZIP code above to find your district.</p>';
  return h}
function viewBreaks(){
  var g=state.kP,o=OTHER[g];
  var mem=D.members.filter(function(m){return m.g===g&&m.c===state.kCh&&m.pl>=50}).map(function(m){m.xp=Math.round(1000*m.x/m.pl)/10;return m}).sort(function(a,b){return b.xp-a.xp||b.x-a.x}).slice(0,15);
  var vs=D.votes.filter(function(v){return v.c===state.kCh&&(g==='D'?v.xD:v.xR)>0&&kindOk(v,state.rKind)});
  return '<h2>Crossing the aisle</h2><p class="lede">Votes where most Democrats and most Republicans voted opposite ways, and who voted with the other party.</p>'+
   '<div class="filters">'+seg('kP',g,[['D','Democrats'],['R','Republicans']])+seg('kCh',state.kCh,[['s','Senate'],['h','House']])+'</div>'+
   '<h3>'+PN[g]+' who side with '+PN[o]+' most often</h3><div class="list">'+mem.map(function(m){
     return '<button class="row" data-go="member-'+m.id+'"><div class="split"><div><div class="ttl">'+esc(m.n)+' '+mtag(m)+'</div><div class="sub">'+m.x+' of '+m.pl.toLocaleString()+' split votes</div></div><div class="right"><div class="pct" style="color:var(--brk)">'+m.xp+'%</div><div class="tally">with '+PN[o]+'</div></div></div></button>'}).join('')+'</div>'+
   '<p class="note">Share of the member\'s Yea or Nay votes, on roll calls where the parties split, that went with the other party. Members with fewer than 50 such votes are left out.</p>'+
   '<h3>Votes where '+PN[g]+' sided with '+PN[o]+'</h3><div class="filters">'+kindSelect('rKind',state.rKind)+'</div><div id="res">'+paged(vs,function(v){return voteRow(v)})+'</div>'}

function viewVote(id){var v=vById[id];if(!v)return '<div class="panel">Vote not found.</div>';
  var ids=v.c==='h'?D.hm:D.sm,G={D:{B:[],Y:[],N:[],P:[],X:[],S:[]},R:{B:[],Y:[],N:[],P:[],X:[],S:[]}},i,ch,m;
  for(i=0;i<ids.length;i++){ch=v.pos[i];if(ch==='.')continue;m=mById[ids[i]];if(!G[m.g])continue;G[m.g][ch].push(m);if(isCross(v,ch,m.g))G[m.g].B.push(m)}
  function names(list,cls){return '<div class="names '+(cls||'')+'">'+list.map(function(m){return '<button data-go="member-'+m.id+'">'+esc(m.l)+' '+mtag(m)+'</button>'}).join('')+'</div>'}
  function grpH(g,k,label){var l=G[g][k];if(!l.length)return '';return '<details'+(l.length<=30?' open':'')+'><summary><span class="dot '+(k==='P'||k==='S'?'X':k)+'"></span>'+label+' ('+l.length+')</summary>'+names(l)+'</details>'}
  var b=v.b&&D.bills[v.b];
  var h='<div class="meta" style="color:var(--muted);font-size:13px;margin-bottom:4px">'+fdate(v.dt)+' · '+chName(v.c)+' roll call '+v.r+(v.lab?' · '+esc(v.lab):'')+'</div>'+
   '<h2>'+esc(v.t)+'</h2><p class="lede">'+esc(v.q)+(v.am?'. '+esc(v.am):'')+'</p>'+
   '<div class="panel"><div class="split"><div><b>'+esc(v.res)+'</b></div><div class="right tally">Whole chamber: '+v.y+' Yea, '+v.n+' Nay</div></div>'+bars(v)+
   (v.mD&&v.mR?'<div class="tally" style="margin-top:8px">Most Democrats voted <b>'+POS[v.mD]+'</b>. Most Republicans voted <b>'+POS[v.mR]+'</b>.</div>':'')+'</div>';
  if(v.pl){
    h+='<h3>Democrats who sided with Republicans ('+G.D.B.length+')</h3>'+(G.D.B.length?names(G.D.B,'brk'):'<p class="note" style="margin:0">None.</p>');
    h+='<h3>Republicans who sided with Democrats ('+G.R.B.length+')</h3>'+(G.R.B.length?names(G.R.B,'brk'):'<p class="note" style="margin:0">None.</p>');
  }else if(v.mD&&v.mR){h+='<p class="note">Most members of both parties voted the same way on this one.</p>'}
  ['D','R'].forEach(function(g){h+='<h3>How each '+P1[g]+' voted</h3>'+grpH(g,'Y','Yea')+grpH(g,'N','Nay')+grpH(g,'P','Present')+grpH(g,'X','Not voting')+grpH(g,'S','Other')});
  h+='<div class="kv">'+(b?'<button class="back" style="margin:0" data-go="bill-'+v.b+'">All votes on '+esc(b.lab)+'</button>':'')+'<a href="'+esc(v.src)+'" target="_blank" rel="noopener">Official record</a></div>';
  return h}
function viewBill(key){var b=D.bills[key];if(!b)return '<div class="panel">Bill not found.</div>';
  return '<div class="meta" style="color:var(--muted);font-size:13px;margin-bottom:4px">'+esc(b.lab)+(b.intro?' · introduced '+fdate(b.intro):'')+'</div><h2>'+esc(b.t||b.lab)+'</h2>'+
   (b.sum?'<p class="lede" style="color:var(--ink)">'+esc(b.sum)+'</p>':'')+
   '<div class="kv">'+(b.url?'<a href="'+esc(b.url)+'" target="_blank" rel="noopener">Full text and status on Congress.gov</a>':'')+'</div>'+
   '<h3>Roll calls on this measure ('+b.votes.length+')</h3><div class="list">'+b.votes.map(function(v){return voteRow(v)}).join('')+'</div>'}
function viewMember(id){var m=mById[id];if(!m)return '<div class="panel">Member not found.</div>';
  var o=OTHER[m.g];
  var rec=D.votes.filter(function(v){var ch=posOf(v,m);if(ch==='.')return false;if(state.rBrk&&!isCross(v,ch,m.g))return false;return kindOk(v,state.rKind)&&match(state.rQ,v.t+' '+(v.lab||'')+' '+v.q)});
  var h='<h2>'+esc(m.n)+'</h2><p class="lede">'+esc(seat(m))+' · '+(m.p==='I'?'Independent, caucuses with '+PN[m.g]:P1[m.g])+(m.cur?'':' · no longer serving')+'</p>'+
   '<div class="tiles"><div class="tile brk"><div class="num">'+(m.x||0)+'</div><div class="lab">times sided with '+PN[o]+', of '+(m.pl||0).toLocaleString()+' split votes</div></div>'+
   '<div class="tile"><div class="num">'+(m.w!=null?m.w+'%':'n/a')+'</div><div class="lab">voted with most '+PN[m.g]+'</div></div>'+
   '<div class="tile"><div class="num">'+(m.miss!=null?m.miss+'%':'n/a')+'</div><div class="lab">votes missed</div></div>'+
   '<div class="tile"><div class="num">'+(m.vc||0).toLocaleString()+'</div><div class="lab">votes cast of '+(m.rc||0).toLocaleString()+'</div></div></div>'+
   '<div class="kv">'+(m.web?'<a href="'+esc(m.web)+'" target="_blank" rel="noopener">Official website</a>':'')+(m.ph?'<span>Office phone '+esc(m.ph)+'</span>':'')+'</div>'+
   '<h3>Voting record</h3><div class="filters"><input type="search" id="rQ" placeholder="Search this record" aria-label="Search this record" value="'+esc(state.rQ)+'">'+kindSelect('rKind',state.rKind)+
   '<label class="check"><input type="checkbox" id="rBrk"'+(state.rBrk?' checked':'')+'> Only votes with '+PN[o]+'</label></div>'+
   '<div id="res">'+paged(rec,function(v){var ch=posOf(v,m);return voteRow(v,'<div class="right"><span class="pill '+ch+'">'+POS[ch]+'</span>'+(isCross(v,ch,m.g)?'<div style="margin-top:4px"><span class="chip brk">With '+o+'</span></div>':'')+'</div>')})+'</div>';
  return h}

var TABPATH={votes:'/',bills:'/bills/',members:'/members/',find:'/find/',breaks:'/crossing/'};
function urlFor(r){return r.kind==='tab'?TABPATH[r.id]:'/'+r.kind+'/'+r.id+'/'}
function parseTarget(t){var m=/^(vote|bill|member)-(.+)$/.exec(t);return m?{kind:m[1],id:m[2]}:{kind:'tab',id:t}}
function route(){
  var h=(location.hash||'').replace(/^#/,''),m=/^(vote|bill|member)-(.+)$/.exec(h);
  if(m){try{history.replaceState(null,'','/'+m[1]+'/'+m[2]+'/')}catch(e){}return{kind:m[1],id:m[2]}}
  var p=location.pathname.replace(/index\.html$/,'');if(p.charAt(p.length-1)!=='/')p+='/';
  m=/^\/(vote|bill|member)\/([^\/]+)\/$/.exec(p);
  if(m)return{kind:m[1],id:decodeURIComponent(m[2])};
  for(var k in TABPATH)if(TABPATH[k]===p)return{kind:'tab',id:k};
  return{kind:'tab',id:'votes'}}
function titleFor(r){var S=' · Crossing the Aisle';
  if(r.kind==='vote'){var v=vById[r.id];return v?((v.lab?v.lab+': ':'')+v.t).slice(0,70)+' · '+chName(v.c)+' vote'+S:'Vote'+S}
  if(r.kind==='bill'){var b=D.bills[r.id];return b?(b.lab+': '+(b.t||'')).slice(0,80)+S:'Bill'+S}
  if(r.kind==='member'){var m=mById[r.id];return m?m.n+' voting record'+S:'Member'+S}
  return r.id==='votes'?'Crossing the Aisle':({bills:'Bills',members:'Members of Congress',find:'Find my rep',breaks:'Who crosses the aisle'})[r.id]+S}
var cur=null,depth=0;
function render(keepFocus){
  var r=cur,html;
  if(r.kind==='tab'){state.tab=r.id;html={votes:viewVotes,bills:viewBills,members:viewMembers,find:viewFind,breaks:viewBreaks}[r.id]()}
  else{html='<div class="topline"><button class="back" data-back="1">← Back</button><button class="share" data-share="1">Copy link</button></div>'+({vote:viewVote,bill:viewBill,member:viewMember}[r.kind](r.id))}
  var f=keepFocus&&document.activeElement&&document.activeElement.id,pos=f&&document.activeElement.selectionStart;
  main.innerHTML=html;drawTabs();document.title=titleFor(r);
  if(f){var el=document.getElementById(f);if(el){el.focus();try{el.setSelectionRange(pos,pos)}catch(e){}}}}
function go(target){
  cur=parseTarget(target);state.lim=40;
  if(cur.kind==='member'){state.rQ='';state.rBrk=false}
  try{history.pushState(null,'',urlFor(cur));depth++}catch(e){}
  render();window.scrollTo(0,0)}
window.addEventListener('popstate',function(){cur=route();state.lim=40;if(depth>0)depth--;render();window.scrollTo(0,0)});
document.addEventListener('click',function(e){
  var t=e.target.closest('[data-go],[data-back],[data-more],[data-set],[data-share]');if(!t)return;
  if(t.dataset.go){go(t.dataset.go)}
  else if(t.dataset.back){if(depth>0)history.back();else go(state.tab)}
  else if(t.dataset.more){state.lim+=40;render()}
  else if(t.dataset.set){state[t.dataset.set]=t.dataset.val;state.lim=40;render()}
  else if(t.dataset.share){
    var url=location.href;
    if(navigator.share){navigator.share({title:document.title,url:url}).catch(function(){})}
    else if(navigator.clipboard){navigator.clipboard.writeText(url).then(function(){t.textContent='Link copied'},function(){t.textContent=url})}
    else{t.textContent=url}}});
var timer;
document.addEventListener('input',function(e){var id=e.target.id;if(!id||!(id in state))return;
  state[id]=e.target.type==='checkbox'?e.target.checked:e.target.value;state.lim=40;
  if(e.target.type==='search'){clearTimeout(timer);timer=setTimeout(function(){render(true)},140)}else render()});
cur=route();render();
}
fetch('/data.json').then(function(r){if(!r.ok)throw new Error(r.status);return r.json()}).then(start).catch(function(){
  document.getElementById('main').innerHTML='<div class="panel">The vote data did not load. Check your connection and reload the page.</div>'});
