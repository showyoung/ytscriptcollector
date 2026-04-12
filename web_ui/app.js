// ---- 主题管理 ----
function _applyTheme() {
  const lightLink = document.getElementById('theme-light');
  const followSystem = document.getElementById('follow_system').checked;
  const darkMode = document.getElementById('dark_mode').checked;

  if (followSystem) {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    lightLink.disabled = prefersDark;
  } else {
    lightLink.disabled = darkMode;
  }
}

function onFollowSystemChange() {
  const followSystem = document.getElementById('follow_system').checked;
  document.getElementById('dark_mode').disabled = followSystem;
  _applyTheme();
}

function onDarkModeChange() {
  _applyTheme();
}

window.addEventListener('DOMContentLoaded', _applyTheme);
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
  if (document.getElementById('follow_system').checked) {
    _applyTheme();
  }
});

// ---- 填充 select ----
function populateSelect(id, options, defaultVal) {
  const sel = document.getElementById(id);
  sel.innerHTML = '';
  for (const opt of options) {
    const el = document.createElement('option');
    el.value = opt.value !== undefined ? opt.value : opt;
    el.textContent = opt.label !== undefined ? opt.label : String(opt);
    sel.appendChild(el);
  }
  if (defaultVal) sel.value = defaultVal;
}

// ---- 根据当前表单状态更新控件启用/禁用状态 ----
function _updateFormState() {
  const mt = document.getElementById('media_type').value;
  const srtChecked = document.getElementById('srt').checked;
  const mdChecked = document.getElementById('md').checked;
  const sepAudioChecked = document.getElementById('separate_audio').checked;

  if (mt === 'audio') {
    document.getElementById('code_convert').disabled = true;
    document.getElementById('separate_audio').disabled = true;
    document.getElementById('audio_format').disabled = false;
  } else {
    document.getElementById('code_convert').disabled = false;
    document.getElementById('separate_audio').disabled = false;
    document.getElementById('audio_format').disabled = !sepAudioChecked;
  }

  const whisperDisabled = !srtChecked && !mdChecked;
  document.getElementById('whisper_model').disabled = whisperDisabled;
}

// ---- 画质选项构建（previewVideo 和 updateQualityOptions 共用） ----
function _buildQualityOptions(qualitySel, formats, lastQuality, defaultQuality) {
  const mt = document.getElementById('media_type').value;
  qualitySel.innerHTML = '';
  document.getElementById('qualityNote').style.display = 'inline';

  if (mt === 'audio') {
    qualitySel.innerHTML = '<option value="audio">🎵 仅音频</option>';
    qualitySel.disabled = false;
    document.getElementById('qualityNote').style.display = 'none';
    return;
  }

  if (!formats || formats.length === 0) {
    qualitySel.innerHTML = '<option value="">-- 先预览视频 --</option>';
    return;
  }

  const availableHeights = [...formats]
    .filter(f => f.height)
    .reduce((acc, f) => { if (!acc.includes(f.height)) acc.push(f.height); return acc; }, [])
    .sort((a, b) => b - a);

  for (const h of availableHeights) {
    const opt = document.createElement('option');
    opt.value = h + 'p';
    opt.textContent = '📺 ' + h + 'p';
    qualitySel.appendChild(opt);
  }

  qualitySel.disabled = false;
  document.getElementById('qualityNote').style.display = 'none';

  // 解析画质：优先用户上次选择 → config 默认值 → 最接近可用画质
  const target = lastQuality || defaultQuality;
  const targetH = parseInt(target);
  let resolved = availableHeights[0] + 'p';
  for (const h of availableHeights) {
    if (h <= targetH) { resolved = h + 'p'; break; }
  }
  // 找不到 ≤ target 的，向上找最小的
  if (qualitySel.value === '' || !availableHeights.includes(targetH)) {
    for (const h of availableHeights) {
      if (h > targetH) { resolved = h + 'p'; break; }
    }
  }
  qualitySel.value = resolved;
  _lastSelectedQuality = resolved;
}

// ---- 全局状态 ----
let _mediaTypeOptions = [];
let _urlDebounceTimer = null;
let _cachedFormats = null;
let _cachedUrl = '';
let _lastSelectedQuality = null;
let _previousMt = null;
let _defaultQuality = null;
let _defaultAudioFormat = 'mp3';

// ---- URL 输入 ----
function onUrlInput() {
  document.getElementById('videoInfo').classList.add('hidden');
  _cachedFormats = null;
  _cachedUrl = '';
}

