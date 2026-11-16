const {useState,useEffect,useRef,useMemo}=React;
const SEV={LOW:'#22c55e',MEDIUM:'#eab308',HIGH:'#f97316',CRITICAL:'#ef4444'};
const STC={FLYING:'text-emerald-400',IDLE:'text-slate-400',PAUSED:'text-yellow-400',BLOCKED:'text-orange-400',COMPLETED:'text-sky-400',E_STOP:'text-red-400',ERROR:'text-red-400'};
const BTN={sky:'bg-sky-600 hover:bg-sky-500',green:'bg-emerald-600 hover:bg-emerald-500',red:'bg-red-600 hover:bg-red-500',amber:'bg-amber-600 hover:bg-amber-500',slate:'bg-slate-700 hover:bg-slate-600'};
const hav=(a,b)=>{const R=6371008.8,r=Math.PI/180,dp=(b[0]-a[0])*r,dl=(b[1]-a[1])*r;const x=Math.sin(dp/2)**2+Math.cos(a[0]*r)*Math.cos(b[0]*r)*Math.sin(dl/2)**2;return 2*R*Math.asin(Math.sqrt(x))};
const tm=s=>s?new Date(s).toLocaleTimeString():'-';
async function api(path,method='GET',body){const r=await fetch(path,{method,headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});if(!r.ok){let m=r.statusText;try{m=(await r.json()).detail||m}catch(e){}throw new Error(typeof m==='string'?m:JSON.stringify(m))}return r.json()}
function beep(){try{const c=new (window.AudioContext||window.webkitAudioContext)(),o=c.createOscillator(),g=c.createGain();o.frequency.value=880;g.gain.value=.08;o.connect(g);g.connect(c.destination);o.start();setTimeout(()=>{o.stop();c.close()},350)}catch(e){}}

const Card=({title,children,className='',right})=>(<section className={`bg-[#101b38] border border-slate-700/60 rounded-lg p-3 ${className}`}>{title&&<div className="flex justify-between items-center mb-2"><h3 className="text-sm font-semibold text-slate-300">{title}</h3>{right}</div>}{children}</section>);
const Btn=({children,onClick,color='sky',disabled,className=''})=>(<button disabled={disabled} onClick={onClick} className={`${BTN[color]} disabled:opacity-40 text-white text-sm px-3 py-1.5 rounded focus:outline focus:outline-2 focus:outline-sky-300 ${className}`}>{children}</button>);
const Stat=({label,value,color='text-slate-100'})=>(<div className="bg-[#101b38] border border-slate-700/60 rounded-lg p-3"><div className="text-xs text-slate-400">{label}</div><div className={`text-2xl font-semibold ${color}`}>{value}</div></div>);
const Sev=({s})=>(<span className="px-2 py-0.5 rounded text-xs font-semibold text-black" style={{background:SEV[s]}}>{s}</span>);
const inp='bg-[#0a1226] border border-slate-600 rounded px-2 py-1 text-sm';

