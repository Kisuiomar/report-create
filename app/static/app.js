/**
 * Octopus UI Logic & Multilingual Controller
 * Supports Russian (RU), English (EN), and Kazakh (KZ)
 */

// Toast notification system
function showToast(message, type = 'error', duration = 5000) {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  const icon = type === 'error' ? '❌' : type === 'success' ? '✅' : 'ℹ️';
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('toast-hide');
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

const I18N = {
  ru: {
    brand_title: "Автономное Досье & Связи",
    system_status: "Локальная LLM",
    online: "Подключена",
    offline: "Недоступна",
    hero_title: "Извлечение досье и родственных связей",
    hero_sub: "100% офлайн анализ документов произвольных форматов (PDF, DOCX, XLSX, HTML, JSON, TXT, сканы) с генерацией отчетов",
    drop_title: "Перетащите файлы сюда или выберите на диске",
    drop_sub: "Поддерживаются PDF (цифровые и сканы), Word, Excel, HTML, JSON, TXT, JPG, PNG",
    btn_browse: "Выбрать файлы",
    btn_start: "Начать извлечение досье",
    step_parse: "1. Парсинг файлов",
    step_clean: "2. Очистка и дедупликация",
    step_llm: "3. Анализ Qwen3.8-27B-Uncensored 262k",
    step_export: "4. Сборка отчетов",
    results_title: "Результаты анализа",
    tab_relatives: "Родственные связи",
    tab_employment: "Места работы",
    tab_contacts: "Контакты и адреса",
    tab_raw: "Очищенный текст",
    tab_json: "JSON структура",
    btn_dl_pdf: "Скачать PDF",
    btn_dl_docx: "Скачать Word",
    btn_dl_xlsx: "Скачать Excel",
    btn_dl_json: "Скачать JSON",
    col_fio: "ФИО лица",
    col_relation: "Степень связи",
    col_iin: "ИИН",
    col_shared: "Общие признаки (совпадения)",
    col_notes: "Примечания",
    col_company: "Организация",
    col_bin: "БИН/ИНН",
    col_position: "Должность",
    col_period: "Период",
    empty_relatives: "Родственные связи в предоставленных документах не выявлены.",
    empty_employment: "Сведения о работе не выявлены.",
    summary_title: "Сводные выводы аналитика:",
    tab_markdown: "Аналитический Отчет",
    or_paste_text: "Или вставьте скопированный текст / HTML:"
  },
  en: {
    brand_title: "Offline Dossier & Graph",
    system_status: "Local LLM",
    online: "Connected",
    offline: "Unreachable",
    hero_title: "Dossier & Kinship Intelligence",
    hero_sub: "100% air-gapped extraction from arbitrary documents (PDF, DOCX, XLSX, HTML, JSON, TXT, Scans) with multi-format reporting",
    drop_title: "Drag & drop files here or browse",
    drop_sub: "Supports PDF (native & scans), Word, Excel, HTML, JSON, TXT, JPG, PNG",
    btn_browse: "Select Files",
    btn_start: "Run Dossier Extraction",
    step_parse: "1. Parsing files",
    step_clean: "2. Cleaning & Deduplication",
    step_llm: "3. Qwen3.8-27B-Uncensored 262k Analysis",
    step_export: "4. Report Generation",
    results_title: "Intelligence Results",
    tab_relatives: "Family & Affiliates",
    tab_employment: "Employment",
    tab_contacts: "Contacts & Addresses",
    tab_raw: "Cleaned Text",
    tab_json: "JSON Data",
    btn_dl_pdf: "Download PDF",
    btn_dl_docx: "Download Word",
    btn_dl_xlsx: "Download Excel",
    btn_dl_json: "Download JSON",
    col_fio: "Full Name",
    col_relation: "Relation Type",
    col_iin: "Tax ID / IIN",
    col_shared: "Shared Attributes",
    col_notes: "Notes",
    col_company: "Organization",
    col_bin: "BIN / TIN",
    col_position: "Role",
    col_period: "Period",
    empty_relatives: "No kinship relations found in the provided documents.",
    empty_employment: "No employment records found.",
    summary_title: "Executive Summary:",
    tab_markdown: "Analytical Report",
    or_paste_text: "Or paste copied text / HTML:"
  },
  kz: {
    brand_title: "Дербес Досье & Байланыстар",
    system_status: "Жергілікті LLM",
    online: "Қосылған",
    offline: "Қолжетімсіз",
    hero_title: "Досье мен туыстық байланыстарды талдау",
    hero_sub: "Кез келген құжаттардан (PDF, DOCX, XLSX, HTML, JSON, TXT, сканерленген суреттер) толық оффлайн ақпарат алу және есептер жасау",
    drop_title: "Файлдарды осында сүйреңіз немесе таңдаңыз",
    drop_sub: "PDF (сандық және скан), Word, Excel, HTML, JSON, TXT, JPG, PNG қолданады",
    btn_browse: "Файлдарды таңдау",
    btn_start: "Досьені қалыптастыру",
    step_parse: "1. Құжаттарды оқу",
    step_clean: "2. Тазарту және қысу",
    step_llm: "3. Qwen3.8-27B-Uncensored 262k талдауы",
    step_export: "4. Есептерді жасау",
    results_title: "Талдау нәтижелері",
    tab_relatives: "Туыстық байланыстар",
    tab_employment: "Жұмыс орындары",
    tab_contacts: "Байланыстар мен мекенжайлар",
    tab_raw: "Тазартылған мәтін",
    tab_json: "JSON құрылымы",
    btn_dl_pdf: "PDF жүктеу",
    btn_dl_docx: "Word жүктеу",
    btn_dl_xlsx: "Excel жүктеу",
    btn_dl_json: "JSON жүктеу",
    col_fio: "Аты-жөні",
    col_relation: "Байланыс түрі",
    col_iin: "ЖСН / ИИН",
    col_shared: "Ортақ белгілер",
    col_notes: "Ескертпелер",
    col_company: "Ұйым / Мекеме",
    col_bin: "БСН / БИН",
    col_position: "Қызметі",
    col_period: "Мерзімі",
    empty_relatives: "Берілген құжаттардан туыстық байланыстар анықталмады.",
    empty_employment: "Жұмыс орны туралы мәліметтер анықталмады.",
    summary_title: "Сарапшының жиынтық қорытындысы:",
    tab_markdown: "Аналитикалық есеп",
    or_paste_text: "Немесе көшірілген мәтінді / HTML енгізіңіз:"
  }
};

let currentLang = 'ru';
let selectedFiles = [];
let lastResult = null;

function setLanguage(lang) {
  currentLang = lang;
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (I18N[lang] && I18N[lang][key]) {
      el.textContent = I18N[lang][key];
    }
  });
}

