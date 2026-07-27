// CoolDecide scene generator — DecideDeck's motion feel, CoolDecide's template.
// Layout is CoolDecide's STACKED panels (top/bottom, countdown chip between), not
// DecideDeck's side-by-side cards. The reveal choreography (countdown pop, winner
// glow + crown + WINNER pill + bar count-up, idle breathe) is ported; the winner
// LIFTS + scales instead of "rising off a table" so it never collides with the
// other panel. Skin: sky-blue gradient + dots, white-border sticker panels, Anton.
// Usage: node cd_anim.js <rounds.json> <outdir>
const fs = require('fs');
const path = require('path');
const [,, roundsPath, outdir] = process.argv;
const rounds = JSON.parse(fs.readFileSync(roundsPath, 'utf8'));

const b64 = (p) => 'data:image/jpeg;base64,' + fs.readFileSync(p).toString('base64');
const esc = (s) => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const ANTON = 'data:font/ttf;base64,' +
  fs.readFileSync(path.join(__dirname, 'fonts', 'Anton-Regular.ttf')).toString('base64');

// CoolDecide palettes: [bgTop, bgBot, aColor, bColor], matching card.PALETTES.
const PAL = {
  sky:    ['#5AD6FF','#789CFF','#FF5A6E','#7C5CFF'],
  sunset: ['#FFC48C','#FF9678','#E84A56','#F08A34'],
  candy:  ['#FFB2DE','#D69EF8','#E85096','#965CDC'],
  grape:  ['#BAA4FA','#968CEB','#8A5CD8','#5468D6'],
  ocean:  ['#78D6F0','#60A8E8','#3884D6','#28B0B2'],
  lagoon: ['#80E8CE','#60CEB2','#2AB0A4','#46BE74'],
  meadow: ['#B0E48A','#78CE8C','#46B260','#96C436'],
  berry:  ['#E094E0','#BA78E0','#D6488C','#9654C4'],
  flame:  ['#FFB278','#FF8A6E','#E4424E','#F0B036'],
  coral:  ['#FFBAB0','#FF96A0','#EC5678','#F47C60'],
};
const GOLD = '#FFD140', NAVY = '#1C285C';
const rgba = (hex, a) => { const n = parseInt(hex.slice(1),16); return `rgba(${(n>>16)&255},${(n>>8)&255},${n&255},${a})`; };

function dotsBg() {
  let o = '<div style="position:absolute;inset:0;overflow:hidden;opacity:.10">';
  for (let r=0;r<13;r++) for (let c=0;c<8;c++)
    o += `<div style="position:absolute;left:${c*150+(r%2?75:0)}px;top:${r*150}px;width:34px;height:34px;border-radius:50%;background:#fff"></div>`;
  return o + '</div>';
}

// A stacked wide panel: art centred on top, label below, %+bar revealed at bottom.
const panel = (id, img, label, accent, top, fit) => `
  <div class="pc" id="${id}" style="top:${top}px">
    <div class="crown" id="${id}crown">👑</div>
    <div class="ribbon" id="${id}rib">WINNER</div>
    <div class="pcin" style="background:${accent}">
      <img class="pcimg" src="${img}" style="object-fit:${fit||'cover'};${fit==='contain'?'background:#fff;padding:16px;':''}">
      <div class="pclabel">${esc(label)}</div>
      <div class="pcrow" id="${id}row">
        <div class="pcpct" id="${id}pct">0%</div>
        <div class="pcbar"><div class="pcfill" id="${id}fill" style="width:0%"></div></div>
      </div>
    </div>
  </div>`;