function MapView({st,sel,onSelect,onClick,preview,editId,onEdit,pick,height='h-[520px]',showPending=true}){
  const el=useRef(),map=useRef(),dyn=useRef(),zl=useRef(),rl=useRef(),pv=useRef(),cb=useRef();cb.current=onClick;
  const ed=useRef();ed.current=onEdit;const [tileWarn,setTileWarn]=useState(false);
  useEffect(()=>{const m=L.map(el.current).setView([12.975,77.60],12);
    const ATTR='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
    let errs=0,fallback=false,osm,hot;
    osm=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:ATTR}).addTo(m);
    osm.on('tileload',()=>{errs=0;setTileWarn(false)});
    osm.on('tileerror',()=>{if(++errs>=4&&!fallback){fallback=true;m.removeLayer(osm);   /* same OSM data, different server */
      hot=L.tileLayer('https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png',{maxZoom:19,subdomains:'abc',attribution:ATTR}).addTo(m);hot.bringToBack();
      let e2=0;hot.on('tileload',()=>{e2=0;setTileWarn(false)});hot.on('tileerror',()=>{if(++e2>=4)setTileWarn(true)})}});
    map.current=m;setTimeout(()=>m.invalidateSize(),0);setTimeout(()=>m.invalidateSize(),500);
    const ro=window.ResizeObserver?new ResizeObserver(()=>m.invalidateSize()):null;ro&&ro.observe(el.current);rl.current=L.layerGroup().addTo(m);zl.current=L.layerGroup().addTo(m);dyn.current=L.layerGroup().addTo(m);pv.current=L.layerGroup().addTo(m);
    m.on('click',e=>cb.current&&cb.current(e.latlng));return()=>{ro&&ro.disconnect();m.remove()}},[]);
  useEffect(()=>{el.current.classList.toggle('pick',!!pick)},[pick]);
  const regKey=JSON.stringify(st.regions);
  useEffect(()=>{rl.current.clearLayers();st.regions.forEach(r=>{const b=r.bounds;L.rectangle([[b[0],b[1]],[b[2],b[3]]],{color:r.color,weight:2,dashArray:'8 6',fillColor:r.color,fillOpacity:.06,interactive:false}).addTo(rl.current).bindTooltip(r.name,{permanent:true,direction:'center',className:'leaflet-tooltip'}).openTooltip()})},[regKey]);
  const zKey=JSON.stringify(st.zones)+editId;
  useEffect(()=>{zl.current.clearLayers();st.zones.forEach(z=>{
    const o={color:'#ef4444',fillColor:'#ef4444',fillOpacity:.25,weight:2};
    const sh=z.shape==='circle'?L.circle(z.center,{...o,radius:z.radius_m}):L.polygon(z.points,o);
    sh.addTo(zl.current).bindTooltip(`${z.id} ${z.name}${z.reason?' - '+z.reason:''}`);
    if(editId===z.id){const hi=L.divIcon({className:'',html:'<div class="hnd"></div>',iconSize:[14,14],iconAnchor:[7,7]});
      if(z.shape==='circle'){const c=z.center,dl=z.radius_m/(111320*Math.cos(c[0]*Math.PI/180));
        const mc=L.marker(c,{draggable:true,icon:hi}).addTo(zl.current),mr=L.marker([c[0],c[1]+dl],{draggable:true,icon:hi}).addTo(zl.current);
        mc.on('dragend',()=>{const p=mc.getLatLng();ed.current(z,{center:[p.lat,p.lng]})});
        mr.on('dragend',()=>{const p=mr.getLatLng();ed.current(z,{radius_m:Math.max(50,Math.round(hav(c,[p.lat,p.lng])))})});
      }else z.points.forEach((pt,i)=>{const mk=L.marker(pt,{draggable:true,icon:hi}).addTo(zl.current);
        mk.on('dragend',()=>{const p=mk.getLatLng(),pts=z.points.map(x=>[...x]);pts[i]=[p.lat,p.lng];ed.current(z,{points:pts})});
        mk.on('contextmenu',()=>{if(z.points.length>3)ed.current(z,{points:z.points.filter((_,k)=>k!==i)})})})}})},[zKey]);
  useEffect(()=>{const g=dyn.current;g.clearLayers();
    st.drones.forEach((d,i)=>{const bad=d.status==='BLOCKED'||d.status==='ERROR'||d.status==='E_STOP';
      if(d.trail.length>1)L.polyline(d.trail,{color:d.color,weight:3,opacity:.45,interactive:false}).addTo(g);
      if(d.route.length>1)L.polyline(d.route,{color:bad?'#ef4444':d.color,weight:3,dashArray:'8 6',opacity:.95,interactive:false}).addTo(g);
      L.circle([d.lat,d.lon],{radius:d.detection_radius_m,color:d.color,weight:1,fillOpacity:.07,dashArray:'3 5',interactive:false}).addTo(g);
      if(d.destination)L.circleMarker(d.destination,{radius:7,color:'#facc15',fillOpacity:.6}).addTo(g).bindTooltip(`${d.name} destination`);
      const ic=L.divIcon({className:'',html:`<div class="drone-ic" style="background:${d.color};outline:${sel===d.id?'2px solid #fff':'none'}">${i+1}</div>`,iconSize:[26,26],iconAnchor:[13,13]});
      L.marker([d.lat,d.lon],{icon:ic,zIndexOffset:1000}).addTo(g).bindTooltip(`${d.name} (${d.status}) ${d.battery}%`,{permanent:true,direction:'right',offset:[14,0],className:'drone-label'}).on('click',()=>onSelect&&onSelect(d.id))});
    st.incidents.forEach(i=>{if(i.detection_status==='PENDING'){if(showPending)L.circleMarker([i.lat,i.lon],{radius:6,color:'#475569',weight:2,dashArray:'2 3',fillOpacity:0}).addTo(g).bindTooltip(`${i.id} pending (not yet detected)`)}
      else if(i.detection_status==='EXCLUDED'){L.circleMarker([i.lat,i.lon],{radius:7,color:'#94a3b8',weight:2,fillColor:'#475569',fillOpacity:.65}).addTo(g).bindTooltip(`${i.id} excluded - inside no-fly zone`)}
      else{const fresh=i.status==='DETECTED';const ic=L.divIcon({className:'',html:`<div class="${fresh?'pulse':''}" style="width:18px;height:18px;border-radius:50%;background:#dc2626;border:2px solid #fff;box-shadow:0 0 0 2px #7f1d1d;opacity:${i.status==='RESOLVED'?.4:1}"></div>`,iconSize:[18,18],iconAnchor:[9,9]});
        L.marker([i.lat,i.lon],{icon:ic}).addTo(g).bindTooltip(`${i.id} ${i.type_label}<br>${i.severity} - ${i.status}<br>by ${i.detected_by.join(', ')}`)}})},[st]);
  const pk=JSON.stringify(preview);
  useEffect(()=>{pv.current.clearLayers();if(!preview)return;const o={color:'#facc15',dashArray:'4 4',weight:2,fillOpacity:.1};
    if(preview.type==='circle'){L.circleMarker(preview.center,{radius:5,color:'#facc15'}).addTo(pv.current);if(preview.radius)L.circle(preview.center,{...o,radius:preview.radius}).addTo(pv.current)}
    else{preview.points.forEach(p=>L.circleMarker(p,{radius:4,color:'#facc15'}).addTo(pv.current));L.polygon(preview.points,o).addTo(pv.current)}},[pk]);
  return <div className="relative"><div ref={el} className={`${height} w-full rounded-lg border border-slate-700`}/>
