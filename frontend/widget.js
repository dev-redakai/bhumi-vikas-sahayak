/* Embeddable widget: <script src="https://HOST/widget.js" data-api-base="https://HOST"></script> */
(function () {
  var s = document.currentScript;
  var base = (s && s.getAttribute('data-api-base')) || (s && new URL(s.src).origin) || '';
  var btn = document.createElement('button');
  btn.textContent = 'भूमि विकास सहायक';
  btn.setAttribute('aria-label', 'Open Bhumi Vikas Sahayak');
  btn.style.cssText = 'position:fixed;right:20px;bottom:20px;z-index:2147483000;border:0;border-radius:999px;padding:12px 18px;color:#fff;font:600 14px Inter,system-ui,sans-serif;cursor:pointer;box-shadow:0 12px 30px -10px rgba(26,104,230,.7);background:linear-gradient(135deg,#1a68e6,#7c3aed 55%,#ff9f1c)';
  var frame = document.createElement('iframe');
  frame.src = base + '/?embed=1#/ask';
  frame.title = 'Bhumi Vikas Sahayak';
  frame.style.cssText = 'position:fixed;right:20px;bottom:76px;width:min(440px,calc(100vw - 40px));height:min(680px,calc(100vh - 110px));border:0;border-radius:18px;box-shadow:0 24px 60px -20px rgba(15,23,42,.45);z-index:2147483000;display:none;background:#fff';
  btn.onclick = function () { frame.style.display = frame.style.display === 'none' ? 'block' : 'none'; };
  document.body.appendChild(frame);
  document.body.appendChild(btn);
})();