// Check local LLM status
async function checkLLMStatus() {
  const dot = document.getElementById('status-dot');
  const txt = document.getElementById('status-text');
  try {
    const res = await fetch('/api/health');
    const data = await res.json();
    if (data.llm_status && data.llm_status.status === 'ok') {
      dot.className = 'status-dot';
      txt.textContent = `${I18N[currentLang].online} (${data.llm_status.provider}: ${data.llm_model})`;
    } else {
      dot.className = 'status-dot offline';
      txt.textContent = `${I18N[currentLang].offline} (${data.llm_base_url})`;
    }
  } catch (e) {
    dot.className = 'status-dot offline';
    txt.textContent = I18N[currentLang].offline;
  }
}

// UI Initializer
document.addEventListener('DOMContentLoaded', () => {
  const langSelect = document.getElementById('lang-select');
  langSelect.addEventListener('change', (e) => setLanguage(e.target.value));

  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('file-input');
  const btnBrowse = document.getElementById('btn-browse');
  const btnStart = document.getElementById('btn-start');
  const filesList = document.getElementById('selected-files');
  const rawTextInput = document.getElementById('raw-text-input');

  function updateStartButton() {
    const hasFiles = selectedFiles.length > 0;
    const hasText = rawTextInput && rawTextInput.value.trim().length > 0;
    btnStart.style.display = (hasFiles || hasText) ? 'inline-flex' : 'none';
  }

  if (rawTextInput) {
    rawTextInput.addEventListener('input', updateStartButton);
  }

  btnBrowse.addEventListener('click', (e) => {
    e.stopPropagation();
    fileInput.click();
  });

  dropzone.addEventListener('click', () => fileInput.click());

  ['dragenter', 'dragover'].forEach(name => {
    dropzone.addEventListener(name, (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(name => {
    dropzone.addEventListener(name, (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
    });
  });

  dropzone.addEventListener('drop', (e) => {
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFiles(Array.from(e.dataTransfer.files));
    }
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files && fileInput.files.length > 0) {
      handleFiles(Array.from(fileInput.files));
    }
  });

  function handleFiles(files) {
    selectedFiles = files;
    filesList.innerHTML = '';
    files.forEach(f => {
      const chip = document.createElement('div');
      chip.className = 'file-chip';
      chip.innerHTML = `<span>📄 <b>${f.name}</b> (${(f.size / 1024).toFixed(1)} KB)</span><span style="color:var(--text-dim);">${f.type || 'auto'}</span>`;
      filesList.appendChild(chip);
    });
    updateStartButton();
  }

  // Processing pipeline execution
  btnStart.addEventListener('click', async () => {
    const textContent = rawTextInput ? rawTextInput.value.trim() : '';
    if (selectedFiles.length === 0 && textContent.length === 0) return;

    const progressBox = document.getElementById('pipeline-progress');
    const resultsBox = document.getElementById('results-section');
    progressBox.style.display = 'block';
    resultsBox.style.display = 'none';
    btnStart.disabled = true;

    // Show spinner on button
    btnStart.innerHTML = `<span class="processing-spinner"><span class="spinner-ring"></span>Обработка...</span>`;

    // Animate steps
    const step1 = document.getElementById('step-1');
    const step2 = document.getElementById('step-2');
    const step3 = document.getElementById('step-3');
    const step4 = document.getElementById('step-4');

    step1.className = 'step-item active';
    step2.className = 'step-item';
    step3.className = 'step-item';
    step4.className = 'step-item';

    const formData = new FormData();
    selectedFiles.forEach(f => formData.append('files', f));
    
    if (textContent.length > 0) {
      const blob = new Blob([textContent], { type: 'text/plain' });
      formData.append('files', blob, 'pasted_text.txt');
    }

    const logConsole = document.getElementById('log-console');
    logConsole.style.display = 'block';
    logConsole.innerHTML = '<div>> Соединение с сервером...</div>';

    try {
      const response = await fetch('/api/process', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Processing failed');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let partialData = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value, { stream: true });
        partialData += chunk;
        
        const lines = partialData.split('\n\n');
        partialData = lines.pop(); // Оставляем незавершенную часть
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.substring(6);
            try {
              const data = JSON.parse(dataStr);
              if (data.type === 'status') {
                 const prog = data.progress ? ` <span style="color:var(--accent-blue);">[${data.progress}%]</span>` : '';
                 logConsole.innerHTML += `<div>> ${data.message}${prog}</div>`;
                 logConsole.scrollTop = logConsole.scrollHeight;
                 
                 // Обновляем UI шагов
                 if (data.message.includes("Очистка")) {
                    step1.className = 'step-item done'; step2.className = 'step-item active';
                 } else if (data.message.includes("Структурирование") || data.message.includes("Генерация")) {
                    step2.className = 'step-item done'; step3.className = 'step-item active';
                 } else if (data.message.includes("Сборка")) {
                    step3.className = 'step-item done'; step4.className = 'step-item active';
                 }

              } else if (data.type === 'result') {
                 lastResult = data.data;
              } else if (data.type === 'error') {
                 throw new Error(data.message);
              }
            } catch (e) {
              if (e.message !== "Unexpected end of JSON input") {
                 throw e;
              }
            }
          }
        }
      }

      // Process any leftover complete messages
      if (partialData && partialData.startsWith('data: ')) {
         const dataStr = partialData.substring(6);
         try {
            const data = JSON.parse(dataStr);
            if (data.type === 'error') throw new Error(data.message);
         } catch(e) {
            if (e.message !== "Unexpected end of JSON input") {
                 throw e;
            }
         }
      }

      if (!lastResult) {
          throw new Error("Не удалось получить результат. Возможно, сервер вернул пустой ответ.");
      }

      step4.className = 'step-item done';

      setTimeout(() => {
        renderResults(lastResult);
        resultsBox.style.display = 'block';
        resultsBox.scrollIntoView({ behavior: 'smooth' });
        btnStart.disabled = false;
        btnStart.innerHTML = `⚡ ${I18N[currentLang].btn_start}`;
        showToast('Досье успешно сформировано!', 'success', 4000);
      }, 500);

    } catch (err) {
      showToast(`Ошибка обработки: ${err.message}`, 'error', 8000);
      btnStart.disabled = false;
      btnStart.innerHTML = `⚡ ${I18N[currentLang].btn_start}`;
    }
  });

  // Tab navigation
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(btn.getAttribute('data-target')).classList.add('active');
    });
  });

  checkLLMStatus();
  setInterval(checkLLMStatus, 15000);
});

