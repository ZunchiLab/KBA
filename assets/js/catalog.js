(() => {
  const cards = [...document.querySelectorAll('.report-card')];
  const search = document.querySelector('#search');
  const month = document.querySelector('#month');
  const versions = document.querySelector('#show-versions');
  const buttons = [...document.querySelectorAll('[data-category-filter]')];
  let category = 'all';
  const normalize = value => value.normalize('NFKC').toLocaleLowerCase('ja').replace(/[\s._/-]+/g, '');

  function render() {
    const query = normalize(search.value);
    let visible = 0;
    cards.forEach(card => {
      const matches = (category === 'all' || card.dataset.category === category)
        && (month.value === 'all' || card.dataset.month === month.value)
        && (versions.checked || card.dataset.superseded !== 'true')
        && (!query || normalize(card.dataset.search).includes(query));
      card.hidden = !matches;
      if (matches) visible++;
    });
    document.querySelector('#visible-count').textContent = visible;
    document.querySelector('#empty').hidden = visible !== 0;
  }

  search.addEventListener('input', render);
  month.addEventListener('change', render);
  versions.addEventListener('change', render);
  buttons.forEach(button => button.addEventListener('click', () => {
    category = button.dataset.categoryFilter;
    buttons.forEach(item => item.setAttribute('aria-pressed', String(item === button)));
    render();
  }));
  document.querySelector('#reset').addEventListener('click', () => {
    search.value = '';
    month.value = 'all';
    versions.checked = false;
    category = 'all';
    buttons.forEach(item => item.setAttribute('aria-pressed', String(item.dataset.categoryFilter === 'all')));
    render();
    search.focus();
  });
  render();
})();
