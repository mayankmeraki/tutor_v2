/**
 * Shared AnimHelper + beat runner for animation tests.
 * Include this + p5.js before the test script.
 */

// ── AnimHelper (same as animation-helpers.js) ──
class AnimHelper {
  constructor(p, W, H) {
    this.p = p; this.W = W; this.H = H;
    this.state = {}; this._targets = {}; this._t = 0; this._speed = 3;
    this.colors = {
      bg:[10,14,26], text:[241,245,249], textMuted:[148,163,184],
      accent:[59,130,246], accentAlt:[52,211,153], warm:[251,191,36],
      danger:[239,68,68], purple:[167,139,250], pink:[244,114,182], cyan:[56,189,248],
    };
  }
  init(d){for(const[k,v]of Object.entries(d)){this.state[k]=v;this._targets[k]=v;} this._defaults={...d};}
  animateTo(k,v,s){this._targets[k]=v;if(s!==undefined)this._speed=s;}
  set(k,v){this.state[k]=v;this._targets[k]=v;}
  _onControl(p){if(p.action==='set')this.animateTo(p.param,p.value,p.speed);else if(p.action==='instant')this.set(p.param,p.value);else if(p.action==='reset'){for(const k in this._defaults){this.state[k]=this._defaults[k];this._targets[k]=this._defaults[k];}}}
  tick(){const dt=Math.min(this.p.deltaTime/1000,0.05);this._t+=dt;for(const k in this._targets){const c=this.state[k],t=this._targets[k];if(typeof c==='number'&&typeof t==='number')this.state[k]=c+(t-c)*Math.min(1,dt*this._speed);else this.state[k]=t;}}
  clear(){this.p.background(10,14,26);}
  grid(sp=40,a=10){const p=this.p;p.stroke(148,163,184,a);p.strokeWeight(0.5);for(let x=0;x<this.W;x+=sp)p.line(x,0,x,this.H);for(let y=0;y<this.H;y+=sp)p.line(0,y,this.W,y);}
  glow(x,y,r,c,int=0.3){const p=this.p,[cr,cg,cb]=c;p.noStroke();for(let i=4;i>0;i--){p.fill(cr,cg,cb,int*255/(i*2));p.ellipse(x,y,r*(1+i*0.5));}p.fill(cr,cg,cb);p.ellipse(x,y,r);}
  label(x,y,t,c,s=12,bold=true){const p=this.p,[cr,cg,cb]=c||this.colors.text;p.fill(cr,cg,cb,200);p.noStroke();p.textAlign(p.CENTER,p.CENTER);p.textSize(s);if(bold)p.textStyle(p.BOLD);p.text(t,x,y);p.textStyle(p.NORMAL);}
  arrow(x1,y1,x2,y2,c,w=2){const p=this.p,[cr,cg,cb]=c;p.stroke(cr,cg,cb,180);p.strokeWeight(w);p.line(x1,y1,x2,y2);const a=Math.atan2(y2-y1,x2-x1);p.fill(cr,cg,cb,180);p.noStroke();p.triangle(x2,y2,x2-8*Math.cos(a-0.4),y2-8*Math.sin(a-0.4),x2-8*Math.cos(a+0.4),y2-8*Math.sin(a+0.4));}
  dashed(x1,y1,x2,y2,c,dl=6,gl=4){const p=this.p,[cr,cg,cb]=c;p.stroke(cr,cg,cb,80);p.strokeWeight(1);p.drawingContext.setLineDash([dl,gl]);p.line(x1,y1,x2,y2);p.drawingContext.setLineDash([]);}
  curve(pts,c,w=2,a=1){if(pts.length<2)return;const p=this.p,[cr,cg,cb]=c;p.stroke(cr,cg,cb,a*255);p.strokeWeight(w);p.noFill();p.beginShape();pts.forEach(([x,y])=>p.vertex(x,y));p.endShape();}
  filledCurve(pts,baseY,c,a=0.15){if(pts.length<2)return;const p=this.p,[cr,cg,cb]=c;p.fill(cr,cg,cb,a*255);p.noStroke();p.beginShape();p.vertex(pts[0][0],baseY);pts.forEach(([x,y])=>p.vertex(x,y));p.vertex(pts[pts.length-1][0],baseY);p.endShape(p.CLOSE);}
  equation(x,y,t,c){const p=this.p,[cr,cg,cb]=c||this.colors.accent;const w=Math.max(180,p.textWidth(t)+30);p.fill(10,14,26,230);p.stroke(cr,cg,cb,60);p.strokeWeight(1);p.rect(x-w/2,y-18,w,36,6);p.fill(cr,cg,cb);p.noStroke();p.textSize(14);p.textStyle(p.BOLD);p.textAlign(p.CENTER,p.CENTER);p.text(t,x,y);p.textStyle(p.NORMAL);}
  legend(items,x,y){const p=this.p,pad=10,lh=20,w=170,h=items.length*lh+pad*2;const lx=x??(this.W-w-12),ly=y??12;p.fill(10,14,26,230);p.stroke(148,163,184,30);p.strokeWeight(1);p.rect(lx,ly,w,h,8);items.forEach((it,i)=>{const ix=lx+pad,iy=ly+pad+i*lh+lh/2;const[cr,cg,cb]=it.color;p.fill(cr,cg,cb);p.noStroke();p.ellipse(ix+4,iy,8,8);p.fill(226,232,240,180);p.textSize(11);p.textAlign(p.LEFT,p.CENTER);p.text(it.label,ix+16,iy);});}
  nx(n){return n*this.W;} ny(n){return n*this.H;}
  osc(f=1,mn=0,mx=1){return mn+(mx-mn)*(0.5+0.5*Math.sin(this._t*f*Math.PI*2));}
  pulse(f=1){return 0.5+0.5*Math.sin(this._t*f*Math.PI*2);}
}
window.AnimHelper = AnimHelper;

// ── Beat runner ──
function initBeatRunner(beats, helperRef) {
  let current = -1;
  function exec(idx) {
    if (idx < 0 || idx >= beats.length) return;
    current = idx;
    document.querySelectorAll('.beat-btn').forEach((btn, i) => {
      btn.className = 'beat-btn' + (i === idx ? ' active' : i < idx ? ' done' : '');
    });
    document.getElementById('subtitle').innerHTML = beats[idx].say;
    beats[idx].fn();
  }
  document.querySelectorAll('.beat-btn').forEach(btn => { btn.onclick = () => exec(+btn.dataset.beat); });
  document.getElementById('auto-play').onclick = () => {
    if (helperRef()) helperRef()._onControl({ action: 'reset' });
    let i = 0;
    (function next() { if (i >= beats.length) return; exec(i++); setTimeout(next, 5500); })();
  };
}
