/**
 * algorithmic_art.js — Fondo procedural estático para Atlas Dashboard v3.
 * Se ejecuta UNA vez al DOMContentLoaded. No re-ejecuta en runtime.
 */
(function() {
  var canvas = document.getElementById('art-bg');
  if (!canvas) return;
  var ctx = canvas.getContext('2d');

  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    draw();
  }

  function draw() {
    var w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    // Fondo base
    ctx.fillStyle = '#0d1117';
    ctx.fillRect(0, 0, w, h);

    // Puntos dispersos (simula grafo de conocimiento)
    var points = [];
    var numPoints = Math.min(200, Math.floor((w * h) / 8000));
    for (var i = 0; i < numPoints; i++) {
      points.push({
        x: Math.random() * w,
        y: Math.random() * h,
        r: 0.5 + Math.random() * 1.5,
        alpha: 0.03 + Math.random() * 0.08
      });
    }

    // Líneas de conexión (distancia < threshold)
    var threshold = Math.min(w, h) * 0.12;
    ctx.lineWidth = 0.5;
    for (var i = 0; i < points.length; i++) {
      for (var j = i + 1; j < points.length; j++) {
        var dx = points[i].x - points[j].x;
        var dy = points[i].y - points[j].y;
        var dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < threshold) {
          var alpha = 0.02 * (1 - dist / threshold);
          ctx.strokeStyle = 'rgba(88, 166, 255, ' + alpha + ')';
          ctx.beginPath();
          ctx.moveTo(points[i].x, points[i].y);
          ctx.lineTo(points[j].x, points[j].y);
          ctx.stroke();
        }
      }
    }

    // Dibujar puntos
    for (var i = 0; i < points.length; i++) {
      var p = points[i];
      ctx.fillStyle = 'rgba(88, 166, 255, ' + p.alpha + ')';
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', resize);
  } else {
    resize();
  }
  window.addEventListener('resize', function() { resize(); });
})();
