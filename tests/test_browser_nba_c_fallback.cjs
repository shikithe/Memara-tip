"use strict";
const fs=require("node:fs");
const vm=require("node:vm");
const assert=require("node:assert/strict");

const html=fs.readFileSync("index.html","utf8");
const start=html.indexOf("async function checkNbaEspnDirectly(){");
const end=html.indexOf("async function refreshPublishedData(){",start);
assert(start>=0&&end>start,"NBA browser fallback function missing");
const fallback=html.slice(start,end);

async function scenario({points=24,espnPlayer="6583",priorState="unverified",expectedLive=true}={}) {
  const kickoff=new Date(Date.now()-30*60*1000).toISOString();
  const leg={sport:"basketball",market:"player_points",espn_event_id:"401909315",
    event_id:"401909315",player_id:"6583",
    fixture_id:"espn:basketball:nba:401909315:6583",
    home:"Washington Wizards",away:"Boston Celtics",points_line:21.5,
    pick:"over",start_utc:kickoff};
  const original={ticket:"C",index:0,home:leg.home,away:leg.away,state:priorState};
  if(priorState==="final") Object.assign(original,{event_id:leg.event_id,fixture_id:leg.fixture_id,
    sport:"basketball",player_points:28,result_status:"pogođen",source:"espn-public-unofficial"});
  const doc={header:{competitions:[{status:{type:{state:"in",completed:false},period:3,
    displayClock:"08:05"}}]},boxscore:{players:[{statistics:[{keys:["minutes","points"],
      athletes:[{athlete:{id:espnPlayer},stats:["28",String(points)]}]}]}]}};
  let calls=0,renderCount=0;
  const ctx={
    document:{hidden:false},
    currentData:{date:"2026-11-24",tickets:[{id:"C",matches:[leg]}]},
    liveScores:{date:"2026-11-24",updated_at_utc:new Date().toISOString(),matches:[original]},
    fetch:async url=>{calls++;assert(url.includes("401909315"));return {ok:true,json:async()=>doc}},
    render:()=>{renderCount++},showRefreshStatus:()=>{},refreshClock:()=>"",
    Date,Set,Map,Number,String,Promise
  };
  vm.createContext(ctx);vm.runInContext(fallback,ctx);
  await vm.runInContext("checkNbaEspnDirectly()",ctx);
  const entries=ctx.liveScores.matches.filter(x=>x.ticket==="C"&&x.index===0);
  assert.equal(calls,1,"should fetch actual event just once");
  assert.equal(entries.length,1,"C must not hold a stale duplicate at same ticket+index");
  if(expectedLive){
    assert.equal(entries[0].state,"live");
    assert.equal(entries[0].event_id,"401909315");
    assert.equal(entries[0].fixture_id,leg.fixture_id);
    assert.equal(entries[0].player_id,"6583");
    assert.equal(entries[0].player_points,points);
    assert.equal(entries[0].result_status,"pogođen");
    assert.equal(renderCount,1);
  } else {
    assert.equal(entries[0].state,priorState);
    assert.equal(renderCount,0);
  }
}
(async()=>{
  await scenario();
  await scenario({priorState:"final",expectedLive:false});
  await scenario({espnPlayer:"wrong",expectedLive:false});
  console.log("NBA_C_BROWSER_FALLBACK_UPDATES_EXISTING_PLACEHOLDER_WITHOUT_DUPLICATES");
})().catch(e=>{console.error(e);process.exitCode=1});