</div>;
}

function DroneTable({st,sel,setSel}){return(<div className="overflow-x-auto"><table className="w-full text-sm"><thead className="text-slate-400 text-left"><tr>{['Drone','Status','Region','Battery','Position','Alt','Speed','Progress'].map(h=><th key={h} className="py-1 pr-3 font-medium">{h}</th>)}</tr></thead><tbody>
  {st.drones.map(d=>(<tr key={d.id} onClick={()=>setSel&&setSel(d.id)} className={`border-t border-slate-700/50 cursor-pointer ${sel===d.id?'bg-slate-700/30':''}`}>
    <td className="py-1 pr-3"><span className="inline-block w-2 h-2 rounded-full mr-1" style={{background:d.color}}/>{d.name}</td><td className={`pr-3 font-semibold ${STC[d.status]}`}>{d.status}{d.scan&&<span className="text-amber-300 font-normal"> scanning {d.scan.pct}%</span>}</td>
    <td className="pr-3">{d.region_id||'-'}</td><td className="pr-3"><div className="w-20 h-2 bg-slate-700 rounded"><div className={`h-2 rounded ${d.battery<20?'bg-red-500':'bg-emerald-500'}`} style={{width:d.battery+'%'}}/></div><span className="text-xs">{d.battery}%</span></td>
    <td className="pr-3 font-mono text-xs">{d.lat.toFixed(5)}, {d.lon.toFixed(5)}</td><td className="pr-3">{d.alt} m</td><td className="pr-3">{d.speed} m/s</td>
    <td className="pr-3"><div className="w-20 h-2 bg-slate-700 rounded"><div className="h-2 rounded bg-sky-500" style={{width:d.progress+'%'}}/></div><span className="text-xs">{d.progress}%</span></td></tr>))}</tbody></table></div>)}

function IncidentTable({incidents,act,actions=true,all=true}){
  const rows=[...incidents].filter(i=>all||i.detection_status==='DETECTED').reverse();
  if(!rows.length)return <p className="text-sm text-slate-400">No incidents yet. Start the generator on the Emergency Generator page.</p>;
  return(<div className="overflow-x-auto max-h-96"><table className="w-full text-sm"><thead className="text-slate-400 text-left sticky top-0 bg-[#101b38]"><tr>{['ID','Type','GPS','Severity','Region','Detected','Detected by','Status',''].map(h=><th key={h} className="py-1 pr-3 font-medium">{h}</th>)}</tr></thead><tbody>
  {rows.map(i=>(<tr key={i.id} className="border-t border-slate-700/50"><td className="py-1 pr-3 font-mono">{i.id}</td><td className="pr-3">{i.type_label}</td><td className="pr-3 font-mono text-xs">{i.lat.toFixed(5)}, {i.lon.toFixed(5)}</td><td className="pr-3"><Sev s={i.severity}/></td><td className="pr-3">{i.region}</td>
   <td className="pr-3">{tm(i.detected_at)}</td><td className="pr-3">{i.detected_by.join(', ')||'-'}</td><td className={`pr-3 font-semibold ${i.status==='UNDETECTED'?'text-slate-400':i.status==='RESOLVED'?'text-emerald-400':i.status==='EXCLUDED'?'text-slate-500':'text-orange-300'}`}>{i.status}</td>
   <td className="whitespace-nowrap">{actions&&i.status==='DETECTED'&&<Btn color="amber" className="mr-1" onClick={()=>act(`/api/incidents/${i.id}/acknowledge`)}>Acknowledge</Btn>}{actions&&(i.status==='DETECTED'||i.status==='ACKNOWLEDGED')&&<Btn color="green" onClick={()=>act(`/api/incidents/${i.id}/resolve`)}>Resolve</Btn>}</td></tr>))}</tbody></table></div>)}

