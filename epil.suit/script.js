// Клик по кнопкам "Записаться" — подставляем зону в форму
document.addEventListener('click', (e)=>{
  const btn = e.target.closest('[data-goto]');
  if(!btn) return;
  const target = document.querySelector(btn.dataset.goto);
  if(btn.dataset.service){
    const svc = document.getElementById('service-input');
    if (svc) svc.value = btn.dataset.service;
  }
  if(target){
    const y = target.getBoundingClientRect().top + window.pageYOffset - 70;
    window.scrollTo({top:y, behavior:'smooth'});
  }
});

// UTM из URL
const params = new URLSearchParams(location.search);
const utmKeys = ['utm_source','utm_medium','utm_campaign','utm_term','utm_content'];
const utm = utmKeys.map(k => params.get(k) ? `${k}=${params.get(k)}` : '').filter(Boolean).join('&');
const utmField = document.getElementById('utm'); if (utmField) utmField.value = utm;

// Отправка формы в n8n/бота
document.getElementById('lead-form')?.addEventListener('submit', async (e)=>{
  e.preventDefault();
  const form = e.currentTarget;
  const msg = form.querySelector('.form-msg');
  msg.textContent = 'Отправляем...';

  const data = Object.fromEntries(new FormData(form).entries());
  if(!data.phone || String(data.phone).trim().length < 6){
    msg.textContent = 'Укажи корректный телефон';
    return;
  }

  try{
    const resp = await fetch('https://YOUR_N8N_WEBHOOK_URL', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        source: 'epil-landing',
        ts: new Date().toISOString(),
        ...data
      })
    });
    if(!resp.ok) throw new Error('Network');
    msg.textContent = 'Заявка отправлена. Перезвоним в ближайшее время.';
    form.reset();
  }catch(err){
    msg.textContent = 'Сервер недоступен. Попробуй позже.';
  }
});
