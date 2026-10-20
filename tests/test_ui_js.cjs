/* Smoke-test the real UI script without pulling browser dependencies. */
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const path = require('path');
const html = fs.readFileSync(path.join(__dirname,'..','ui','index.html'),'utf8');
const js = html.split('<script>')[1].split('</script>')[0];
const elements = {};
function element(id) {
  if (!elements[id]) elements[id] = {
    value:'',innerHTML:'',textContent:'',className:'',
    classList:{add(){},remove(){}},scrollIntoView(){},focus(){}
  };
  return elements[id];
}
const BOT = {id:'abc012',name:'Exact V4 Probe',path:'/bots/test.bot.cfg',exists:true,
             category:'Standard',favorite:false,diagnostics:{framework:'rlbot-v4',observation:'unknown'}};
const setup = {players:[{kind:'human',team:0},{kind:'bot',id:BOT.id,team:1}],
  map:'Stadium_P',mode:'Soccar',mutators:{},options:{}};
const fakeResponses = {'/api/bots':[BOT],'/api/setup':setup,'/api/status':{running:false}};
const context=vm.createContext({
  document:{getElementById:element,querySelectorAll(){return []}},
  window:{addEventListener(){}},
  fetch:async url=>({ok:true,json:async()=>fakeResponses[url]||{ok:true}}),
  setInterval(){},setTimeout,clearTimeout,console,confirm:()=>true,
});
vm.runInContext(js,context);
setTimeout(()=>{
  try {
    assert(elements.blueSlots.innerHTML.includes('Human'),'Human missing in Blue');
    assert(elements.orangeSlots.innerHTML.includes('Exact V4 Probe'),'Imported V4 missing in Orange');
    assert(elements.library.innerHTML.includes('onclick="addBot(&quot;abc012&quot;,0)"'), 'button HTML unsafe');
    vm.runInContext("addBot('abc012',0)",context);
    assert(elements.blueCount.textContent==='2 PLAYERS','Bot assign button failed');
    vm.runInContext('usePreset(2)',context);
    assert(elements.blueCount.textContent==='2 PLAYERS' && elements.orangeCount.textContent==='2 PLAYERS','2v2 preset failed');
    console.log('UI bootstrap, library, buttons and 2v2: PASS');
  } catch(e){console.error(e);process.exitCode=1}
},80);
