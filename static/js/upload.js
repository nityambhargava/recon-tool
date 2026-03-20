const dropZone   = document.getElementById('dropZone');
const fileInput  = document.getElementById('fileInput');
const filePreview= document.getElementById('filePreview');
const fileName   = document.getElementById('fileName');
const fileSize   = document.getElementById('fileSize');
const fileClear  = document.getElementById('fileClear');
const submitBtn  = document.getElementById('submitBtn');
const dropTitle  = document.getElementById('dropTitle');

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function setFile(file) {
  if (!file) return;
  fileName.textContent = file.name;
  fileSize.textContent = formatBytes(file.size);
  filePreview.style.display = 'block';
  dropTitle.textContent = 'File selected';
  submitBtn.disabled = false;
}

function clearFile() {
  fileInput.value = '';
  filePreview.style.display = 'none';
  dropTitle.textContent = 'Drag & drop your file here';
  submitBtn.disabled = true;
}

fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) setFile(fileInput.files[0]);
});

fileClear.addEventListener('click', clearFile);

// Drag and drop
dropZone.addEventListener('dragover', e => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) {
    const dt = new DataTransfer();
    dt.items.add(file);
    fileInput.files = dt.files;
    setFile(file);
  }
});