const Log=({log,n=8})=>(<ul className="text-sm space-y-1 max-h-72 overflow-y-auto">{[...log].filter(e=>e.priority!=='QUIET').reverse().slice(0,n).map((e,i)=>(<li key={i} className={`border-l-2 pl-2 ${e.priority==='ALERT'?'border-red-500 text-red-200':e.priority==='WARN'?'border-amber-500 text-amber-200':'border-slate-600 text-slate-300'}`}><span className="text-xs text-slate-500">{tm(e.time)} </span>{e.message}</li>))}{!log.length&&<li className="text-slate-400">No alerts yet.</li>}</ul>);

function FleetControls({act,sel}){return(<div className="flex flex-wrap gap-2">
  <Btn color="green" onClick={()=>act('/api/fleet/start')}>Start all</Btn><Btn color="amber" onClick={()=>act('/api/fleet/pause')}>Pause all</Btn><Btn onClick={()=>act('/api/fleet/resume')}>Resume all</Btn><Btn color="red" onClick={()=>act('/api/fleet/estop')}>Emergency stop all</Btn></div>)}

function Dashboard({st,act,sel,setSel}){const s=st.stats;return(<div className="space-y-3">
  <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-2"><Stat label="Total drones" value={s.drones}/><Stat label="Active" value={s.active} color="text-emerald-400"/><Stat label="Idle" value={s.idle}/><Stat label="Errors" value={s.errors} color={s.errors?'text-red-400':''}/>
   <Stat label="Emergencies" value={s.incidents}/><Stat label="Detected" value={s.detected} color="text-orange-300"/><Stat label="Undetected" value={s.undetected}/><Stat label="Critical open" value={s.critical} color={s.critical?'text-red-400':''}/></div>
  <div className="grid xl:grid-cols-3 gap-3"><div className="xl:col-span-2 space-y-2"><MapView st={st} sel={sel} onSelect={setSel}/><FleetControls act={act}/></div>
   <div className="space-y-3"><Card title="Demo scenario" right={<div className="flex gap-1"><Btn color="green" onClick={()=>act('/api/demo/start')}>Run demo</Btn><Btn color="slate" onClick={()=>act('/api/demo/stop')}>Stop</Btn><Btn color="slate" onClick={()=>act('/api/reset')}>Reset</Btn></div>}>
     <ol className="text-sm space-y-1">{st.demo_steps.map((d,i)=><li key={i} className="text-emerald-300">{d.text}</li>)}{!st.demo_steps.length&&<li className="text-slate-400">Configure no-fly zones and emergencies first. Run demo preserves your setup, sweeps each assigned region, then detects all eligible incidents outside restricted zones.</li>}</ol></Card>
    <Card title="Recent alerts"><Log log={st.log}/></Card></div></div>
  <Card title="Drone monitoring"><DroneTable st={st} sel={sel} setSel={setSel}/></Card>
  <Card title="Incidents"><IncidentTable incidents={st.incidents} act={act}/></Card></div>)}

function LiveMap({st,act,sel,setSel}){const d=st.drones.find(x=>x.id===sel)||st.drones[0];return(<div className="grid xl:grid-cols-4 gap-3"><div className="xl:col-span-3"><MapView st={st} sel={d.id} onSelect={setSel} height="h-[640px]"/></div>
  <div className="space-y-3"><Card title={`${d.name} telemetry`}><dl className="text-sm grid grid-cols-2 gap-y-1"><dt className="text-slate-400">Status</dt><dd className={STC[d.status]}>{d.status}</dd><dt className="text-slate-400">Latitude</dt><dd>{d.lat.toFixed(5)}</dd><dt className="text-slate-400">Longitude</dt><dd>{d.lon.toFixed(5)}</dd><dt className="text-slate-400">Altitude</dt><dd>{d.alt} m</dd><dt className="text-slate-400">Speed</dt><dd>{d.speed} m/s</dd><dt className="text-slate-400">Heading</dt><dd>{d.heading}&deg;</dd><dt className="text-slate-400">Battery</dt><dd>{d.battery}%</dd><dt className="text-slate-400">Progress</dt><dd>{d.progress}%</dd><dt className="text-slate-400">Region</dt><dd>{d.region_id||'-'}</dd><dt className="text-slate-400">Scan radius</dt><dd>{d.detection_radius_m} m</dd></dl>
    {d.note&&<p className="text-amber-300 text-sm mt-2">{d.note}</p>}
    <div className="flex flex-wrap gap-2 mt-3"><Btn color="green" onClick={()=>act(`/api/drones/${d.id}/mission`,'POST',{type:d.destination&&!d.region_id?'transit':'inspect'})}>Start</Btn><Btn color="amber" onClick={()=>act(`/api/drones/${d.id}/pause`)}>Pause</Btn><Btn onClick={()=>act(`/api/drones/${d.id}/resume`)}>Resume</Btn><Btn color="red" onClick={()=>act(`/api/drones/${d.id}/estop`)}>E-Stop</Btn><Btn color="slate" onClick={()=>act(`/api/drones/${d.id}/reset`)}>Reset</Btn></div></Card>
   <Card title="Fleet"><FleetControls act={act}/><div className="mt-2 text-xs text-slate-400">Cyan dashed = planned safe route. Red = blocked. Dotted circle = scan radius.</div></Card></div></div>)}

