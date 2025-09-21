const canvas = document.getElementById('bg');
if(canvas){
  const ctx = canvas.getContext('2d');
  const DPR = window.devicePixelRatio || 1;
  function resize(){
    canvas.width = innerWidth * DPR;
    canvas.height = innerHeight * DPR;
    ctx.setTransform(DPR,0,0,DPR,0,0);
  }
  resize(); addEventListener('resize', resize);

  const stars = Array.from({length: 120}).map(() => ({
    x: Math.random()*innerWidth,
    y: Math.random()*innerHeight,
    vx: (Math.random()-.5)*0.25,
    vy: (Math.random()-.5)*0.25,
    r: Math.random()*1.4+0.4
  }));

  function tick(){
    ctx.clearRect(0,0,innerWidth,innerHeight);
    ctx.fillStyle = 'rgba(255,255,255,0.9)';
    for(const s of stars){
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI*2);
      ctx.fill();
      s.x += s.vx; s.y += s.vy;
      if(s.x<0||s.x>innerWidth) s.vx*=-1;
      if(s.y<0||s.y>innerHeight) s.vy*=-1;
    }
    ctx.strokeStyle = 'rgba(255,30,66,0.20)';
    ctx.lineWidth = 1;
    for(let i=0;i<stars.length;i++){
      for(let j=i+1;j<stars.length;j++){
        const a = stars[i], b = stars[j];
        const dx = a.x-b.x, dy = a.y-b.y;
        const d2 = dx*dx + dy*dy;
        if(d2 < 160*160){
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
      }
    }
    requestAnimationFrame(tick);
  }
  tick();
}