function onUrlBlur() {
  const url = document.getElementById('url').value.trim();
  if (!url) return;
  if (_urlDebounceTimer) clearTimeout(_urlDebounceTimer);
  _urlDebounceTimer = setTimeout(() => previewVideo(), 800);
}

// ---- 初始化 ----
async function init() {
  const [defaultsRes, optionsRes] = await Promise.all([
    fetch('/api/defaults'),
    fetch('/api/options'),
  ]);
  const d = await defaultsRes.json();
  const o = await optionsRes.json();

  // media_type
  _mediaTypeOptions = o.media_types.map(v => ({ value: v, label: v === 'video' ? '视频' : '音频' }));
  populateSelect('media_type', _mediaTypeOptions, d.media_type);

  _defaultQuality = d.quality;
  _defaultAudioFormat = d.audio_format || 'mp3';
  _lastSelectedQuality = d.quality;

  document.getElementById('media_type').addEventListener('change', () => {
    const currentMt = document.getElementById('media_type').value;
    if (currentMt !== 'audio') {
      if (_previousMt !== 'audio') {
        _lastSelectedQuality = document.getElementById('quality').value || _defaultQuality;
      }
    }
    updateQualityOptions();
    _previousMt = currentMt;
    _updateFormState();
  });

  // quality
  updateQualityOptions();
  document.getElementById('quality').addEventListener('change', function() {
    _lastSelectedQuality = this.value;
  });

  // whisper_language
  const slOptions = (o.subtitle_languages || []).map(v => ({ value: v, label: v }));
  slOptions.push({ value: 'other', label: '其他（手动输入）' });
  populateSelect('whisper_language', slOptions, d.whisper_language);

  // whisper_model
  populateSelect('whisper_model', o.whisper_models.map(v => ({ value: v, label: v })), d.whisper_model);

  // audio_format
  populateSelect('audio_format', o.audio_formats.map(v => ({ value: v, label: v.toUpperCase() })), d.audio_format);

  // cookies
  populateSelect('cookies', o.browsers.map(v => ({
    value: v,
    label: v === 'auto' ? '🔍 自动检测（推荐）' : v.charAt(0).toUpperCase() + v.slice(1),
  })), d.cookies_method);

  // checkbox 默认值
  if (d.separate_audio) document.getElementById('separate_audio').checked = true;
  if (d.srt !== undefined) document.getElementById('srt').checked = d.srt;
  if (d.md !== undefined) document.getElementById('md').checked = d.md;
  if (d.code_convert !== undefined) document.getElementById('code_convert').checked = d.code_convert;

  // output_dir
  if (d.output_dir) document.getElementById('output_dir').placeholder = d.output_dir;

  _updateFormState();
}

// ---- 预览画质选项更新（由 media_type 切换触发） ----
function updateQualityOptions() {
  const qualitySel = document.getElementById('quality');
  const currentUrl = document.getElementById('url').value.trim();

  if (document.getElementById('media_type').value === 'audio') {
    _buildQualityOptions(qualitySel, null, _lastSelectedQuality, _defaultQuality);
    return;
  }

  if (currentUrl && _cachedUrl === currentUrl && _cachedFormats) {
    _buildQualityOptions(qualitySel, _cachedFormats, _lastSelectedQuality, _defaultQuality);
  } else if (currentUrl) {
    previewVideo();
  } else {
    qualitySel.innerHTML = '<option value="">-- 先预览视频 --</option>';
    qualitySel.disabled = true;
    document.getElementById('qualityNote').style.display = 'inline';
  }
}

// ---- 消息框 ----
function _msgboxShow(title, body) {
  document.getElementById('msgboxTitle').textContent = title;
  document.getElementById('msgboxBody').textContent = body;
  document.getElementById('msgboxOverlay').classList.add('show');
}
function _msgboxClose() {
  document.getElementById('msgboxOverlay').classList.remove('show');
}
document.getElementById('msgboxOverlay').addEventListener('click', function(e) {
  if (e.target === this) _msgboxClose();
});

// ---- Whisper 语言：选择"其他"时显示自定义输入框 ----
document.getElementById('whisper_language').addEventListener('change', function() {
  const customInput = document.getElementById('whisper_language_custom');
  if (this.value === 'other') {
    customInput.classList.remove('hidden');
    customInput.focus();
  } else {
    customInput.classList.add('hidden');
    customInput.value = '';
  }
});

function getWhisperLanguage() {
  const sel = document.getElementById('whisper_language');
  if (sel.value === 'other') {
    return document.getElementById('whisper_language_custom').value.trim() || 'zh';
  }
  return sel.value;
}

