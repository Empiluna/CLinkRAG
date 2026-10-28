/* Load before styles to avoid a light flash; no network or account dependency. */
(() => {
  let theme = 'dark';
  try { if (localStorage.getItem('clinkrag-theme') === 'light') theme = 'light'; } catch {}
  document.documentElement.dataset.theme = theme;
})();