function Planner({st,act,sel,setSel}){const [pick,setPick]=useState(null);const d=st.drones.find(x=>x.id===sel)||st.drones[0];
  const click=async ll=>{if(!pick)return;await act(`/api/drones/${d.id}/${pick==='start'?'start-location':'destination'}`,'POST',{lat:ll.lat,lon:ll.lng});setPick(null)};
  return(<div className="grid xl:grid-cols-4 gap-3"><div className="xl:col-span-3"><MapView st={st} sel={d.id} onSelect={setSel} onClick={click} pick={pick} height="h-[640px]"/></div>
  <div className="space-y-3"><Card title="Mission planner"><label className="text-xs text-slate-400">Drone</label><select className={inp+' w-full mb-2'} value={d.id} onChange={e=>setSel(e.target.value)}>{st.drones.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select>
    <label className="text-xs text-slate-400">Inspection region</label><select className={inp+' w-full mb-2'} value={d.region_id||''} onChange={e=>act(`/api/drones/${d.id}/assign`,'POST',{region_id:e.target.value})}><option value="" disabled>Select region</option>{st.regions.map(r=><option key={r.id} value={r.id}>{r.name}</option>)}</select>
    <div className="flex flex-wrap gap-2 mb-2"><Btn color={pick==='start'?'amber':'slate'} onClick={()=>setPick(pick==='start'?null:'start')}>{pick==='start'?'Click map...':'Set start'}</Btn><Btn color={pick==='dest'?'amber':'slate'} onClick={()=>setPick(pick==='dest'?null:'dest')}>{pick==='dest'?'Click map...':'Set destination'}</Btn>{d.destination&&<Btn color="slate" onClick={()=>act(`/api/drones/${d.id}/destination`,'DELETE')}>Clear</Btn>}</div>
    <p className="text-xs text-slate-400 mb-2">Destination: {d.destination?d.destination.map(x=>x.toFixed(5)).join(', '):'none'}. Start: {d.base.map(x=>x.toFixed(5)).join(', ')}</p>
    <div className="flex flex-wrap gap-2"><Btn color="green" disabled={!d.region_id} onClick={()=>act(`/api/drones/${d.id}/mission`,'POST',{type:'inspect'})}>Start inspection</Btn><Btn disabled={!d.destination} onClick={()=>act(`/api/drones/${d.id}/mission`,'POST',{type:'transit'})}>Fly to destination</Btn></div></Card>
   <Card title="Quick setup"><Btn onClick={async()=>{for(let i=0;i<3;i++)await act(`/api/drones/${st.drones[i].id}/assign`,'POST',{region_id:st.regions[i].id})}}>Assign Drone 1/2/3 to R1/R2/R3</Btn><div className="mt-2"><FleetControls act={act}/></div></Card></div></div>)}

function NFZ({st,act}){const [mode,setMode]=useState(null),[pts,setPts]=useState([]),[editId,setEditId]=useState(null),[renameId,setRenameId]=useState(null),[rename,setRename]=useState({name:'',reason:''}),[f,setF]=useState({name:'Restricted Area',reason:'Operator-defined'});
  const click=async ll=>{const p=[ll.lat,ll.lng];if(mode==='circle'){if(!pts.length)setPts([p]);else{await act('/api/zones','POST',{...f,shape:'circle',center:pts[0],radius_m:Math.max(100,Math.round(hav(pts[0],p)))});setPts([]);setMode(null)}}else if(mode==='poly')setPts([...pts,p])};
  const finish=async()=>{if(pts.length<3)return;await act('/api/zones','POST',{...f,shape:'polygon',points:pts});setPts([]);setMode(null)};
  const put=(z,patch)=>act(`/api/zones/${z.id}`,'PUT',{name:z.name,reason:z.reason,shape:z.shape,center:z.center,radius_m:z.radius_m,points:z.points,...patch});
  const preview=mode==='circle'&&pts.length?{type:'circle',center:pts[0],radius:0}:mode==='poly'&&pts.length?{type:'poly',points:pts}:null;
  return(<div className="grid xl:grid-cols-4 gap-3"><div className="xl:col-span-3"><MapView st={st} onClick={click} pick={!!mode} preview={preview} editId={editId} onEdit={put} height="h-[640px]"/></div>
  <div className="space-y-3"><Card title="Draw a no-fly zone"><input className={inp+' w-full mb-1'} value={f.name} onChange={e=>setF({...f,name:e.target.value})} placeholder="Name"/><input className={inp+' w-full mb-2'} value={f.reason} onChange={e=>setF({...f,reason:e.target.value})} placeholder="Reason"/>
    <div className="flex flex-wrap gap-2"><Btn color={mode==='circle'?'amber':'sky'} onClick={()=>{setMode('circle');setPts([])}}>Circle</Btn><Btn color={mode==='poly'?'amber':'sky'} onClick={()=>{setMode('poly');setPts([])}}>Polygon</Btn>{mode==='poly'&&<Btn color="green" onClick={finish} disabled={pts.length<3}>Finish ({pts.length})</Btn>}{mode&&<Btn color="slate" onClick={()=>{setMode(null);setPts([])}}>Cancel</Btn>}</div>
    <p className="text-xs text-slate-400 mt-2">{mode==='circle'?(pts.length?'Click again to set the radius.':'Click the map to set the centre.'):mode==='poly'?'Click each corner, then Finish.':'Choose a shape, then click the map.'}</p></Card>
   <Card title={`Zones (${st.zones.length})`}><ul className="space-y-2">{st.zones.map(z=>(<li key={z.id} className="text-sm border border-red-900/60 rounded p-2"><div className="font-semibold text-red-300">{z.id} {z.name}</div><div className="text-xs text-slate-400">{z.shape==='circle'?`Circle r=${Math.round(z.radius_m)} m`:`Polygon, ${z.points.length} points`}{z.reason&&` - ${z.reason}`}</div>
     <div className="flex flex-wrap gap-1 mt-1"><Btn color={editId===z.id?'amber':'slate'} onClick={()=>setEditId(editId===z.id?null:z.id)}>{editId===z.id?'Done editing':'Edit boundary'}</Btn><Btn color="slate" onClick={()=>{setRenameId(renameId===z.id?null:z.id);setRename({name:z.name,reason:z.reason||''})}}>Rename</Btn><Btn color="red" onClick={()=>{act('/api/zones/'+z.id,'DELETE');if(editId===z.id)setEditId(null)}}>Remove</Btn></div>
     {renameId===z.id&&<div className="mt-2 space-y-1"><input className={inp+' w-full'} value={rename.name} onChange={e=>setRename({...rename,name:e.target.value})} placeholder="Zone name"/><input className={inp+' w-full'} value={rename.reason} onChange={e=>setRename({...rename,reason:e.target.value})} placeholder="Reason"/><div className="flex gap-1"><Btn color="green" onClick={async()=>{await put(z,rename);setRenameId(null)}}>Save</Btn><Btn color="slate" onClick={()=>setRenameId(null)}>Cancel</Btn></div></div>}{editId===z.id&&<p className="text-xs text-slate-400 mt-1">Drag the white handles.{z.shape==='circle'?' Centre handle moves, edge handle resizes.':' Right-click a corner to delete it.'}</p>}</li>))}{!st.zones.length&&<li className="text-sm text-slate-400">No zones. Draw one on the map.</li>}</ul></Card></div></div>)}

function Generator({st,act}){const g=st.generator;const [seed,setSeed]=useState(g.seed??'');const [iv,setIv]=useState(g.interval_s);const [reg,setReg]=useState('');const [ty,setTy]=useState('');const [sv,setSv]=useState('');const [count,setCount]=useState(5);
  const cfg=body=>act('/api/generator/config','POST',body);
  return(<div className="grid xl:grid-cols-3 gap-3"><div className="space-y-3"><Card title="Emergency generator (SIMULATED)"><p className="text-xs text-slate-400 mb-2">Independent Python module. Incidents are detected during a scan or in the final end-of-sweep pass.</p>
   <div className="grid grid-cols-2 gap-2 mb-2"><select className={inp} value={reg} onChange={e=>setReg(e.target.value)}><option value="">Random region</option>{st.regions.map(r=><option key={r.id} value={r.id}>{r.name}</option>)}</select><select className={inp} value={ty} onChange={e=>setTy(e.target.value)}><option value="">Random type</option>{g.types.map(t=><option key={t.key} value={t.key}>{t.label}</option>)}</select><select className={inp} value={sv} onChange={e=>setSv(e.target.value)}><option value="">Random severity</option>{Object.keys(SEV).map(s=><option key={s}>{s}</option>)}</select></div>
   <div className="flex flex-wrap items-center gap-2"><Btn onClick={()=>act('/api/generator/generate','POST',{region_id:reg||null,type:ty||null,severity:sv||null})}>Generate one emergency</Btn><label className="text-xs text-slate-400">Batch size</label><input type="number" min="1" max="50" className={inp+' w-20'} value={count} onChange={e=>setCount(Math.max(1,Math.min(50,+e.target.value||1)))}/><Btn color="green" onClick={()=>act('/api/generator/generate-batch','POST',{count,region_id:reg||null,type:ty||null,severity:sv||null})}>Pre-generate emergencies</Btn></div><p className="text-xs text-slate-400 mt-2">Configure emergencies here before starting the demo. New incidents are placed outside all no-fly zones.</p></Card>
   <Card title="Automatic generation"><div className="flex gap-2 mb-2"><Btn color="green" disabled={g.auto} onClick={async()=>{await cfg({interval_s:+iv});act('/api/generator/start')}}>Start</Btn><Btn color="red" disabled={!g.auto} onClick={()=>act('/api/generator/stop')}>Stop</Btn><span className={`text-sm self-center ${g.auto?'text-emerald-400':'text-slate-400'}`}>{g.auto?'Running':'Stopped'}</span></div>
    <label className="text-xs text-slate-400">Interval (seconds)</label><div className="flex gap-2 mb-2"><input type="number" min="1" className={inp+' w-24'} value={iv} onChange={e=>setIv(e.target.value)}/><Btn color="slate" onClick={()=>cfg({interval_s:+iv})}>Apply</Btn></div>
    <label className="text-xs text-slate-400">Random seed (reproducible)</label><div className="flex gap-2 mb-2"><input type="number" className={inp+' w-24'} value={seed} onChange={e=>setSeed(e.target.value)}/><Btn color="slate" onClick={()=>seed!==''&&cfg({seed:+seed})}>Apply</Btn></div>
    <label className="text-xs text-slate-400">Regions used by auto mode</label><div className="flex flex-wrap gap-3">{st.regions.map(r=>(<label key={r.id} className="text-sm"><input type="checkbox" className="mr-1" checked={g.enabled_regions.includes(r.id)} onChange={e=>cfg({enabled_regions:e.target.checked?[...g.enabled_regions,r.id]:g.enabled_regions.filter(x=>x!==r.id)})}/>{r.id}</label>))}</div></Card></div>
   <div className="xl:col-span-2 space-y-3"><MapView st={st} height="h-[360px]"/><Card title={`All generated incidents (${st.incidents.length})`}><IncidentTable incidents={st.incidents} act={act} actions={false}/></Card></div></div>)}

function Detection({st,act,sel,setSel}){return(<div className="space-y-3"><div className="grid xl:grid-cols-3 gap-3"><div className="xl:col-span-2"><MapView st={st} sel={sel} onSelect={setSel} height="h-[460px]"/></div>
  <div className="space-y-2">{st.drones.map(d=>(<Card key={d.id} title={`${d.name} - ${d.region_id?st.regions.find(r=>r.id===d.region_id).name:'no region'}`}><div className="text-sm grid grid-cols-2 gap-y-1"><span className="text-slate-400">Coverage</span><span>{d.progress}%</span><span className="text-slate-400">Regions scanned</span><span>{d.scanned_regions.join(', ')||'none yet'}</span><span className="text-slate-400">Detected</span><span className="text-orange-300">{d.detected.length} {d.detected.join(' ')}</span><span className="text-slate-400">Pending in region</span><span>{d.pending}</span><span className="text-slate-400">Scan state</span><span className={d.scan?'text-amber-300':''}>{d.scan?`Scanning ${d.scan.incident} ${d.scan.pct}%`:'Searching'}</span></div></Card>))}</div></div>
  <Card title="Detected incidents"><IncidentTable incidents={st.incidents} act={act} all={false}/></Card></div>)}

function Reports({st,act}){const [flt,setFlt]=useState('ALL');const rows=st.incidents.filter(i=>flt==='ALL'||i.status===flt);return(<div className="space-y-3">
  <Card title="Export" right={<div className="flex gap-2"><a href="/api/reports/incidents.csv"><Btn color="green">Download CSV</Btn></a><a href="/api/reports/incidents.pdf"><Btn>Download PDF</Btn></a></div>}><p className="text-sm text-slate-400">Reports contain simulated incidents only; no real emergencies or drones are involved.</p></Card>
  <Card title={`Incident history (${rows.length})`} right={<select className={inp} value={flt} onChange={e=>setFlt(e.target.value)}>{['ALL','UNDETECTED','DETECTED','ACKNOWLEDGED','RESOLVED','EXCLUDED'].map(s=><option key={s}>{s}</option>)}</select>}>
   <div className="overflow-x-auto"><table className="w-full text-sm"><thead className="text-slate-400 text-left"><tr>{['ID','Type','GPS','Severity','Generated','Detected','By','Status','Description','Report'].map(h=><th key={h} className="py-1 pr-3 font-medium">{h}</th>)}</tr></thead><tbody>
   {[...rows].reverse().map(i=>(<tr key={i.id} className="border-t border-slate-700/50"><td className="py-1 pr-3 font-mono">{i.id}</td><td className="pr-3">{i.type_label}</td><td className="pr-3 font-mono text-xs">{i.lat.toFixed(5)}, {i.lon.toFixed(5)}</td><td className="pr-3"><Sev s={i.severity}/></td><td className="pr-3">{tm(i.created_at)}</td><td className="pr-3">{tm(i.detected_at)}</td><td className="pr-3">{i.detected_by.join(', ')||'-'}</td><td className="pr-3">{i.status}</td><td className="pr-3 text-xs max-w-xs">{i.description}</td>
    <td className="whitespace-nowrap"><a className="text-sky-400 underline mr-2" href={`/api/reports/incident/${i.id}.pdf`}>PDF</a><a className="text-sky-400 underline" href={`/api/reports/incident/${i.id}.json`} target="_blank">JSON</a></td></tr>))}</tbody></table></div></Card></div>)}

const PAGES=[['dash','Command Dashboard',Dashboard],['live','Live Drone Map',LiveMap],['plan','Mission Planner',Planner],['nfz','No-Fly Zone Manager',NFZ],['gen','Emergency Generator',Generator],['det','Incident Detection',Detection],['rep','Reports & History',Reports]];

function App(){const [st,setSt]=useState(null),[page,setPage]=useState('dash'),[toasts,setToasts]=useState([]),[conn,setConn]=useState(false),[sel,setSel]=useState('DRN-1');
  const toast=(msg,pr='INFO')=>{if(pr==='WARN')return;const id=Math.random();setToasts(t=>[...t.slice(-4),{id,msg,pr}]);setTimeout(()=>setToasts(t=>t.filter(x=>x.id!==id)),pr==='ALERT'?15000:6000);if(pr==='ALERT')beep()};
  useEffect(()=>{let ws,timer,dead=false;const go=()=>{ws=new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host+'/ws');ws.onopen=()=>setConn(true);ws.onclose=()=>{setConn(false);if(!dead)timer=setTimeout(go,1500)};ws.onmessage=m=>{const d=JSON.parse(m.data);setSt(d.state);(d.events||[]).forEach(e=>{if(e.priority==='ALERT'||e.priority==='INFO')toast(e.message,e.priority)})}};go();return()=>{dead=true;clearTimeout(timer);ws&&ws.close()}},[]);
  const act=async(p,m='POST',b)=>{try{return await api(p,m,b)}catch(e){toast(e.message,'WARN')}};
  const Page=PAGES.find(p=>p[0]===page)[2];
  return(<div className="min-h-screen flex flex-col"><header className="flex flex-wrap items-center gap-3 px-4 py-2 bg-[#0d1733] border-b border-slate-700"><h1 className="text-lg font-bold text-sky-300">AeroPulse AI</h1><span className="text-xs px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40">SIMULATION - no real drones or emergencies</span>
    <div className="ml-auto flex items-center gap-3 text-sm"><label className="flex items-center gap-2 text-slate-400">Sim speed x{st?st.scale:10}<input type="range" min="1" max="40" value={st?st.scale:10} onChange={e=>act('/api/sim/speed','POST',{scale:+e.target.value})}/></label><span className={conn?'text-emerald-400':'text-red-400'}>{conn?'Link online':'Link lost'}</span></div></header>
   <nav className="flex gap-1 overflow-x-auto px-3 py-2 bg-[#0d1733]">{PAGES.map(p=><button key={p[0]} onClick={()=>setPage(p[0])} className={`whitespace-nowrap px-3 py-1.5 rounded text-sm ${page===p[0]?'bg-sky-600 text-white':'text-slate-300 hover:bg-slate-700'}`}>{p[1]}</button>)}</nav>
   <main className="p-3 flex-1">{st?<Page st={st} act={act} sel={sel} setSel={setSel}/>:<p className="text-slate-400">Connecting to ground station...</p>}</main>
   <div className="fixed top-3 right-3 z-[2000] w-80 space-y-2" role="status" aria-live="polite">{toasts.map(t=><div key={t.id} className={`rounded p-3 text-sm shadow-lg border ${t.pr==='ALERT'?'bg-red-900 border-red-400':t.pr==='WARN'?'bg-amber-900 border-amber-500':'bg-slate-800 border-slate-600'}`}>{t.pr==='ALERT'&&<b>EMERGENCY ALERT: </b>}{t.msg}</div>)}</div></div>)}
ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
