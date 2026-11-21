/* Load before styles to avoid a light flash; no network or account dependency. */
(() => {
  let theme = 'light';
  try { if (localStorage.getItem('clinkrag-theme') === 'dark') theme = 'dark'; } catch {}
  document.documentElement.dataset.theme = theme;
})();
