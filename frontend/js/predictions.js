/**
 * SwasthAI — Health risk assessments hub.
 * Lists the signed-in user's saved assessment results (newest first) with
 * a filter, paging and delete. Results come from GET /predict/history.
 */
(() => {
  const PAGE_SIZE = 8;
  const state = { filter: '', page: 1, total: 0 };

  const list = document.getElementById('historyList');
  const pager = document.getElementById('historyPager');
  const count = document.getElementById('historyCount');
  const prev = document.getElementById('historyPrev');
  const next = document.getElementById('historyNext');
  if (!list) return;

  function renderEmpty() {
    const filtered = Boolean(state.filter);
    list.innerHTML = AppUI.state({
      icon: 'fa-chart-line',
      title: filtered ? 'No saved results of this type' : 'No saved results yet',
      text: filtered
        ? 'Try another filter, or run this assessment to see it here.'
        : 'Complete an assessment above and your result will be saved here.'
    });
    pager.hidden = true;
  }

  async function load() {
    list.innerHTML = AppUI.skeletonRows(4);
    try {
      const data = await SwasthAPI.predictions.history({
        assessment: state.filter,
        page: state.page,
        page_size: PAGE_SIZE
      });
      state.total = data.total;

      // Deleting the last row of a page: step back one page.
      if (!data.items.length && state.page > 1) {
        state.page -= 1;
        return load();
      }
      if (!data.items.length) return renderEmpty();

      list.innerHTML = `<ul class="rows">${data.items.map((item) => `
        ${AppUI.predictionRow(item, { withDelete: true })}
        ${item.message ? `<li class="row-item" style="padding-top:0; border-top:none; margin-top:-1px;"><span style="width:40px; flex-shrink:0;"></span><p class="row-item__meta" style="margin:0;">${AppUI.esc(item.message)} ${followUpLink(item)}</p></li>` : ''}`).join('')}</ul>`;

      const first = (state.page - 1) * PAGE_SIZE + 1;
      const last = first + data.items.length - 1;
      count.textContent = `Showing ${first} to ${last} of ${data.total}`;
      prev.disabled = state.page === 1;
      next.disabled = last >= data.total;
      pager.hidden = data.total <= PAGE_SIZE;
    } catch (err) {
      list.innerHTML = AppUI.errorState(AppUI.errorText(err), 'historyRetry');
      pager.hidden = true;
      document.getElementById('historyRetry')?.addEventListener('click', load);
    }
  }

  function followUpLink(item) {
    const info = AppUI.assessmentInfo(item.assessment);
    if (!item.is_elevated || !info.specialty) return '';
    return `<a class="panel__link" href="doctors.html?specialty=${encodeURIComponent(info.specialty)}&from=${encodeURIComponent(item.assessment)}">Find a specialist</a>`;
  }

  document.querySelectorAll('.tabs__btn[data-filter]').forEach((button) => {
    button.addEventListener('click', () => {
      document.querySelectorAll('.tabs__btn[data-filter]').forEach((b) => b.setAttribute('aria-pressed', String(b === button)));
      state.filter = button.dataset.filter;
      state.page = 1;
      load();
    });
  });

  prev.addEventListener('click', () => { state.page -= 1; load(); });
  next.addEventListener('click', () => { state.page += 1; load(); });

  list.addEventListener('click', async (e) => {
    const button = e.target.closest('[data-action="delete-result"]');
    if (!button) return;
    const row = button.closest('[data-id]');
    const confirmed = await AppUI.confirm({
      title: 'Delete this saved result?',
      text: 'It will be removed from your account permanently. This cannot be undone.',
      confirmLabel: 'Delete result',
      danger: true
    });
    if (!confirmed) return;
    try {
      await SwasthAPI.predictions.deleteHistory(row.dataset.id);
      AppUI.toast('Saved result deleted');
      load();
    } catch (err) {
      AppUI.toast(AppUI.errorText(err), 'error');
    }
  });

  load();
})();