function build(Q) {
  const P = PAL[Q.pal] || PAL.sky;
  const [BGT, BGB, ACOL, BCOL] = P;
  const IA = b64(Q.imgA), IB = b64(Q.imgB);
  const GLOWA = `0 0 0 9px ${ACOL},0 0 44px 8px ${rgba(ACOL,.7)},0 30px 54px rgba(0,0,0,.35)`;
  const GLOWB = `0 0 0 9px ${BCOL},0 0 44px 8px ${rgba(BCOL,.7)},0 30px 54px rgba(0,0,0,.35)`;
  return `<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{font-family:'Anton';src:url('${ANTON}') format('truetype')}
*{margin:0;padding:0;box-sizing:border-box}html,body{width:1080px;height:1920px;background:#000}
.stage{width:1080px;height:1920px;position:relative;overflow:hidden;font-family:'Anton',sans-serif;
  background:linear-gradient(180deg,${BGT} 0%,${BGB} 100%)}
.head{position:absolute;top:60px;left:50%;transform:translateX(-50%);text-align:center;z-index:8;width:1000px}
.head .t{font-family:'Anton';font-size:112px;line-height:.92;color:#fff;letter-spacing:1px;-webkit-text-stroke:9px ${NAVY};paint-order:stroke fill}
.head .badge{display:inline-block;margin-top:12px;background:${ACOL};border:6px solid #fff;border-radius:44px;padding:4px 40px 10px;font-family:'Anton';font-size:42px;letter-spacing:3px;color:#fff;box-shadow:0 8px 18px rgba(0,0,0,.22)}
.pc{position:absolute;left:96px;width:888px;height:560px;border:12px solid #fff;border-radius:46px;
  transform-origin:50% 50%;box-shadow:0 22px 40px rgba(0,0,0,.3);will-change:transform}
/* the clip lives on the INNER wrapper so long labels get clipped but the crown
   and WINNER pill (which overhang the top of the panel) never do */
.pcin{position:absolute;inset:0;border-radius:34px;overflow:hidden;display:flex;flex-direction:column;
  align-items:center;padding:24px 30px 30px}
.pcimg{width:286px;height:286px;border-radius:28px;object-fit:cover;box-shadow:0 10px 20px rgba(0,0,0,.22);flex:none}
.pclabel{font-family:'Anton';font-size:58px;color:#fff;text-align:center;line-height:1.02;letter-spacing:.5px;margin-top:16px;
  text-shadow:0 5px 0 ${NAVY},0 7px 12px rgba(0,0,0,.28)}
.pcrow{margin-top:auto;width:100%;display:flex;align-items:center;gap:20px;opacity:0}
.pcpct{font-family:'Anton';font-size:82px;color:#fff;-webkit-text-stroke:4px ${NAVY};paint-order:stroke fill;min-width:184px;text-align:left}
.pcbar{flex:1;height:52px;border-radius:26px;background:rgba(255,255,255,.55);overflow:hidden;border:5px solid #fff}
.pcfill{height:100%;border-radius:24px;background:${GOLD};width:0%}
.crown{position:absolute;top:-104px;left:50%;transform:translateX(-50%) rotate(-8deg);font-size:100px;z-index:9;filter:drop-shadow(0 8px 12px rgba(0,0,0,.35));opacity:0}
.ribbon{position:absolute;top:-28px;right:44px;transform:scale(.6);font-family:'Anton';font-size:38px;padding:8px 40px;border-radius:999px;letter-spacing:2px;background:${GOLD};color:${NAVY};box-shadow:0 8px 16px rgba(0,0,0,.3);z-index:7;white-space:nowrap;border:5px solid #fff;opacity:0}
#count{position:absolute;top:960px;left:50%;transform:translate(-50%,-50%);width:196px;height:196px;border-radius:50%;background:rgba(255,255,255,.9);border:10px solid ${GOLD};display:flex;align-items:center;justify-content:center;z-index:10;opacity:0;box-shadow:0 12px 26px rgba(0,0,0,.3)}
#count span{font-family:'Anton';font-size:150px;color:${NAVY};line-height:1}
.foot{position:absolute;bottom:52px;width:100%;text-align:center;z-index:6}
.foot span{font-family:'Anton';font-size:54px;color:#fff;letter-spacing:1px;text-shadow:0 5px 0 ${NAVY},0 7px 12px rgba(0,0,0,.28)}
</style></head><body><div class="stage">
  ${dotsBg()}
  <div class="head"><div class="t">${esc(Q.head)}</div><div class="badge" id="sub">${esc(Q.sub)}</div></div>
  ${panel('A', IA, Q.la, ACOL, 340, Q.fitA)}
  ${panel('B', IB, Q.lb, BCOL, 1020, Q.fitB)}
  <div id="count"><span>3</span></div>
  <div class="foot"><span>COMMENT YOUR PICK 👇</span></div>
</div>
<script>
const WIN=${JSON.stringify(Q.win)}, PA=${Q.pa}, PB=${Q.pb};
const GLOW={A:${JSON.stringify(GLOWA)}, B:${JSON.stringify(GLOWB)}};
const BASE='0 22px 40px rgba(0,0,0,.3)';
const el=id=>document.getElementById(id);
const parts={
  A:{card:el('A'),crown:el('Acrown'),rib:el('Arib'),fill:el('Afill'),row:el('Arow'),pct:el('Apct'),pctVal:PA,ph:0},
  B:{card:el('B'),crown:el('Bcrown'),rib:el('Brib'),fill:el('Bfill'),row:el('Brow'),pct:el('Bpct'),pctVal:PB,ph:1.1},
};
const countEl=el('count'),countN=countEl.querySelector('span'),sub=el('sub');
const SUB0=${JSON.stringify(Q.sub)};
const VOTE_END=${(Q.vl||1.8).toFixed(2)},STEP=0.55,REVEAL=VOTE_END+3*STEP,beats=[VOTE_END,VOTE_END+STEP,VOTE_END+2*STEP];
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const ease=x=>x<0?0:x>1?1:(1-Math.cos(Math.PI*x))/2;
const easeOut=x=>x<0?0:x>1?1:1-Math.pow(1-x,3);
const backOut=x=>{if(x<=0)return 0;if(x>=1)return 1;const c1=1.1,c3=c1+1;return 1+c3*Math.pow(x-1,3)+c1*Math.pow(x-1,2);};
// per-beat punch impulse (a little scale kick when each countdown number lands)
function punch(t){let s=0;for(const bt of beats){if(t>=bt){const sb=t-bt;s+=0.06*Math.exp(-sb/0.14)*Math.cos(2*Math.PI*sb/0.34);}}return s;}

window.setT=function(t){
  const rv=easeOut(clamp((t-REVEAL)/0.55,0,1));
  const riseP=backOut(clamp((t-REVEAL)/0.6,0,1));
  const fillP=easeOut(clamp((t-REVEAL)/0.7,0,1));
  const pk=punch(t);
  const tj=t-REVEAL-0.06;
  const jelly=tj>0?Math.exp(-tj/0.19)*Math.sin(2*Math.PI*tj/0.27):0;

  for(const key of ['A','B']){
    const p=parts[key];
    const bob=Math.sin(2*Math.PI*t/2.6 + p.ph)*7;                 // idle vertical breathe
    const breathe=1+0.006*Math.sin(2*Math.PI*t/3.1 + p.ph);
    if(WIN===key){
      const ty=bob*(1-rv) + (-14)*riseP;                          // small LIFT, no collision
      const sc=(breathe*(1-riseP)+1.03*riseP)*(1+pk)*(1+0.028*jelly);
      const scY=(breathe*(1-riseP)+1.03*riseP)*(1+pk)*(1-0.028*jelly);
      p.card.style.transform='translateY('+ty.toFixed(1)+'px) scale('+sc.toFixed(3)+','+scY.toFixed(3)+')';
      p.card.style.boxShadow=rv>0?BASE+','+GLOW[key]:BASE;
      p.card.style.opacity='1'; p.card.style.zIndex=rv>0?5:3;
      const cr=ease(clamp((t-REVEAL-0.05)/0.4,0,1));
      p.crown.style.opacity=cr.toFixed(3);
      p.crown.style.transform='translateX(-50%) rotate(-8deg) translateY('+((1-cr)*-24).toFixed(1)+'px)';
      const rb=easeOut(clamp((t-REVEAL-0.12)/0.35,0,1));
      p.rib.style.opacity=rb.toFixed(3);
      p.rib.style.transform='scale('+(0.6+0.4*rb+0.08*Math.sin(rb*Math.PI)).toFixed(3)+')';
    } else {
      const sc=breathe*(1+pk);
      p.card.style.transform='translateY('+bob.toFixed(1)+'px) scale('+sc.toFixed(3)+')';
      p.card.style.boxShadow=BASE; p.card.style.opacity=(1-0.14*rv).toFixed(3); p.card.style.zIndex=2;
      p.crown.style.opacity='0'; p.rib.style.opacity='0';
    }
    p.fill.style.width=(p.pctVal*fillP).toFixed(1)+'%';
    p.pct.textContent=Math.round(p.pctVal*fillP)+'%';
    p.row.style.opacity=fillP.toFixed(3);
  }

  if(t>=VOTE_END && t<REVEAL){
    const idx=Math.min(2,Math.floor((t-VOTE_END)/STEP));
    const local=(t-VOTE_END-idx*STEP)/STEP;
    countN.textContent=String(3-idx);
    const pop=1.0+0.5*Math.exp(-local*9);
    const op=local<0.82?Math.min(1,local*8):(1-(local-0.82)/0.18);
    countEl.style.opacity=clamp(op,0,1).toFixed(3);
    countEl.style.transform='translate(-50%,-50%) scale('+pop.toFixed(3)+')';
  } else countEl.style.opacity='0';

  if(t<VOTE_END) sub.textContent=SUB0;
  else if(t<REVEAL) sub.textContent='LOCKING IN…';
  else sub.textContent='THE RESULTS';
};
window.setT(0);
</script></body></html>`;
}

rounds.forEach((q,i)=>{
  fs.writeFileSync(path.join(outdir,'round_'+i+'.html'), build(q));
  console.log('wrote round_'+i+'.html ('+q.pal+', win '+q.win+', vl '+(q.vl||1.8)+')');
});
