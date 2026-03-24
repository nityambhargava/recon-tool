const dropZone  = document.getElementById('dropZone');
const fileInput  = document.getElementById('fileInput');
const fileList   = document.getElementById('fileList');
const submitBtn  = document.getElementById('submitBtn');
const dropTitle  = document.getElementById('dropTitle');

function formatBytes(b) {
  if (b < 1024) return b + ' B';
  if (b < 1024 * 1024) return (b / 1024).toFixed(1) + ' KB';
  return (b / (1024 * 1024)).toFixed(1) + ' MB';
}

function isZip(name) {
  return name.toLowerCase().endsWith('.zip');
}

function renderFileList(files) {
  fileList.innerHTML = '';
  if (!files || files.length === 0) {
    submitBtn.disabled = true;
    dropTitle.textContent = 'Drag & drop your files here';
    return;
  }

  Array.from(files).forEach(file => {
    const item = document.createElement('div');
    item.className = 'file-list-item';
    const ext = isZip(file.name) ? 'ZIP' : 'TXT';
    const badgeCls = isZip(file.name) ? 'file-list-badge zip' : 'file-list-badge';
    item.innerHTML = `
      <span class="file-list-icon">
        <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
          <path d="M3 1h7l3 3v10a1 1 0 01-1 1H3a1 1 0 01-1-1V2a1 1 0 011-1z"
                stroke="currentColor" stroke-width="1.2"/>
          <path d="M10 1v3h3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
        </svg>
      </span>
      <span class="file-list-name">${file.name}</span>
      <span class="file-list-size">${formatBytes(file.size)}</span>
      <span class="${badgeCls}">${ext}</span>
    `;
    fileList.appendChild(item);
  });

  const n = files.length;
  dropTitle.textContent = n === 1 ? `1 file selected` : `${n} files selected`;
  submitBtn.disabled = false;
}

fileInput.addEventListener('change', () => renderFileList(fileInput.files));

// Drag and drop
dropZone.addEventListener('dragover', e => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const dt = new DataTransfer();
  Array.from(e.dataTransfer.files).forEach(f => dt.items.add(f));
  fileInput.files = dt.files;
  renderFileList(fileInput.files);
});