// ---- 预览 ----
async function previewVideo() {
  const url = document.getElementById('url').value.trim();
  if (!url) { _msgboxShow('提示', '请先输入 YouTube 链接'); return; }

  const btn = document.getElementById('previewBtn');
  const info = document.getElementById('videoInfo');
  const qualitySel = document.getElementById('quality');

  btn.disabled = true;
  btn.textContent = '⏳ 预览中...';
  info.classList.add('hidden');
  qualitySel.disabled = true;
  qualitySel.innerHTML = '<option value="">加载中...</option>';

  try {
    const res = await fetch('/api/collect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, preview: true, cookies: document.getElementById('cookies').value }),
    });
    const r = await res.json();

    if (r.ok && r.formats) {
      _cachedFormats = r.formats;
      _cachedUrl = url;

      const result = r.result;
      info.innerHTML = `<span style="color:var(--success)">✅</span> ${result.title || '未知标题'} | ${result.channel || ''} | ${result.duration_str || ''} | ${result.upload_date || ''}`;
      info.classList.remove('hidden');

      _buildQualityOptions(qualitySel, r.formats, _lastSelectedQuality, _defaultQuality);
    } else {
      qualitySel.innerHTML = '<option value="">预览失败</option>';
      info.innerHTML = `<span style="color:var(--danger)">❌</span> ` + (r.error || '无法获取视频信息');
      info.classList.remove('hidden');
    }
  } catch(e) {
    qualitySel.innerHTML = '<option value="">预览失败</option>';
  } finally {
    btn.disabled = false;
    btn.textContent = '🔍 预览';
  }
}

// ---- 开始采集 ----
async function startCollect() {
  const url = document.getElementById('url').value.trim();
  if (!url) { _msgboxShow('提示', '请先输入 YouTube 链接'); return; }

  const media_type     = document.getElementById('media_type').value;
  const quality        = document.getElementById('quality').value || '360p';
  const whisper_model  = document.getElementById('whisper_model').value;
  const whisper_language = getWhisperLanguage();
  const srt            = document.getElementById('srt').checked;
  const md             = document.getElementById('md').checked;
  const cookies        = document.getElementById('cookies').value;
  const separate_audio = document.getElementById('separate_audio').checked;
  const audio_format   = document.getElementById('audio_format').value;
  const code_convert   = document.getElementById('code_convert').checked;
  const output_dir     = document.getElementById('output_dir').value.trim();

  const btn = document.getElementById('startBtn');
  const progress = document.getElementById('progress');
  const resultDiv = document.getElementById('result');
  const statusText = document.getElementById('statusText');

  btn.disabled = true;
  progress.style.display = 'block';
  resultDiv.style.display = 'none';
  resultDiv.className = 'result';
  resultDiv.textContent = '';
  statusText.textContent = '正在采集，请稍候...';

  try {
    const res = await fetch('/api/collect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url, media_type, quality, whisper_model, whisper_language, srt, md,
        cookies, separate_audio, audio_format, code_convert,
        output_dir: output_dir || undefined,
      }),
    });

    const r = await res.json();

    if (r.ok) {
      resultDiv.className = 'result ok';
      _msgboxShow('✅ 采集完成', r.summary || '采集完成');
      resultDiv.innerHTML = '<span class="success-badge">✅ 采集完成</span>\n\n' + (r.summary || '').replace(/\n/g, '<br>');
      if (r.result && r.result.transcript) {
        const t = r.result.transcript;
        let html = '<br><b>字幕/文本文件：</b><br>';
        for (const [k, v] of Object.entries(t)) {
          html += `  ${k}: ${v.split('/').pop()}<br>`;
        }
        resultDiv.innerHTML += html;
      }
      resultDiv.style.display = 'block';
      statusText.textContent = '采集完成';
    } else {
      resultDiv.className = 'result fail';
      resultDiv.textContent = '❌ ' + (r.error || '采集失败');
      resultDiv.style.display = 'block';
      _msgboxShow('❌ 采集失败', r.error || '未知错误');
      statusText.textContent = '采集失败';
    }
  } catch(e) {
    resultDiv.className = 'result fail';
    resultDiv.textContent = '请求失败: ' + e.message;
    resultDiv.style.display = 'block';
    _msgboxShow('❌ 请求失败', e.message);
    statusText.textContent = '请求失败';
  } finally {
    btn.disabled = false;
    setTimeout(() => { progress.style.display = 'none'; }, 3000);
  }
}

init();