function renderResults(data) {
  const d = data.dossier;

  // Banner
  document.getElementById('subject-name').textContent = d.subject.full_name || 'Не указано';
  document.getElementById('subject-iin').textContent = `ИИН: ${d.subject.iin || '—'}`;
  document.getElementById('subject-birth').textContent = `Дата рожд.: ${d.subject.birth_date || '—'}`;
  document.getElementById('subject-citizenship').textContent = `Гражданство: ${d.subject.citizenship || '—'}`;
  document.getElementById('summary-text').textContent = d.executive_summary || '';

  // Render Markdown Report
  if (data.markdown_report && typeof marked !== 'undefined') {
    document.getElementById('markdown-preview').innerHTML = marked.parse(data.markdown_report);
  } else {
    document.getElementById('markdown-preview').innerHTML = "<p style='color:red;'>Markdown report not generated or marked.js missing.</p>";
  }

  // Relatives table
  const relTbody = document.getElementById('relatives-tbody');
  relTbody.innerHTML = '';
  if (d.relatives_and_affiliates && d.relatives_and_affiliates.length > 0) {
    d.relatives_and_affiliates.forEach(r => {
      const tr = document.createElement('tr');
      const sharedHtml = r.shared_attributes && r.shared_attributes.length > 0
        ? r.shared_attributes.map(s => `<span class="badge-shared">🔗 ${s}</span>`).join(' ')
        : '—';

      tr.innerHTML = `
        <td><b>${r.full_name}</b></td>
        <td>${r.relation_type}</td>
        <td><code>${r.iin || '—'}</code></td>
        <td>${sharedHtml}</td>
        <td style="color:var(--text-muted);">${r.notes || '—'}</td>
      `;
      relTbody.appendChild(tr);
    });
  } else {
    relTbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--text-dim);">${I18N[currentLang].empty_relatives}</td></tr>`;
  }

  // Employment table
  const empTbody = document.getElementById('employment-tbody');
  empTbody.innerHTML = '';
  if (d.employment_history && d.employment_history.length > 0) {
    d.employment_history.forEach(e => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><b>${e.organization}</b></td>
        <td><code>${e.bin || '—'}</code></td>
        <td>${e.position || '—'}</td>
        <td>${e.period || '—'}</td>
      `;
      empTbody.appendChild(tr);
    });
  } else {
    empTbody.innerHTML = `<tr><td colspan="4" style="text-align:center;color:var(--text-dim);">${I18N[currentLang].empty_employment}</td></tr>`;
  }

  // Contacts
  const phones = (d.contacts.phone_numbers || []).join(', ') || 'Не выявлены';
  const emails = (d.contacts.emails || []).join(', ') || 'Не выявлены';
  const socials = (d.contacts.social_profiles || []).join(', ') || 'Не выявлены';
  const addrs = (d.addresses || []).map(a => `<li><b>[${a.address_type}]</b> ${a.full_address}</li>`).join('') || '<li>Не выявлены</li>';

  document.getElementById('contacts-content').innerHTML = `
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 20px;">
      <div class="glass-panel" style="padding:16px;">
        <h3 style="margin-bottom:12px;color:var(--accent-blue);">📞 Средства связи</h3>
        <p><b>Телефоны:</b> ${phones}</p>
        <p style="margin-top:6px;"><b>Email:</b> ${emails}</p>
        <p style="margin-top:6px;"><b>Соцсети:</b> ${socials}</p>
      </div>
      <div class="glass-panel" style="padding:16px;">
        <h3 style="margin-bottom:12px;color:var(--accent-blue);">📍 Выявленные адреса</h3>
        <ul style="padding-left:18px;line-height:1.8;">${addrs}</ul>
      </div>
    </div>
  `;

  // Raw & JSON
  document.getElementById('raw-text-preview').textContent = data.raw_cleaned_text || '';
  document.getElementById('json-preview').textContent = JSON.stringify(data.dossier, null, 2);

  // Setup download buttons
  setupDownloadBtn('btn-dl-pdf', data.generated_files.pdf);
  setupDownloadBtn('btn-dl-docx', data.generated_files.docx);
  setupDownloadBtn('btn-dl-xlsx', data.generated_files.xlsx);
  setupDownloadBtn('btn-dl-json', data.generated_files.json);
}

function setupDownloadBtn(elemId, filePath) {
  const btn = document.getElementById(elemId);
  if (!filePath) {
    btn.style.display = 'none';
    return;
  }
  btn.style.display = 'inline-flex';
  const filename = filePath.split(/[/\\]/).pop();
  btn.onclick = () => {
    window.location.href = `/api/download/${filename}`;
  };
}
